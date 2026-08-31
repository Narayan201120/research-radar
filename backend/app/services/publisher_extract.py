"""Publisher HTML fallback for abstract recovery.

Tries doi.org redirect HTML and extracts abstract from meta tags or
publisher sections (Springer, Elsevier). Polite and bounded.
"""

from __future__ import annotations

import re
import time

import httpx

HTML_TIMEOUT = 12.0
USER_AGENT = "research-radar-abstract-recovery/0.1 (mailto:research-radar@example.com)"


def _get_with_backoff(client: httpx.Client, url: str, *, timeout: float) -> httpx.Response | None:
    for attempt in range(3):
        try:
            resp = client.get(url, timeout=timeout)
            if resp.status_code == 429:
                time.sleep(1.5 ** attempt)
                continue
            return resp
        except httpx.HTTPError:
            time.sleep(0.5)
            continue
    return None

_WS_RE = re.compile(r"\s+")


def _clean(text: str) -> str:
    return _WS_RE.sub(" ", text).strip()


def _extract_meta(soup) -> str | None:  # type: ignore[no-untyped-def]
    # Highwire Press meta used by Springer, Elsevier, many publishers
    for name in ("citation_abstract", "dc.Description", "dc.description"):
        tag = soup.find("meta", attrs={"name": name})
        if tag and tag.get("content"):
            c = _clean(tag["content"])
            if len(c) >= 50:
                return c
    for prop in ("og:description",):
        tag = soup.find("meta", attrs={"property": prop})
        if tag and tag.get("content"):
            c = _clean(tag["content"])
            if len(c) >= 50:
                return c
    # generic description only if long enough to be abstract-like
    tag = soup.find("meta", attrs={"name": "description"})
    if tag and tag.get("content"):
        c = _clean(tag["content"])
        if len(c) >= 100:
            return c
    return None


def _extract_sections(soup) -> str | None:  # type: ignore[no-untyped-def]
    # Springer
    for sel in ["#Abs1-content", "#Abs1-section", "section#Abs1", "div#Abs1-section"]:
        el = soup.select_one(sel)
        if el:
            t = _clean(el.get_text(" ", strip=True))
            if len(t) >= 50:
                return t
    # Elsevier
    for sel in ["div.abstract.author", "section#abstract", "div#abstracts", "div.abstract"]:
        el = soup.select_one(sel)
        if el:
            # Elsevier often has multiple <p> inside
            t = _clean(el.get_text(" ", strip=True))
            if len(t) >= 50:
                return t
    # Generic
    for sel in ["section.abstract", "article section.abstract"]:
        el = soup.select_one(sel)
        if el:
            t = _clean(el.get_text(" ", strip=True))
            if len(t) >= 80:
                return t
    return None


def fetch_html_abstract(
    doi: str,
    locations: list[dict] | None = None,
    *,
    transport: httpx.BaseTransport | None = None,
) -> str | None:
    doi = (doi or "").strip()
    if not doi:
        return None
    bare = doi.removeprefix("https://doi.org/").removeprefix("http://doi.org/").strip()
    # doi.org will redirect to publisher landing page
    url = f"https://doi.org/{bare}"
    headers = {"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"}
    with httpx.Client(headers=headers, follow_redirects=True, transport=transport) as client:
        resp = _get_with_backoff(client, url, timeout=HTML_TIMEOUT)
        if resp is None or resp.status_code != 200:
            return None
        # only parse HTML
        ctype = resp.headers.get("content-type", "")
        if ctype and "html" not in ctype.lower() and "xml" not in ctype.lower():
            # Some publishers return pdf content-type — skip
            # but allow if no ctype or text
            if "text" not in ctype.lower():
                pass  # still try to parse as HTML, many servers omit ctype
        try:
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(resp.text, "lxml")
        except Exception:
            try:
                from bs4 import BeautifulSoup

                soup = BeautifulSoup(resp.text, "html.parser")
            except Exception:
                return None
        # try meta first (most stable)
        meta = _extract_meta(soup)
        if meta:
            return meta
        sec = _extract_sections(soup)
        if sec:
            return sec
        return None


def source_for_doi(doi: str) -> str:
    d = (doi or "").lower()
    if "10.1007" in d:
        return "springer"
    if "10.1016" in d:
        return "elsevier"
    return "html_generic"
