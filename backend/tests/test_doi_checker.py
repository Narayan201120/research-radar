import httpx

from app.services.doi_checker import DoiVerifier, _is_private_url, verify_works


def test_private_urls_are_blocked():
    assert _is_private_url("http://127.0.0.1/secret") is True
    assert _is_private_url("http://192.168.1.1/admin") is True
    assert _is_private_url("http://10.0.0.5/") is True
    assert _is_private_url("http://169.254.169.254/latest/meta-data/") is True
    assert _is_private_url("http://[::1]/") is True
    assert _is_private_url("http://localhost/paper") is True
    assert _is_private_url("file:///etc/passwd") is True
    assert _is_private_url("https://doi.org/10.1234/test") is False
    assert _is_private_url("https://arxiv.org/abs/2301.00001") is False


def test_private_doi_is_kept_not_fetched():
    def handler(request):
        raise AssertionError("private host must not be fetched")

    transport = httpx.MockTransport(handler)
    verifier = DoiVerifier(transport=transport)
    # 127.0.0.1 is private → check returns unknown without calling transport
    assert verifier.check("http://127.0.0.1/secret") == "unknown"
    verifier.close()


def test_verify_works_keeps_private_doi():
    works = [{"id": "https://openalex.org/W1", "doi": "http://192.168.1.1/evil"}]
    kept, dropped, replaced = verify_works(works)
    assert len(kept) == 1 and len(dropped) == 0
