from __future__ import annotations

import time

import httpx

from app.services.http_retry import compute_sleep, is_retryable_status, parse_retry_after

PER_PAGE = 100
REQUEST_DELAY_SECONDS = 0.5
MAX_RETRIES = 3
DEFAULT_FROM_DATE = "2023-01-01"


class OpenAlexError(RuntimeError):
    pass


def reconstruct_abstract(inverted_index: dict | None) -> str | None:
    """Rebuild plain text from OpenAlex's inverted-index abstract."""
    if not inverted_index:
        return None
    positions: dict[int, str] = {}
    for word, indexes in inverted_index.items():
        for pos in indexes:
            positions[pos] = word
    if not positions:
        return None
    return " ".join(positions[i] for i in sorted(positions))


class OpenAlexClient:
    def __init__(
        self,
        mailto: str,
        *,
        base_url: str = "https://api.openalex.org",
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._mailto = mailto
        self._client = httpx.Client(base_url=base_url, timeout=30.0, transport=transport)

    def close(self) -> None:
        self._client.close()

    def _get(self, path: str, params: dict) -> dict:
        last_error: Exception | None = None
        for attempt in range(MAX_RETRIES):
            try:
                response = self._client.get(path, params=params)
            except (httpx.TimeoutException, httpx.ConnectError) as exc:
                # Retryable network errors only.
                last_error = exc
                if attempt == MAX_RETRIES - 1:
                    break
                time.sleep(compute_sleep(attempt, None))
                continue
            except httpx.HTTPError as exc:
                # Non-retryable transport error — fail fast, no sleep.
                raise OpenAlexError(f"OpenAlex request failed: {exc}") from exc
            # Retryable statuses: shared RETRYABLE (429/502/503/504) + 500
            # (500 kept for legacy compat; existing 500x3 test expects retry).
            if is_retryable_status(response.status_code) or response.status_code == 500:
                retry_after = parse_retry_after(response.headers)
                last_error = OpenAlexError(f"OpenAlex returned {response.status_code}")
                if attempt == MAX_RETRIES - 1:
                    break
                time.sleep(compute_sleep(attempt, retry_after))
                continue
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                # 400/401/403/404/422 etc — fail fast, no sleep/retry.
                raise OpenAlexError(f"OpenAlex request failed: {exc}") from exc
            return response.json()
        raise OpenAlexError(f"OpenAlex request failed after {MAX_RETRIES} attempts: {last_error}")

    def _paginate(self, base_params: dict, max_papers: int) -> list[dict]:
        results: list[dict] = []
        cursor: str | None = "*"
        while cursor and len(results) < max_papers:
            params = {
                **base_params,
                "per-page": str(PER_PAGE),
                "cursor": cursor,
            }
            data = self._get("/works", params)
            results.extend(data.get("results", []))
            cursor = (data.get("meta") or {}).get("next_cursor")
            if cursor:
                time.sleep(REQUEST_DELAY_SECONDS)
        return results[:max_papers]

    def fetch_topic_works(self, topic_id: str, from_date: str, max_papers: int) -> list[dict]:
        """Cursor-paginate the top-cited works for a topic since from_date."""
        return self._paginate(
            {
                "filter": f"topics.id:{topic_id},from_publication_date:{from_date}",
                "sort": "cited_by_count:desc",
                "mailto": self._mailto,
            },
            max_papers,
        )

    def fetch_updated_works(
        self, topic_id: str, from_updated_date: str, max_papers: int
    ) -> list[dict]:
        """Cursor-paginate works for a topic changed since from_updated_date.

        Sorts by ``updated_date`` instead of citations: freshly published or
        re-indexed works have ~0 citations and would never surface under the
        cited-by sort used for cold-start ingests.
        """
        return self._paginate(
            {
                "filter": f"topics.id:{topic_id},from_updated_date:{from_updated_date}",
                "sort": "updated_date:desc",
                "mailto": self._mailto,
            },
            max_papers,
        )
