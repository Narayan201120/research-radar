from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT_SECONDS = 15.0
MAX_WORKERS = 8
USER_AGENT = "research-radar-verifier/0.1 (link health check)"

DEAD_STATUS_CODES = {404, 410}
# Publishers like IEEE Xplore answer bots with 202/403, ACM/MDPI/Wiley with
# 403, ACL Anthology may drop the connection outright. None of those mean the
# link is broken for a human, so they must never count as "dead".


def classify_status(status_code: int) -> str:
    """Map an HTTP status to ok / dead / unknown.

    ``unknown`` covers bot-blocking and transient errors: the link is kept.
    Only definitive 404/410 mark a link as dead.
    """
    if status_code == 200:
        return "ok"
    if status_code in DEAD_STATUS_CODES:
        return "dead"
    return "unknown"


def _landing_candidates(work: dict) -> list[str]:
    """Working alternatives to the primary DOI, arXiv landing pages first."""
    candidates: list[str] = []
    for location in work.get("locations") or []:
        url = (location.get("landing_page_url") or "").strip()
        if url and url.startswith(("http://", "https://")):
            candidates.append(url)
    primary = (work.get("doi") or "").strip()
    if primary and primary.startswith(("http://", "https://")):
        candidates.append(primary)
    return list(dict.fromkeys(candidates))


def _arxiv_first(urls: list[str]) -> list[str]:
    return sorted(urls, key=lambda u: (0 if ("arxiv.org" in u or "10.48550" in u) else 1))


class DoiVerifier:
    """Checks a paper's landing URL resolves, with arXiv-first fallback.

    Uses a single shared client; each check gets a fresh request. Safe to
    share across threads because httpx.Client is read-mostly after creation.
    """

    def __init__(self, *, transport: httpx.BaseTransport | None = None) -> None:
        self.transport = transport
        self._client = httpx.Client(
            timeout=REQUEST_TIMEOUT_SECONDS,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT},
            transport=transport,
        )

    def close(self) -> None:
        self._client.close()

    def check(self, url: str) -> str:
        try:
            response = self._client.get(url)
            return classify_status(response.status_code)
        except httpx.HTTPError:
            logger.debug("landing URL check failed (transient/bot-block): %s", url)
            return "unknown"

    def resolve(self, work: dict) -> str | None:
        """Return the URL to store for this work, or None when it must be dropped.

        Strategy: if the primary DOI checks ok (or is ambiguous bot-block,
        which we keep), return it unchanged. If it is definitively dead,
        walk arXiv-first through alternate landing pages and return the first
        that resolves; return None when nothing resolves.
        """
        doi = (work.get("doi") or "").strip()
        if not doi:
            return None
        primary_status = self.check(doi)
        if primary_status != "dead":
            return doi
        for candidate in _arxiv_first(_landing_candidates(work)):
            if candidate == doi:
                continue
            if self.check(candidate) == "ok":
                logger.info("dead DOI %s replaced with %s", doi, candidate)
                return candidate
        logger.warning("no working landing page for %s (%s)", work.get("id"), doi)
        return None


def verify_works(
    works: list[dict],
    *,
    transport: httpx.BaseTransport | None = None,
) -> tuple[list[dict], list[dict], int]:
    """Filter works whose DOI is dead and could not be replaced.

    Returns (kept_works, dropped_works, replaced_count). Works with a missing
    DOI are kept: they simply have no publisher link. Only works whose DOI is
    definitively 404/410 AND has no resolving alternate landing page are
    dropped.
    """
    verifier = DoiVerifier(transport=transport)
    kept: list[dict] = []
    dropped: list[dict] = []
    replaced = 0
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        for work, url in zip(works, pool.map(verifier.resolve, works)):
            original = (work.get("doi") or "").strip()
            if url is None:
                if not original:
                    kept.append(work)  # no DOI at all: keep, just no link
                    continue
                dropped.append(work)
                continue
            if url != original:
                replaced += 1
            work["doi"] = url
            kept.append(work)
    verifier.close()
    return kept, dropped, replaced
