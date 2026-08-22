from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

import httpx
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Author, IngestState, Paper, PaperAuthor, PaperSimilarity, PaperTopic, Topic
from app.services.doi_checker import verify_works
from app.services.openalex import OpenAlexClient, reconstruct_abstract
from app.services.similarity import build_tfidf_matrix, find_top_similar

logger = logging.getLogger(__name__)

MIN_TOTAL_PAPERS = 300
MAX_TOTAL_PAPERS = 500
PER_TOPIC_TARGET = 200
PER_TOPIC_MAX = 250
INCREMENTAL_MAX_PER_TOPIC = 200

DATE_LADDER = [
    "2023-01-01",
    "2022-01-01",
    "2021-01-01",
    "2020-01-01",
    "2019-01-01",
    "2018-01-01",
]


@dataclass
class IngestReport:
    topics_fetched: dict[str, int] = field(default_factory=dict)
    papers: int = 0
    papers_new: int = 0
    papers_updated: int = 0
    authors: int = 0
    relations: int = 0
    similarity_pairs: int = 0
    papers_in_db: int = 0
    fell_back_to: str | None = None
    dois_checked: int = 0
    dois_replaced: int = 0
    dois_dropped: int = 0


def _fetch_topic(client: OpenAlexClient, topic_id: str) -> tuple[list[dict], str]:
    """Fetch up to target for a topic, widening the window only as a last resort."""
    works: list[dict] = []
    for from_date in DATE_LADDER:
        batch = client.fetch_topic_works(topic_id, from_date, PER_TOPIC_MAX)
        if len(batch) >= PER_TOPIC_TARGET:
            return batch, from_date
        works = batch  # remember the widest attempt
    return works, DATE_LADDER[-1]


def _normalize_work(work: dict) -> dict | None:
    title = (work.get("display_name") or "").strip()
    if not title:
        return None
    openalex_id = (work.get("id") or "").rsplit("/", 1)[-1]
    if not openalex_id:
        return None
    year = work.get("publication_year") or (work.get("publication_date") or "")[:4] or None
    return {
        "openalex_id": openalex_id,
        "title": title,
        "abstract": reconstruct_abstract(work.get("abstract_inverted_index")),
        "publication_year": int(year) if year else None,
        "doi": work.get("doi"),
        "cited_by_count": work.get("cited_by_count") or 0,
        "authors": [
            {
                "openalex_id": ((a.get("author") or {}).get("id") or "").rsplit("/", 1)[-1],
                "name": ((a.get("author") or {}).get("display_name") or "").strip(),
            }
            for a in work.get("authorships", [])
        ],
    }


def _upsert_topic(session: Session, slug: str, openalex_id: str, name: str) -> Topic:
    topic = session.scalar(select(Topic).where(Topic.slug == slug))
    if topic is None:
        topic = Topic(slug=slug, openalex_id=openalex_id, name=name)
        session.add(topic)
    return topic


def _upsert_author(session: Session, openalex_id: str, name: str) -> Author | None:
    if not openalex_id:
        return None
    author = session.scalar(select(Author).where(Author.openalex_id == openalex_id))
    if author is None:
        author = Author(openalex_id=openalex_id, name=name)
        session.add(author)
        session.flush()  # assign id before junction rows reference it
    return author


def _normalize_fetched(fetched: dict[str, list[dict]]) -> dict[str, dict]:
    """Normalize works and dedupe across topics by openalex_id.

    A work fetched under several topics stays one paper carrying every
    topic slug it appeared under.
    """
    normalized: dict[str, dict] = {}
    for slug, batch in fetched.items():
        for work in batch:
            paper = _normalize_work(work)
            if paper is None:
                continue
            stored = normalized.setdefault(paper["openalex_id"], paper)
            stored.setdefault("_topics", set()).add(slug)
    return normalized


def _drop_unresolvable_dois(
    fetched: dict[str, list[dict]],
    report: IngestReport,
    transport: httpx.BaseTransport | None,
) -> None:
    """Verify DOIs in place; works with dead DOIs and no mirror are removed."""
    all_works = [w for batch in fetched.values() for w in batch]
    report.dois_checked = sum(1 for w in all_works if (w.get("doi") or "").strip())
    kept, dropped, replaced = verify_works(all_works, transport=transport)
    report.dois_replaced = replaced
    report.dois_dropped = len(dropped)
    if dropped:
        logger.warning(
            "dropping %s works with unresolvable DOIs: %s",
            len(dropped),
            ", ".join(str(w.get("id")) for w in dropped),
        )
    by_id = {w.get("id"): w for w in kept}
    for slug, batch in fetched.items():
        fetched[slug] = [w for w in batch if w.get("id") in by_id]


def _apply_normalized_works(
    session: Session,
    normalized: dict[str, dict],
    topic_rows: dict[str, Topic],
    report: IngestReport,
) -> None:
    """Upsert papers (assign ids via flush), then authors and junction rows."""
    papers_by_openalex: dict[str, Paper] = {}
    for openalex_id, data in normalized.items():
        paper = session.scalar(select(Paper).where(Paper.openalex_id == openalex_id))
        is_new = paper is None
        if is_new:
            paper = Paper(openalex_id=openalex_id)
            session.add(paper)
        paper.title = data["title"]
        paper.abstract = data["abstract"]
        paper.publication_year = data["publication_year"]
        paper.doi = data["doi"]
        paper.cited_by_count = data["cited_by_count"]
        if is_new:
            report.papers_new += 1
        else:
            report.papers_updated += 1
        papers_by_openalex[openalex_id] = paper
    session.flush()  # all papers get ids now

    paper_ids = [p.id for p in papers_by_openalex.values()]
    existing_author_rels = {
        (r.paper_id, r.author_id)
        for r in session.scalars(select(PaperAuthor).where(PaperAuthor.paper_id.in_(paper_ids)))
    }
    existing_topic_rels = {
        (r.paper_id, r.topic_id)
        for r in session.scalars(select(PaperTopic).where(PaperTopic.paper_id.in_(paper_ids)))
    }

    author_rows: dict[str, Author] = {}
    for openalex_id, data in normalized.items():
        paper = papers_by_openalex[openalex_id]

        for author_data in data["authors"]:
            author = author_rows.get(author_data["openalex_id"]) or _upsert_author(
                session, author_data["openalex_id"], author_data["name"]
            )
            if author is not None:
                author_rows.setdefault(author_data["openalex_id"], author)
                key = (paper.id, author.id)
                if key not in existing_author_rels:
                    existing_author_rels.add(key)
                    session.add(PaperAuthor(paper_id=paper.id, author_id=author.id))
                    report.relations += 1

        for slug in data["_topics"]:
            topic = topic_rows[slug]
            key = (paper.id, topic.id)
            if key not in existing_topic_rels:
                existing_topic_rels.add(key)
                session.add(PaperTopic(paper_id=paper.id, topic_id=topic.id))
                report.relations += 1

    report.authors = len(author_rows)


def _seed_watermarks(session: Session, topics: list[tuple[str, str, str]]) -> None:
    """Record full-ingest time per topic so incremental runs know where to resume."""
    ingested_at = datetime.now(timezone.utc)
    for slug, _topic_id, _name in topics:
        state = session.scalar(select(IngestState).where(IngestState.topic_slug == slug))
        if state is None:
            state = IngestState(topic_slug=slug)
            session.add(state)
        state.last_full_ingest_at = ingested_at
        state.last_incremental_at = ingested_at


def _as_utc(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def run_ingest(
    session: Session,
    client: OpenAlexClient,
    topics: list[tuple[str, str, str]],
    *,
    only_if_empty: bool = False,
    verify_dois: bool = False,
    doi_transport: httpx.BaseTransport | None = None,
) -> IngestReport:
    """Upsert papers/authors/topics + rebuild junctions inside one transaction.

    topics: list of (slug, openalex_topic_id, display_name).
    verify_dois: when True, DOIs are checked at ingest; works whose DOI is
    definitively dead (404/410) and has no resolving alternate landing page
    are dropped before normalization. doi_transport overrides the HTTP
    transport (tests).
    """
    report = IngestReport()

    if only_if_empty:
        existing = session.scalar(select(func.count()).select_from(Paper)) or 0
        if existing > 0:
            logger.info("papers already present (%s), skipping ingest", existing)
            report.papers_in_db = existing
            return report

    # 1. Ensure the two topic rows exist
    topic_rows: dict[str, Topic] = {}
    for slug, topic_id, name in topics:
        topic_rows[slug] = _upsert_topic(session, slug, topic_id, name)

    # 2. Fetch per topic
    fetched: dict[str, list[dict]] = {}
    fell_back = False
    for slug, topic_id, _name in topics:
        batch, from_date = _fetch_topic(client, topic_id)
        fetched[slug] = batch
        report.topics_fetched[slug] = len(batch)
        if from_date != DATE_LADDER[0]:
            fell_back = True
        logger.info("topic %s: fetched %s papers (from %s)", slug, len(batch), from_date)
    report.fell_back_to = None if not fell_back else "date ladder"

    # 2b. Verify DOIs before normalizing (dropped works never reach the DB)
    if verify_dois:
        _drop_unresolvable_dois(fetched, report, transport=doi_transport)

    # 3. Normalize + dedupe across topics by openalex_id
    normalized = _normalize_fetched(fetched)

    total = len(normalized)
    if total < MIN_TOTAL_PAPERS:
        raise RuntimeError(
            f"ingest produced only {total} papers; "
            f"minimum is {MIN_TOTAL_PAPERS} (check topic IDs and OpenAlex availability)"
        )
    if total > MAX_TOTAL_PAPERS:
        raise RuntimeError(
            f"ingest produced {total} papers; maximum is {MAX_TOTAL_PAPERS}"
        )
    report.papers = total

    # 4-5. Upsert papers, authors, and junction rows
    _apply_normalized_works(session, normalized, topic_rows, report)

    # 6. Rebuild the similarity snapshot in the same transaction
    report.similarity_pairs = rebuild_similarity(session)
    _seed_watermarks(session, topics)
    session.commit()

    report.papers_in_db = session.scalar(select(func.count()).select_from(Paper)) or 0
    logger.info("ingest complete: %s papers (%s new, %s updated)", report.papers, report.papers_new, report.papers_updated)
    return report


def run_incremental_ingest(
    session: Session,
    client: OpenAlexClient,
    topics: list[tuple[str, str, str]],
    *,
    verify_dois: bool = False,
    doi_transport: httpx.BaseTransport | None = None,
    max_papers_per_topic: int = INCREMENTAL_MAX_PER_TOPIC,
    since_date: str | None = None,
) -> IngestReport:
    """Fetch works changed since each topic's watermark and upsert them.

    The 300-500 corpus guards deliberately do not apply here: a quiet day
    may legitimately bring zero new works. Raises RuntimeError when a topic
    has no watermark yet (run a full ingest first). On success every
    watermark advances to the fetch *start* time inside the same transaction
    as the data, so a crash rolls both back and nothing is missed next run.
    Day-level filter granularity means same-day churn can be refetched;
    upsert-by-openalex-id makes that safe. ``since_date`` (YYYY-MM-DD)
    overrides the stored watermark for manual backfills.
    """
    report = IngestReport()
    started_at = datetime.now(timezone.utc)

    states: dict[str, IngestState] = {}
    for slug, _topic_id, _name in topics:
        state = session.scalar(select(IngestState).where(IngestState.topic_slug == slug))
        if state is None or state.last_incremental_at is None:
            raise RuntimeError(
                f"no ingest watermark for topic '{slug}'; run a full ingest first"
            )
        states[slug] = state

    topic_rows: dict[str, Topic] = {
        slug: _upsert_topic(session, slug, topic_id, name)
        for slug, topic_id, name in topics
    }

    fetched: dict[str, list[dict]] = {}
    for slug, topic_id, _name in topics:
        since = (
            since_date
            or _as_utc(states[slug].last_incremental_at).date().isoformat()
        )
        batch = client.fetch_updated_works(topic_id, since, max_papers_per_topic)
        fetched[slug] = batch
        report.topics_fetched[slug] = len(batch)
        logger.info("incremental %s: %s changed works since %s", slug, len(batch), since)

    if verify_dois and any(fetched.values()):
        _drop_unresolvable_dois(fetched, report, transport=doi_transport)

    normalized = _normalize_fetched(fetched)
    report.papers = len(normalized)

    if normalized:
        _apply_normalized_works(session, normalized, topic_rows, report)
        report.similarity_pairs = rebuild_similarity(session)

    for state in states.values():
        state.last_incremental_at = started_at

    session.commit()

    report.papers_in_db = session.scalar(select(func.count()).select_from(Paper)) or 0
    logger.info(
        "incremental complete: %s changed (%s new, %s updated)",
        report.papers,
        report.papers_new,
        report.papers_updated,
    )
    return report


def rebuild_similarity(session: Session, top_k: int = 5) -> int:
    """Regenerate the paper_similarity snapshot inside the current transaction.

    Every paper gets up to ``top_k`` neighbors with score > 0. Papers with no
    text (no title and no abstract) produce zero vectors and therefore no rows.
    """
    clear_similarity(session)
    rows = session.execute(select(Paper.id, Paper.title, Paper.abstract).order_by(Paper.id)).all()
    if len(rows) < 2:
        return 0

    ids = [int(row.id) for row in rows]
    texts = [
        " ".join(part.strip() for part in (row.title, row.abstract) if part and part.strip())
        for row in rows
    ]
    matrix = build_tfidf_matrix(texts)
    triples = find_top_similar(matrix, top_k)
    session.add_all(
        PaperSimilarity(paper_id=ids[i], similar_paper_id=ids[j], similarity_score=score)
        for i, j, score in triples
    )
    return len(triples)


def run_similarity_rebuild(session: Session, top_k: int = 5) -> int:
    """Standalone similarity-only rebuild in its own transaction."""
    count = rebuild_similarity(session)
    session.commit()
    return count


def clear_similarity(session: Session) -> None:
    """Wipe stale similarity snapshot before regenerating (same transaction)."""
    session.execute(PaperSimilarity.__table__.delete())


def backfill_watermarks(session: Session, topics: list[tuple[str, str, str]]) -> None:
    """Ensure every topic has a watermark row (upgrade path).

    Databases ingested before watermarks existed get a baseline stamped at
    upgrade time: there is no fetch history to reconstruct, so "now" becomes
    the point from which change tracking starts.
    """
    now = datetime.now(timezone.utc)
    for slug, _topic_id, _name in topics:
        state = session.scalar(select(IngestState).where(IngestState.topic_slug == slug))
        if state is None:
            session.add(IngestState(topic_slug=slug, last_incremental_at=now))
            logger.info("seeded watermark for topic '%s' at upgrade baseline", slug)
    session.commit()


def resolve_boot_action(papers: int, similarity_pairs: int) -> str:
    """What ``--boot`` should do, given current table sizes."""
    if papers == 0:
        return "ingest"
    if similarity_pairs == 0:
        return "rebuild-similarity"
    return "skip"
