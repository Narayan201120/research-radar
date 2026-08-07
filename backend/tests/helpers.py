from sqlalchemy.orm import Session

from app.models import Author, Paper, PaperAuthor, PaperSimilarity, PaperTopic, Topic


def add_topic(session: Session, slug: str, *, name: str | None = None, openalex_id: str | None = None) -> Topic:
    topic = Topic(
        slug=slug,
        name=name or slug.replace("-", " ").title(),
        openalex_id=openalex_id or f"T-{slug}",
    )
    session.add(topic)
    return topic


def add_author(session: Session, name: str, openalex_id: str | None = None) -> Author:
    author = Author(name=name, openalex_id=openalex_id or f"A-{name}")
    session.add(author)
    return author


def add_paper(
    session: Session,
    title: str,
    *,
    openalex_id: str | None = None,
    abstract: str | None = None,
    year: int = 2024,
    cited_by_count: int = 0,
    doi: str | None = None,
    authors: list[Author] | None = None,
    topics: list[Topic] | None = None,
) -> Paper:
    paper = Paper(
        openalex_id=openalex_id or f"W-{title}",
        title=title,
        abstract=abstract,
        publication_year=year,
        cited_by_count=cited_by_count,
        doi=doi,
    )
    session.add(paper)
    session.flush()
    for author in authors or []:
        session.add(PaperAuthor(paper_id=paper.id, author_id=author.id))
    for topic in topics or []:
        session.add(PaperTopic(paper_id=paper.id, topic_id=topic.id))
    return paper


def add_similarity(session: Session, paper_id: int, similar_paper_id: int, score: float) -> None:
    session.add(
        PaperSimilarity(
            paper_id=paper_id,
            similar_paper_id=similar_paper_id,
            similarity_score=score,
        )
    )


def make_work(
    openalex_id: str,
    title: str,
    *,
    year: int = 2024,
    abstract: str | None = None,
    cited_by_count: int = 0,
    doi: str | None = "https://doi.org/10.1/test",
    author_names: list[str] | None = ("Ada Lovelace",),
) -> dict:
    """A single OpenAlex \"work\" dict in the wire format ingest expects."""
    inverted = None
    if abstract:
        inverted = {}
        for pos, word in enumerate(abstract.split()):
            inverted.setdefault(word, []).append(pos)
    return {
        "id": f"https://openalex.org/{openalex_id}",
        "display_name": title,
        "publication_year": year,
        "publication_date": f"{year}-01-01",
        "abstract_inverted_index": inverted,
        "cited_by_count": cited_by_count,
        "doi": doi,
        "authorships": [
            {
                "author": {
                    "id": f"https://openalex.org/{name.replace(' ', '_')}",
                    "display_name": name,
                }
            }
            for name in author_names
        ],
    }