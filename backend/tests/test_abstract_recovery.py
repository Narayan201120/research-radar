import httpx

from app.models import Paper
from app.services.abstract_recovery import (
    fetch_arxiv_abstract,
    fetch_crossref_abstract,
    recover_missing_abstracts,
)
from app.services.embeddings import HashingFakeProvider
from tests.helpers import add_paper


def test_fetch_crossref_strips_jats():
    def handler(request):
        assert "api.crossref.org" in str(request.url)
        return httpx.Response(
            200,
            json={"message": {"abstract": "<jats:p>We study <i>attention</i> mechanisms.</jats:p>"}},
        )

    transport = httpx.MockTransport(handler)
    abstract = fetch_crossref_abstract("https://doi.org/10.1234/test", transport=transport)
    assert abstract == "We study attention mechanisms."


def test_fetch_crossref_misses_on_48550():
    abstract = fetch_crossref_abstract("https://doi.org/10.48550/arXiv.2301.00001")
    assert abstract is None


def test_fetch_arxiv_parses_atom():
    atom = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"><entry><summary>ArXiv abstract about transformers.</summary></entry></feed>"""

    def handler(request):
        assert "export.arxiv.org" in str(request.url)
        return httpx.Response(200, text=atom)

    transport = httpx.MockTransport(handler)
    abstract = fetch_arxiv_abstract("https://doi.org/10.48550/arXiv.2301.00001", transport=transport)
    assert abstract == "ArXiv abstract about transformers."


def test_recover_missing_abstracts_waterfall(session):
    p1 = add_paper(session, "Paper One", abstract=None, doi="https://doi.org/10.1234/crossref")
    p2 = add_paper(session, "Paper Two", abstract=None, doi="https://doi.org/10.48550/arXiv.2301.00001")
    p3 = add_paper(session, "Paper Three", abstract="already has abstract", doi="https://doi.org/10.1234/keep")
    session.commit()

    def handler(request):
        url = str(request.url)
        if "api.crossref.org" in url and "10.1234/crossref" in url:
            return httpx.Response(200, json={"message": {"abstract": "<jats:p>Crossref abstract.</jats:p>"}})
        if "api.crossref.org" in url:
            return httpx.Response(200, json={"message": {}})
        if "export.arxiv.org" in url:
            atom = """<?xml version="1.0" encoding="UTF-8"?><feed xmlns="http://www.w3.org/2005/Atom"><entry><summary>Arxiv fallback abstract.</summary></entry></feed>"""
            return httpx.Response(200, text=atom)
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    recovered = recover_missing_abstracts(
        session, limit=10, transport=transport, embedding_provider=HashingFakeProvider(dim=8)
    )
    session.commit()

    assert recovered == 2
    session.refresh(p1)
    session.refresh(p2)
    assert p1.abstract == "Crossref abstract."
    assert p1.abstract_source == "crossref"
    assert p1.abstract_recovered_at is not None
    assert p2.abstract == "Arxiv fallback abstract."
    assert p2.abstract_source == "arxiv"
    assert p3.abstract == "already has abstract"
