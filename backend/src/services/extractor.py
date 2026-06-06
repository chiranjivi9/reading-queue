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

import trafilatura


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
# Public API
# ---------------------------------------------------------------------------

async def extract_article(url: str) -> dict:
    """
    Fetch and extract clean article text from a URL.

    Args:
        url: The article URL to extract content from.

    Returns:
        dict with keys:
            "title" (str): The article title, or the URL if no title found.
            "text"  (str): The clean article body text.

    Raises:
        ExtractorError: If the page cannot be downloaded or no article
                        text can be extracted from it.

    Why asyncio.to_thread()?
        Trafilatura is a synchronous library — it blocks while downloading
        and parsing. Calling it directly in an async function would freeze
        the entire server during that time. asyncio.to_thread() runs it in
        a separate thread, keeping the event loop free to handle other requests.
    """
    try:
        result = await asyncio.to_thread(_fetch_and_extract, url)
        return result
    except ExtractorError:
        # re-raise our own exceptions unchanged
        raise
    except Exception as e:
        # wrap unexpected errors (network timeouts, parsing crashes, etc.)
        # so the caller always gets a clean ExtractorError
        raise ExtractorError(f"Unexpected error extracting {url}: {e}") from e
