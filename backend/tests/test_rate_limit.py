from app.core.rate_limit import clear_rate_limit
from app.core.settings import get_settings


def test_papers_rate_limit_429_and_exemptions(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "rate_limit_per_minute", 3)
    clear_rate_limit()

    for _ in range(3):
        r = client.get("/papers")
        assert r.status_code == 200

    r = client.get("/papers")
    assert r.status_code == 429
    assert r.headers.get("retry-after") is not None
    assert r.json() == {"detail": "Rate limit exceeded, retry shortly"}

    # health + metrics exempt after cap hit
    assert client.get("/health").status_code == 200
    assert client.get("/metrics").status_code == 200


def test_papers_rate_limit_unlimited_when_zero(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "rate_limit_per_minute", 0)
    clear_rate_limit()

    for _ in range(5):
        r = client.get("/papers")
        assert r.status_code == 200
