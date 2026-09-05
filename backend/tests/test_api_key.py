from app.core.settings import get_settings
from tests.helpers import add_paper


def test_papers_open_by_default(client):
    assert get_settings().api_key == ""
    response = client.get("/papers")
    assert response.status_code == 200


def test_papers_require_key_when_configured(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "api_key", "secret")

    response = client.get("/papers")
    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid or missing API key"}

    response = client.get("/papers", headers={"X-API-Key": "wrong"})
    assert response.status_code == 401

    response = client.get("/papers", headers={"X-API-Key": "secret"})
    assert response.status_code == 200


def test_detail_requires_key_before_handler(client, session, monkeypatch):
    paper = add_paper(session, "Keyed Paper")
    session.commit()
    monkeypatch.setattr(get_settings(), "api_key", "secret")

    response = client.get(f"/papers/{paper.id}")
    assert response.status_code == 401

    response = client.get(f"/papers/{paper.id}", headers={"X-API-Key": "secret"})
    assert response.status_code == 200


def test_health_stays_public_when_key_set(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "api_key", "secret")

    response = client.get("/health")
    assert response.status_code == 200
