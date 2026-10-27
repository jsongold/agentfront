"""Optional Crawl4AI fetch. Returns None when the extra is not installed."""

from __future__ import annotations

import asyncio
from typing import Any


def fetch_markdown(url: str) -> dict[str, Any] | None:
    """Best-effort Crawl4AI fetch.

    The default image uses httpx + trafilatura. Install the `crawl4ai` extra
    and set CRAWL_BACKEND=crawl4ai (or leave auto) to prefer a browser crawl.
    """
    try:
        from crawl4ai import AsyncWebCrawler
    except Exception:  # noqa: BLE001
        return None

    async def _run() -> Any:
        async with AsyncWebCrawler() as crawler:
            return await crawler.arun(url=url)

    try:
        result = asyncio.run(_run())
    except Exception:  # noqa: BLE001
        return None
    markdown = getattr(result, "markdown", None) or ""
    if hasattr(markdown, "raw_markdown"):
        markdown = markdown.raw_markdown
    html = getattr(result, "html", None) or getattr(result, "cleaned_html", None) or ""
    title = ""
    metadata = getattr(result, "metadata", None) or {}
    if isinstance(metadata, dict):
        title = str(metadata.get("title") or "")
    if not markdown and not html:
        return None
    return {"title": title, "markdown": str(markdown or ""), "html": str(html or ""), "metadata": metadata}
