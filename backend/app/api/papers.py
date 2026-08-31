from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, func, or_, select, text
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_db
from app.models import Author, Paper, Topic
from app.schemas.papers import (
    PaperDetail,
    PaperListItem,
    PaperListResponse,
    SimilarItem,
)

router = APIRouter(tags=["papers"])

DbSession = Annotated[Session, Depends(get_db)]

MAX_PAGE_SIZE = 100
SIMILAR_LIMIT = 5

_ANN_SIMILAR_SQL = text(
    """
    SELECT pe.paper_id AS similar_paper_id,
           p.title,
           1 - (pe.embedding <=> self.embedding) AS similarity_score
    FROM paper_embedding self
    JOIN paper_embedding pe ON pe.paper_id <> self.paper_id
    JOIN paper p ON p.id = pe.paper_id
    WHERE self.paper_id = :paper_id
    ORDER BY pe.embedding <=> self.embedding, pe.paper_id ASC
    LIMIT :limit
    """
)


def _similar_via_vectors(db: Session, paper_id: int) -> list[SimilarItem] | None:
    """HNSW-backed neighbors; ``None`` signals the paper has no stored vector."""
    has_self_vector = db.execute(
        text("SELECT 1 FROM paper_embedding WHERE paper_id = :pid"),
        {"pid": paper_id},
    ).first()
    if has_self_vector is None:
        return None
    items = [
        SimilarItem(
            id=row.similar_paper_id,
            title=row.title,
            similarity_score=round(float(row.similarity_score), 4),
        )
        for row in db.execute(_ANN_SIMILAR_SQL, {"paper_id": paper_id, "limit": SIMILAR_LIMIT})
        if float(row.similarity_score) > 0
    ]
    return items


def _escape_like(value: str) -> str:
    """Escape LIKE wildcards so user input matches literally."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _parse_paper_id(raw: str) -> int | None:
    try:
        return int(raw)
    except ValueError:
        return None


def _paper_wildcard(term: str) -> str:
    return f"%{_escape_like(term)}%"


_MATCH_CLAUSE = "(p.id @@@ paradedb.match('title', :q) OR p.id @@@ paradedb.match('abstract', :q))"

_RRF_K = 60


def _rrf_fuse(dense_ids: list[int], sparse_ids: list[int], k: int = _RRF_K) -> list[int]:
    scores: dict[int, float] = {}
    for rank, pid in enumerate(dense_ids):
        scores[pid] = scores.get(pid, 0.0) + 1.0 / (k + rank + 1)
    for rank, pid in enumerate(sparse_ids):
        scores[pid] = scores.get(pid, 0.0) + 1.0 / (k + rank + 1)
    return sorted(scores, key=lambda pid: scores[pid], reverse=True)


def _list_papers_hybrid(
    db: Session,
    *,
    q: str,
    year: int | None,
    topic: str | None,
    author: str | None,
    page: int,
    page_size: int,
) -> PaperListResponse:
    """Hybrid RRF: dense 10 (pgvector HNSW) + sparse 10 (BM25) → RRF → filters after."""
    # dense 10
    dense_ids: list[int] = []
    try:
        from app.services.embeddings import FastEmbedProvider, vector_literal

        provider = FastEmbedProvider()
        qvec = provider.embed_texts([q])[0]
        literal = vector_literal(qvec)
        rows = db.execute(
            text("SELECT paper_id FROM paper_embedding ORDER BY embedding <=> CAST(:qvec AS vector) LIMIT 10"),
            {"qvec": literal},
        ).all()
        dense_ids = [r.paper_id for r in rows]
    except Exception:
        dense_ids = []

    # sparse 10
    sparse_ids: list[int] = []
    try:
        rows = db.execute(
            text(
                "SELECT p.id FROM paper p "
                f"WHERE {_MATCH_CLAUSE} "
                "ORDER BY paradedb.score(p.id) DESC LIMIT 10"
            ),
            {"q": q},
        ).all()
        sparse_ids = [r.id for r in rows]
    except Exception:
        sparse_ids = []

    fused = _rrf_fuse(dense_ids, sparse_ids)  # at most 20 → 10
    if not fused:
        return PaperListResponse(items=[], total=0, page=page, page_size=page_size)

    # hydrate in RRF order, then apply filters after (Option A)
    papers = db.scalars(
        select(Paper).options(selectinload(Paper.authors)).where(Paper.id.in_(fused))
    ).all()
    by_id = {p.id: p for p in papers}
    ordered = [by_id[pid] for pid in fused if pid in by_id]

    # filters after fusion
    def _keep(p: Paper) -> bool:
        if year is not None and p.publication_year != year:
            return False
        if topic and not any(t.slug == topic for t in p.topics):
            # need topics loaded — for hybrid we didn't load topics, check via query
            return False
        if author and not any(author.lower() in a.name.lower() for a in p.authors):
            return False
        return True

    # For topic filter we need topics; load them if needed
    if topic:
        # reload with topics for accurate filter
        papers_with_topics = db.scalars(
            select(Paper).options(selectinload(Paper.authors), selectinload(Paper.topics)).where(Paper.id.in_(fused))
        ).all()
        by_id_t = {p.id: p for p in papers_with_topics}
        ordered = [by_id_t[pid] for pid in fused if pid in by_id_t]
        filtered = [p for p in ordered if _keep(p)]
    else:
        filtered = [p for p in ordered if _keep(p)]

    total = len(filtered)
    start = (page - 1) * page_size
    page_items = filtered[start : start + page_size]

    # need topics for response? PaperListItem only needs authors, not topics
    return PaperListResponse(
        items=[PaperListItem.model_validate(p) for p in page_items],
        total=total,
        page=page,
        page_size=page_size,
    )


def _list_papers_ranked(
    db: Session,
    *,
    q: str,
    year: int | None,
    topic: str | None,
    author: str | None,
    page: int,
    page_size: int,
) -> PaperListResponse:
    """BM25-relevance listing via the paper_search_idx ParadeDB index.

    Deterministic pagination: score DESC, then year DESC, id DESC.
    """
    filters = ""
    params: dict[str, object] = {"q": q}
    if year is not None:
        filters += " AND p.publication_year = :year"
        params["year"] = year
    if topic:
        filters += (
            " AND EXISTS (SELECT 1 FROM paper_topic pt JOIN topic t ON t.id = pt.topic_id"
            " WHERE pt.paper_id = p.id AND t.slug = :topic)"
        )
        params["topic"] = topic
    if author:
        filters += (
            " AND EXISTS (SELECT 1 FROM paper_author pa JOIN author a ON a.id = pa.author_id"
            " WHERE pa.paper_id = p.id AND a.name ILIKE :author_wild)"
        )
        params["author_wild"] = _paper_wildcard(author)

    where = f"WHERE {_MATCH_CLAUSE}{filters}"
    total = int(
        db.execute(text(f"SELECT count(*) FROM paper p {where}"), params).scalar_one()
    )
    rows = db.execute(
        text(
            "SELECT p.id FROM paper p "
            f"{where} "
            "ORDER BY paradedb.score(p.id) DESC, p.publication_year DESC, p.id DESC "
            "LIMIT :limit OFFSET :offset"
        ),
        {**params, "limit": page_size, "offset": (page - 1) * page_size},
    ).all()
    ids = [row.id for row in rows]
    if not ids:
        return PaperListResponse(items=[], total=total, page=page, page_size=page_size)

    papers = db.scalars(
        select(Paper).options(selectinload(Paper.authors)).where(Paper.id.in_(ids))
    ).all()
    by_id = {p.id: p for p in papers}
    return PaperListResponse(
        items=[PaperListItem.model_validate(by_id[pid]) for pid in ids if pid in by_id],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/papers", response_model=PaperListResponse)
def list_papers(
    db: DbSession,
    q: Annotated[str | None, Query(max_length=200)] = None,
    year: int | None = None,
    topic: str | None = None,
    author: str | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 20,
    ranked: Annotated[bool, Query()] = False,
    hybrid: Annotated[bool, Query()] = False,
) -> PaperListResponse:
    if ranked and hybrid:
        raise HTTPException(status_code=422, detail="ranked and hybrid are mutually exclusive")
    if ranked and not q:
        raise HTTPException(status_code=422, detail="ranked=true requires q")
    if hybrid and not q:
        raise HTTPException(status_code=422, detail="hybrid=true requires q")
    if ranked and q:
        if db.get_bind().dialect.name == "postgresql":
            return _list_papers_ranked(
                db, q=q, year=year, topic=topic, author=author,
                page=page, page_size=page_size,
            )
        # non-PostgreSQL dialects (tests) degrade to the legacy path
    if hybrid and q:
        if db.get_bind().dialect.name == "postgresql":
            return _list_papers_hybrid(
                db, q=q, year=year, topic=topic, author=author,
                page=page, page_size=page_size,
            )
        # non-PostgreSQL dialects (tests) degrade to the legacy path

    conditions = []
    if q:
        terms = [t for t in q.split() if t]
        term_conditions = [
            or_(
                Paper.title.ilike(_paper_wildcard(term), escape="\\"),
                Paper.abstract.ilike(_paper_wildcard(term), escape="\\"),
            )
            for term in terms
        ]
        conditions.append(and_(*term_conditions))
    if year is not None:
        conditions.append(Paper.publication_year == year)
    if topic:
        conditions.append(Paper.topics.any(Topic.slug == topic))
    if author:
        conditions.append(
            Paper.authors.any(Author.name.ilike(_paper_wildcard(author), escape="\\"))
        )

    total = db.scalar(select(func.count()).select_from(Paper).where(*conditions)) or 0
    papers = db.scalars(
        select(Paper)
        .options(selectinload(Paper.authors))
        .where(*conditions)
        .order_by(Paper.publication_year.desc(), Paper.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    return PaperListResponse(
        items=[PaperListItem.model_validate(paper) for paper in papers],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/papers/{paper_id}", response_model=PaperDetail)
def get_paper(paper_id: str, db: DbSession) -> PaperDetail:
    parsed = _parse_paper_id(paper_id)
    if parsed is None:
        raise HTTPException(status_code=404, detail="Paper not found")
    paper = db.scalar(
        select(Paper)
        .options(selectinload(Paper.authors), selectinload(Paper.topics))
        .where(Paper.id == parsed)
    )
    if paper is None:
        raise HTTPException(status_code=404, detail="Paper not found")
    return PaperDetail.model_validate(paper)


@router.get("/papers/{paper_id}/similar", response_model=list[SimilarItem])
def get_similar_papers(paper_id: str, db: DbSession) -> list[SimilarItem]:
    raw = _parse_paper_id(paper_id)
    if raw is None:
        raise HTTPException(status_code=404, detail="Paper not found")
    exists = db.scalar(select(Paper.id).where(Paper.id == raw))
    if exists is None:
        raise HTTPException(status_code=404, detail="Paper not found")

    if db.get_bind().dialect.name == "postgresql":
        vector_items = _similar_via_vectors(db, raw)
        if vector_items is not None:
            return vector_items

    return []