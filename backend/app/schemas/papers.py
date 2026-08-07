from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AuthorBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class TopicBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str


class PaperListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    publication_year: int
    cited_by_count: int
    authors: list[AuthorBrief]


class PaperListResponse(BaseModel):
    items: list[PaperListItem]
    total: int
    page: int
    page_size: int


class PaperDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    abstract: str | None
    publication_year: int
    doi: str | None
    cited_by_count: int
    created_at: datetime
    authors: list[AuthorBrief]
    topics: list[TopicBrief]


class SimilarItem(BaseModel):
    id: int
    title: str
    similarity_score: float