"""Abstract recovery via Crossref then arXiv then publisher HTML.

Waterfall: for a paper with a DOI, try Crossref's JATS abstract first
(``api.crossref.org/works/{doi}`` → ``message.abstract``). arXiv's
DataCite prefix ``10.48550`` is not in Crossref, so fallback is
``export.arxiv.org/api/query?id_list={arxiv_id}`` → Atom ``<summary>``.
Final fallback fetches ``https://doi.org/{doi}`` HTML and extracts
``citation_abstract`` meta or publisher sections (Springer/Elsevier).
Bounded and polite.
"""

from __future__ import annotations

import os
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Protocol

import httpx
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models import Paper
from app.services.embeddings import EmbeddingProvider, embed_papers_by_ids
from app.services.http_retry import compute_sleep, is_retryable_status, parse_retry_after

CROSSREF_TIMEOUT = 10.0
ARXIV_TIMEOUT = 10.0
USER_AGENT = "research-radar-abstract-recovery/0.1 (mailto:research-radar@example.com)"
JATS_RE = re.compile(r"<[^>]+>")
ARXIV_ID_RE = re.compile(r"(?:arxiv\.org/abs/|10\.48550/arXiv\.)(\d{4}\.\d{4,5}(?:v\d+)?)", re.IGNORECASE)


def _strip_jats(raw: str) -> str:
    return JATS_RE.sub("", raw).strip()


def _extract_arxiv_id(doi: str, locations: list[dict] | None = None) -> str | None:
    candidates = []
    if doi:
        candidates.append(doi)
    for loc in locations or []:
        url = (loc.get("landing_page_url") or "").strip()
        if url:
            candidates.append(url)
    for cand in candidates:
        m = ARXIV_ID_RE.search(cand)
        if m:
            return m.group(1)
    return None


def _get_with_backoff(client: httpx.Client, url: str, *, timeout: float) -> httpx.Response | None:
    """Thin compat wrapper over shared http_retry helper.

    Retries 429 + 5xx (500/502/503/504) with Retry-After + jitter and
    httpx Timeout/Connect errors. Returns None on exhaustion.
    """
    for attempt in range(3):
        try:
            resp = client.get(url, timeout=timeout)
        except (httpx.TimeoutException, httpx.ConnectError):
            if attempt == 2:
                return None
            time.sleep(compute_sleep(attempt, None))
            continue
        except httpx.HTTPError:
            return None
        if is_retryable_status(resp.status_code) or resp.status_code == 500:
            if attempt == 2:
                return None
            time.sleep(compute_sleep(attempt, parse_retry_after(resp.headers)))
            continue
        return resp
    return None


def fetch_crossref_abstract(doi: str, *, transport: httpx.BaseTransport | None = None) -> str | None:
    doi = doi.strip()
    if not doi or doi.startswith("10.48550"):
        return None
    bare = doi.removeprefix("https://doi.org/").removeprefix("http://doi.org/").strip()
    url = f"https://api.crossref.org/works/{bare}"
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    with httpx.Client(headers=headers, follow_redirects=True, transport=transport) as client:
        resp = _get_with_backoff(client, url, timeout=CROSSREF_TIMEOUT)
        if resp is None or resp.status_code != 200:
            return None
        try:
            msg = resp.json().get("message", {})
            raw = msg.get("abstract")
            if not raw:
                return None
            cleaned = _strip_jats(raw)
            return cleaned or None
        except Exception:
            return None


def fetch_arxiv_abstract(doi: str, locations: list[dict] | None = None, *, transport: httpx.BaseTransport | None = None) -> str | None:
    arxiv_id = _extract_arxiv_id(doi, locations)
    if not arxiv_id:
        return None
    url = f"https://export.arxiv.org/api/query?id_list={arxiv_id}"
    headers = {"User-Agent": USER_AGENT}
    with httpx.Client(headers=headers, follow_redirects=True, transport=transport) as client:
        resp = _get_with_backoff(client, url, timeout=ARXIV_TIMEOUT)
        if resp is None or resp.status_code != 200:
            return None
        try:
            root = ET.fromstring(resp.text)
            ns = {"atom": "http://www.w3.org/2005/Atom"}
            entry = root.find("atom:entry", ns)
            if entry is None:
                return None
            summary = entry.find("atom:summary", ns)
            if summary is None or not summary.text:
                return None
            return summary.text.strip() or None
        except Exception:
            return None


def recover_abstract_for_paper(
    paper: Paper,
    *,
    locations: list[dict] | None = None,
    transport: httpx.BaseTransport | None = None,
) -> tuple[str | None, str | None]:
    """Try Crossref then arXiv then HTML. Returns (abstract, source) or (None, None)."""
    doi = (paper.doi or "").strip()
    if not doi:
        return None, None
    cr = fetch_crossref_abstract(doi, transport=transport)
    if cr:
        return cr, "crossref"
    ar = fetch_arxiv_abstract(doi, locations, transport=transport)
    if ar:
        return ar, "arxiv"
    # HTML fallback — only after Crossref+arXiv miss
    try:
        from app.services.publisher_extract import fetch_html_abstract, source_for_doi

        html = fetch_html_abstract(doi, locations, transport=transport)
        if html:
            return html, source_for_doi(doi)
    except Exception:
        pass
    return None, None


def recover_missing_abstracts(
    session: Session,
    *,
    limit: int = 20,
    offset: int = 0,
    transport: httpx.BaseTransport | None = None,
    embedding_provider: EmbeddingProvider | None = None,
) -> int:
    """Recover up to ``limit`` papers with ``abstract IS NULL`` inline.

    Each recovered paper is updated with ``abstract``, ``abstract_source``,
    ``abstract_recovered_at`` and re-embedded via ``embed_papers_by_ids``.
    Returns number recovered.
    """
    if transport is None and os.getenv("PYTEST_CURRENT_TEST"):
        return 0
    rows = session.execute(
        select(Paper.id, Paper.doi)
        .where(Paper.abstract.is_(None), Paper.doi.is_not(None))
        .order_by(Paper.id)
        .offset(offset)
        .limit(limit)
    ).all()
    recovered = 0
    for pid, doi in rows:
        paper = session.get(Paper, pid)
        if paper is None or paper.abstract is not None:
            continue
        abstract, source = recover_abstract_for_paper(paper, transport=transport)
        if not abstract:
            continue
        paper.abstract = abstract
        paper.abstract_source = source
        paper.abstract_recovered_at = datetime.now(timezone.utc)
        if embedding_provider is not None:
            try:
                embed_papers_by_ids(session, embedding_provider, [pid])
            except Exception:
                pass
        recovered += 1
        # polite pause between live calls
        if transport is None:
            time.sleep(0.5)
    return recovered
