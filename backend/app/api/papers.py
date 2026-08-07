from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_db
from app.models import Author, Paper, PaperSimilarity, Topic
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


@router.get("/papers", response_model=PaperListResponse)
def list_papers(
    db: DbSession,
    q: Annotated[str | None, Query(max_length=200)] = None,
    year: int | None = None,
    topic: str | None = None,
    author: str | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 20,
) -> PaperListResponse:
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

    rows = db.execute(
        select(
            PaperSimilarity.similar_paper_id,
            Paper.title,
            PaperSimilarity.similarity_score,
        )
        .join(Paper, Paper.id == PaperSimilarity.similar_paper_id)
        .where(PaperSimilarity.paper_id == raw)
        .order_by(
            PaperSimilarity.similarity_score.desc(),
            PaperSimilarity.similar_paper_id.asc(),
        )
        .limit(SIMILAR_LIMIT)
    ).all()

    return [
        SimilarItem(
            id=row.similar_paper_id,
            title=row.title,
            similarity_score=round(row.similarity_score, 4),
        )
        for row in rows
    ]