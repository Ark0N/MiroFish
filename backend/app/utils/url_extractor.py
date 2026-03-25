"""
URL content extractor.

Fetches web pages and extracts clean text content using trafilatura.
Supports news articles, blog posts, and general web pages.
"""

import trafilatura
from typing import Optional, Dict, Any

from .logger import get_logger

logger = get_logger('mirofish.url_extractor')


def extract_text_from_url(url: str, timeout: int = 30) -> Dict[str, Any]:
    """Fetch a URL and extract clean text content.

    Args:
        url: The URL to fetch and extract text from
        timeout: Request timeout in seconds

    Returns:
        Dict with keys:
            - text: Extracted text content (empty string on failure)
            - title: Page title if available
            - url: The original URL
            - success: Whether extraction succeeded
            - error: Error message if failed
    """
    result = {
        "text": "",
        "title": "",
        "url": url,
        "success": False,
        "error": None,
    }

    try:
        # Download the page
        downloaded = trafilatura.fetch_url(url)
        if not downloaded:
            result["error"] = f"Failed to fetch URL: {url}"
            logger.warning(result["error"])
            return result

        # Extract text content
        text = trafilatura.extract(
            downloaded,
            include_comments=False,
            include_tables=True,
            no_fallback=False,
        )

        if not text or len(text.strip()) < 50:
            result["error"] = "Extracted text too short or empty"
            logger.warning(f"Insufficient text from {url}: {len(text) if text else 0} chars")
            return result

        # Extract metadata for title
        metadata = trafilatura.extract_metadata(downloaded)
        if metadata and metadata.title:
            result["title"] = metadata.title

        result["text"] = text.strip()
        result["success"] = True
        logger.info(f"Extracted {len(result['text'])} chars from {url}")

    except Exception as e:
        result["error"] = str(e)
        logger.error(f"URL extraction failed for {url}: {e}")

    return result


def extract_text_from_urls(urls: list, timeout: int = 30) -> list:
    """Extract text from multiple URLs.

    Args:
        urls: List of URLs to process
        timeout: Per-request timeout

    Returns:
        List of extraction result dicts
    """
    results = []
    for url in urls:
        results.append(extract_text_from_url(url, timeout=timeout))
    return results
