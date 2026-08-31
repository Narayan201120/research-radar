import httpx

from app.models import Paper
from app.services.abstract_recovery import (
    fetch_arxiv_abstract,
    fetch_crossref_abstract,
    recover_abstract_for_paper,
    recover_missing_abstracts,
)
from app.services.embeddings import HashingFakeProvider
from app.services.publisher_extract import fetch_html_abstract, source_for_doi
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


def test_fetch_html_springer_meta():
    html = '<html><head><meta name="citation_abstract" content="Springer abstract here. This is long enough to pass fifty characters threshold for testing."></head></html>'

    def handler(request):
        assert "doi.org" in str(request.url)
        return httpx.Response(200, text=html, headers={"content-type": "text/html"})

    transport = httpx.MockTransport(handler)
    abstract = fetch_html_abstract("https://doi.org/10.1007/test", transport=transport)
    assert abstract == "Springer abstract here. This is long enough to pass fifty characters threshold for testing."


def test_fetch_html_elsevier_section():
    html = '<html><body><div class="abstract author"><p>Elsevier abstract section with enough length to be considered valid abstract for testing purposes here.</p></div></body></html>'

    def handler(request):
        return httpx.Response(200, text=html, headers={"content-type": "text/html"})

    transport = httpx.MockTransport(handler)
    abstract = fetch_html_abstract("https://doi.org/10.1016/test", transport=transport)
    assert abstract is not None
    assert "Elsevier abstract" in abstract


def test_fetch_html_generic_fallback():
    html = '<html><body><section class="abstract"><p>Generic abstract fallback that is long enough to pass the eighty character threshold for generic selector.</p></section></body></html>'

    def handler(request):
        return httpx.Response(200, text=html, headers={"content-type": "text/html"})

    transport = httpx.MockTransport(handler)
    abstract = fetch_html_abstract("https://doi.org/10.1234/generic", transport=transport)
    assert abstract is not None
    assert "Generic abstract" in abstract


def test_recover_waterfall_prefers_crossref_over_html(session):
    p = add_paper(session, "Pref", abstract=None, doi="https://doi.org/10.1234/pref")
    session.commit()

    def handler(request):
        url = str(request.url)
        if "api.crossref.org" in url:
            return httpx.Response(200, json={"message": {"abstract": "<jats:p>Crossref wins.</jats:p>"}})
        if "doi.org" in url:
            html = '<html><head><meta name="citation_abstract" content="HTML should not be used when Crossref succeeds and is long enough."></head></html>'
            return httpx.Response(200, text=html, headers={"content-type": "text/html"})
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    abstract, source = recover_abstract_for_paper(p, transport=transport)
    assert abstract == "Crossref wins."
    assert source == "crossref"


def test_recover_html_source_tagged(session):
    p1 = add_paper(session, "Springer Paper", abstract=None, doi="https://doi.org/10.1007/s12345-024-00001-1")
    p2 = add_paper(session, "Elsevier Paper", abstract=None, doi="https://doi.org/10.1016/j.test.2024.01.001")
    p3 = add_paper(session, "Generic Paper", abstract=None, doi="https://doi.org/10.9999/generic")
    session.commit()

    def handler(request):
        url = str(request.url)
        if "api.crossref.org" in url:
            return httpx.Response(200, json={"message": {}})
        if "export.arxiv.org" in url:
            return httpx.Response(404)
        if "doi.org" in url:
            if "10.1007" in url:
                html = '<html><head><meta name="citation_abstract" content="Springer HTML abstract recovered for testing that is definitely longer than fifty characters."></head></html>'
                return httpx.Response(200, text=html, headers={"content-type": "text/html"})
            if "10.1016" in url:
                html = '<html><body><div class="abstract author"><p>Elsevier HTML abstract recovered for testing that is definitely longer than fifty characters.</p></div></body></html>'
                return httpx.Response(200, text=html, headers={"content-type": "text/html"})
            html = '<html><body><section class="abstract"><p>Generic HTML abstract recovered that is long enough to pass the eighty character threshold for generic selector test.</p></section></body></html>'
            return httpx.Response(200, text=html, headers={"content-type": "text/html"})
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    recovered = recover_missing_abstracts(session, limit=10, transport=transport, embedding_provider=HashingFakeProvider(dim=8))
    session.commit()
    assert recovered == 3
    session.refresh(p1)
    session.refresh(p2)
    session.refresh(p3)
    assert p1.abstract_source == "springer"
    assert p2.abstract_source == "elsevier"
    assert p3.abstract_source == "html_generic"
    assert source_for_doi("10.1007/test") == "springer"
    assert source_for_doi("10.1016/test") == "elsevier"
    assert source_for_doi("10.9999/test") == "html_generic"
