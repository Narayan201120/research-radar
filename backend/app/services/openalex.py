from __future__ import annotations

import time

import httpx

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
                if response.status_code in (429, 500, 502, 503, 504):
                    raise OpenAlexError(f"OpenAlex returned {response.status_code}")
                response.raise_for_status()
                return response.json()
            except Exception as exc:  # retryable: network + 429/5xx
                last_error = exc
                time.sleep(2**attempt)
        raise OpenAlexError(f"OpenAlex request failed after {MAX_RETRIES} attempts: {last_error}")

    def fetch_topic_works(self, topic_id: str, from_date: str, max_papers: int) -> list[dict]:
        """Cursor-paginate the top-cited works for a topic since from_date."""
        results: list[dict] = []
        cursor: str | None = "*"
        while cursor and len(results) < max_papers:
            params = {
                "filter": f"topics.id:{topic_id},from_publication_date:{from_date}",
                "sort": "cited_by_count:desc",
                "per-page": str(PER_PAGE),
                "cursor": cursor,
                "mailto": self._mailto,
            }
            data = self._get("/works", params)
            results.extend(data.get("results", []))
            cursor = (data.get("meta") or {}).get("next_cursor")
            time.sleep(REQUEST_DELAY_SECONDS)
        return results[:max_papers]
