import httpx
import pytest

from app.services.doi_checker import (
    DoiVerifier,
    classify_status,
    verify_works,
)


# --- classify_status ---


def test_classify_status_ok():
    assert classify_status(200) == "ok"


def test_classify_status_dead_only_definitive():
    assert classify_status(404) == "dead"
    assert classify_status(410) == "dead"
    # bot-blocking / transient codes must never count as dead
    for status in (202, 403, 429, 500, 502, 503, 504, 301):
        assert classify_status(status) == "unknown", status


# --- DoiVerifier with MockTransport ---


def _handler(status_by_url, *, follow_count=None):
    def handler(request):
        url = str(request.url)
        if follow_count is not None and url in follow_count:
            return httpx.Response(302, headers={"Location": follow_count[url]})
        return httpx.Response(status_by_url.get(url, 200))

    return handler


def test_resolve_keeps_healthy_doi():
    transport = httpx.MockTransport(_handler({"https://doi.org/10.1/ok": 200}))
    verifier = DoiVerifier(transport=transport)
    work = {"id": "W1", "doi": "https://doi.org/10.1/ok", "locations": []}
    assert verifier.resolve(work) == "https://doi.org/10.1/ok"
    verifier.close()


def test_resolve_keeps_bot_blocked_doi():
    # IEEE answers bots with 202, ACM with 403 - both are fine for humans
    transport = httpx.MockTransport(_handler({"https://doi.org/10.1/ieee": 202}))
    verifier = DoiVerifier(transport=transport)
    work = {"id": "W1", "doi": "https://doi.org/10.1/ieee", "locations": []}
    assert verifier.resolve(work) == "https://doi.org/10.1/ieee"
    verifier.close()


def test_resolve_replaces_dead_doi_with_arxiv_fallback():
    def handler(request):
        url = str(request.url)
        if url == "https://doi.org/10.1/dead":
            return httpx.Response(404)
        if "arxiv.org" in url:
            return httpx.Response(200)
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    verifier = DoiVerifier(transport=transport)
    work = {
        "id": "W1",
        "doi": "https://doi.org/10.1/dead",
        "locations": [
            {"landing_page_url": "https://arxiv.org/abs/1706.03762"},
            {"landing_page_url": "https://somewhere.example/p"},
        ],
    }
    assert verifier.resolve(work) == "https://arxiv.org/abs/1706.03762"
    verifier.close()


def test_resolve_returns_none_when_no_alternate_resolves():
    def handler(request):
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    verifier = DoiVerifier(transport=transport)
    work = {
        "id": "W1",
        "doi": "https://doi.org/10.1/dead",
        "locations": [{"landing_page_url": "https://dead.example/p"}],
    }
    assert verifier.resolve(work) is None
    verifier.close()


def test_resolve_returns_none_for_missing_doi():
    transport = httpx.MockTransport(_handler({}))
    verifier = DoiVerifier(transport=transport)
    work = {"id": "W1", "doi": "", "locations": []}
    assert verifier.resolve(work) is None
    verifier.close()


# --- verify_works batch filter ---


def test_verify_works_drops_only_unresolvable_dead_dois():
    def handler(request):
        url = str(request.url)
        if url == "https://doi.org/10.1/dead":
            return httpx.Response(404)
        if "arxiv.org" in url:
            return httpx.Response(200)
        if url == "https://doi.org/10.1/ieee":
            return httpx.Response(202)
        return httpx.Response(200)

    transport = httpx.MockTransport(handler)
    works = [
        {"id": "W1", "doi": "https://doi.org/10.1/ok", "locations": []},
        {"id": "W2", "doi": "https://doi.org/10.1/ieee", "locations": []},  # bot-block: keep
        {"id": "W3", "doi": "https://doi.org/10.1/dead", "locations": [{"landing_page_url": "https://arxiv.org/abs/1"}]},  # fallback
        {"id": "W4", "doi": "https://doi.org/10.1/dead", "locations": []},  # drop
        {"id": "W5", "doi": None, "locations": []},  # no DOI: keep
    ]
    kept, dropped, replaced = verify_works(works, transport=transport)
    assert [w["id"] for w in kept] == ["W1", "W2", "W3", "W5"]
    assert [w["id"] for w in dropped] == ["W4"]
    assert replaced == 1
    assert next(w for w in kept if w["id"] == "W3")["doi"] == "https://arxiv.org/abs/1"
