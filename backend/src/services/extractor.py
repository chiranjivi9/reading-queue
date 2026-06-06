"""
services/extractor.py — Article content extraction.

Uses Trafilatura to fetch a URL and extract the clean article text,
stripping ads, navigation, and other noise from the page.

Public API:
    extract_article(url: str) -> dict
        Returns { "title": str, "text": str }
        Raises ExtractorError if the article cannot be extracted.
"""

import asyncio

import httpx
import trafilatura

JINA_BASE = "https://r.jina.ai/"


# ---------------------------------------------------------------------------
# Custom exception
# ---------------------------------------------------------------------------

class ExtractorError(Exception):
    """
    Raised when article extraction fails for any reason.

    Using a custom exception (rather than a generic Exception) lets the
    caller in main.py catch *only* extraction failures specifically,
    without accidentally swallowing unrelated bugs.

    Example:
        try:
            result = await extract_article(url)
        except ExtractorError as e:
            # handle extraction failure
        # other exceptions bubble up normally
    """
    pass


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _fetch_and_extract(url: str) -> dict:
    """
    Synchronous helper that does the actual Trafilatura work.

    Trafilatura's functions are synchronous (blocking), so this runs in
    a thread via asyncio.to_thread() — see extract_article() below.

    Returns { "title": str, "text": str }
    Raises ExtractorError on any failure.
    """
    # fetch_url downloads the raw HTML with a built-in timeout
    downloaded = trafilatura.fetch_url(url)

    if downloaded is None:
        raise ExtractorError(f"Could not download content from: {url}")

    # extract() strips boilerplate (ads, nav, footers) and returns clean text
    text = trafilatura.extract(
        downloaded,
        include_comments=False,
        include_tables=False,
        favor_precision=True,  # prefer accuracy over recall — less noise
    )

    if text is None:
        raise ExtractorError(f"Could not extract article text from: {url}")

    # extract metadata separately to get the title
    metadata = trafilatura.extract_metadata(downloaded)
    title = metadata.title if metadata and metadata.title else url

    return {"title": title, "text": text}


# ---------------------------------------------------------------------------
# Jina Reader fallback
# ---------------------------------------------------------------------------

async def _extract_via_jina(url: str) -> dict:
    """
    Fallback extractor using Jina Reader (r.jina.ai).

    Jina fetches and renders the page server-side, bypassing bot detection
    used by sites like Medium. Returns plain text with a title header.
    Free tier, no API key required.
    """
    jina_url = JINA_BASE + url
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        resp = await client.get(jina_url, headers={"Accept": "text/plain"})
    if resp.status_code != 200:
        raise ExtractorError(f"Jina Reader failed ({resp.status_code}) for: {url}")

    text = resp.text.strip()
    if not text:
        raise ExtractorError(f"Jina Reader returned empty content for: {url}")

    # Jina returns "Title: <title>\n..." as the first line
    lines = text.splitlines()
    title = url
    for line in lines[:5]:
        if line.startswith("Title:"):
            title = line.removeprefix("Title:").strip()
            break

    return {"title": title, "text": text}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def extract_article(url: str) -> dict:
    """
    Fetch and extract clean article text from a URL.

    Tries Trafilatura first (fast, local). If it fails — e.g. the site
    blocks server-side requests (Medium, etc.) — falls back to Jina Reader,
    which renders the page remotely and returns plain text.
    """
    try:
        return await asyncio.to_thread(_fetch_and_extract, url)
    except ExtractorError:
        pass  # fall through to Jina
    except Exception:
        pass

    # Jina fallback
    try:
        return await _extract_via_jina(url)
    except ExtractorError:
        raise
    except Exception as e:
        raise ExtractorError(f"Unexpected error extracting {url}: {e}") from e
