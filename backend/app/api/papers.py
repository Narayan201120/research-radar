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
) -> PaperListResponse:
    if ranked and not q:
        raise HTTPException(status_code=422, detail="ranked=true requires q")
    if ranked and q:
        if db.get_bind().dialect.name == "postgresql":
            return _list_papers_ranked(
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