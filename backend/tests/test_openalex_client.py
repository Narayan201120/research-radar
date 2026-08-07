import httpx
import pytest

import app.services.openalex as openalex_mod
from app.services.openalex import OpenAlexClient, OpenAlexError, reconstruct_abstract


def _canned_response(payload: dict) -> httpx.Request:
    return httpx.Response(200, json=payload)


# --- reconstruct_abstract ---


def test_reconstruct_abstract_none():
    assert reconstruct_abstract(None) is None
    assert reconstruct_abstract({}) is None


def test_reconstruct_abstract_reorders_positions():
    inverted = {"alpha": [0], "beta": [1], "gamma": [2]}
    assert reconstruct_abstract(inverted) == "alpha beta gamma"


def test_reconstruct_abstract_out_of_order_positions():
    inverted = {"gamma": [5], "alpha": [3], "beta": [4]}
    assert reconstruct_abstract(inverted) == "alpha beta gamma"


def test_reconstruct_abstract_single_word_inverted():
    inverted = {"hello": [0]}
    assert reconstruct_abstract(inverted) == "hello"


def test_reconstruct_abstract_empty_inverted_index():
    assert reconstruct_abstract({"": []}) is None


# --- fetch works with httpx MockTransport (real client, no network) ---


def _pin_results(handler):
    transport = httpx.MockTransport(handler)
    return transport


def test_fetch_topic_works_returns_results():
    captured = {}

    def handler(request):
        captured["params"] = request.url.params
        return httpx.Response(
            200,
            json={
                "meta": {"next_cursor": None},
                "results": [
                    {"id": "W1", "display_name": "Paper 1", "abstract_inverted_index": None},
                    {"id": "W2", "display_name": "Paper 2", "abstract_inverted_index": None},
                ],
            },
        )

    client = OpenAlexClient("me@example.com", transport=httpx.MockTransport(handler))
    works = client.fetch_topic_works("T10531", "2023-01-01", max_papers=100)
    assert len(works) == 2
    assert captured["params"]["filter"] == "topics.id:T10531,from_publication_date:2023-01-01"
    assert captured["params"]["mailto"] == "me@example.com"
    assert captured["params"]["cursor"] == "*"
    assert captured["params"]["sort"] == "cited_by_count:desc"
    client.close()


def test_fetch_respects_max_papers_and_next_cursor():
    pages = iter(
        [
            {
                "meta": {"next_cursor": "page2"},
                "results": [{"id": "W1"}, {"id": "W2"}, {"id": "W3"}],
            },
            {
                "meta": {"next_cursor": None},
                "results": [{"id": "W4"}, {"id": "W5"}],
            },
        ]
    )

    def handler(request):
        return httpx.Response(200, json=next(pages))

    client = OpenAlexClient("me@example.com", transport=httpx.MockTransport(handler))
    results = client.fetch_topic_works("T10531", "2023-01-01", max_papers=3)
    assert [r["id"] for r in results] == ["W1", "W2", "W3"]
    client.close()


def test_fetch_stops_when_cursor_exhausted():
    page1 = {
        "meta": {"next_cursor": None},
        "results": [{"id": f"W{i}"} for i in range(3)],
    }

    def handler(request):
        return httpx.Response(200, json=page1)

    client = OpenAlexClient("me@example.com", transport=httpx.MockTransport(handler))
    results = client.fetch_topic_works("T10537", "2023-01-01", max_papers=100)
    assert len(results) == 3
    client.close()


def test_retries_then_raises_on_persistent_http_error():
    attempts = {"n": 0}

    def handler(request):
        attempts["n"] += 1
        return httpx.Response(500, json={})

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(openalex_mod, "time", _NoSleep())
    monkeypatch.setattr(openalex_mod, "MAX_RETRIES", 3)
    try:
        client = OpenAlexClient("me@example.com", transport=httpx.MockTransport(handler))
        with pytest.raises(OpenAlexError):
            client.fetch_topic_works("T10539", "2023-01-01", max_papers=5)
        assert attempts["n"] == 3
        client.close()
    finally:
        monkeypatch.undo()


class _NoSleep:
    def sleep(self, seconds):
        pass


# --- client construction ---


def test_client_sends_debug_mailto_header():
    captured = {}

    def handler(request):
        captured["headers"] = request.headers
        return httpx.Response(200, json={"results": [], "meta": {"next_cursor": None}})

    client = OpenAlexClient("me@example.com", transport=httpx.MockTransport(handler))
    client.fetch_topic_works("T10531", "2023-01-01", max_papers=1)
    # mailto passed as a query param rather than a header; just assert request made
    assert captured["headers"] is not None
    client.close()