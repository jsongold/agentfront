"""URL ingestion: Crawl4AI when available, otherwise httpx + trafilatura + extruct."""

from __future__ import annotations

import io
import logging
import mimetypes
import uuid
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
import pluggy
from lxml import html as lhtml
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import get_settings
from app.crawl.crawl4ai_backend import fetch_markdown
from app.domain.catalog import Media

logger = logging.getLogger(__name__)
hookimpl = pluggy.HookimplMarker("agentfront")

USER_AGENT = "agentfront/0.1 (+https://localhost/llms.txt)"
MAX_IMAGES = 6
MAX_IMAGE_BYTES = 2_000_000


@dataclass
class CrawlResult:
    url: str
    ok: bool
    title: str = ""
    text: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    images: list[Media] = field(default_factory=list)
    error: str | None = None


def rewrite_for_fetch(url: str) -> str:
    """Let the worker reach fixture pages published on the host-facing base URL."""
    settings = get_settings()
    public = settings.public_base_url.rstrip("/")
    internal = settings.internal_base_url.rstrip("/")
    if public != internal and url.startswith(public):
        return internal + url[len(public) :]
    return url


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=0.4, min=0.4, max=4), reraise=True)
def _http_get(url: str) -> httpx.Response:
    with httpx.Client(timeout=20, follow_redirects=True, headers={"User-Agent": USER_AGENT}) as client:
        response = client.get(url)
        response.raise_for_status()
        return response


def parse_document(url: str, body: bytes, content_type: str = "") -> CrawlResult:
    """Turn fetched bytes into text, JSON-LD/OGP metadata, and image URLs."""
    html = body.decode("utf-8", errors="replace")
    title = ""
    text = ""
    metadata: dict[str, Any] = {}
    try:
        import trafilatura

        extracted = trafilatura.extract(html, url=url, include_comments=False, include_tables=True) or ""
        text = extracted
        meta = trafilatura.extract_metadata(html)
        if meta is not None:
            title = meta.title or ""
    except Exception as exc:  # noqa: BLE001
        logger.info("trafilatura failed for %s: %s", url, exc)
    try:
        import extruct

        metadata = extruct.extract(
            html,
            base_url=url,
            syntaxes=["json-ld", "opengraph", "microdata"],
            uniform=False,
        )
        if not title:
            og = metadata.get("opengraph") or []
            if og and isinstance(og, list):
                title = str((og[0] or {}).get("properties", {}).get("og:title") or (og[0] or {}).get("title") or "")
    except Exception as exc:  # noqa: BLE001
        logger.info("extruct failed for %s: %s", url, exc)
        metadata = {}
    images = _image_urls(url, html)
    if not text and not title:
        return CrawlResult(url=url, ok=False, metadata=metadata, images=images, error="no text extracted")
    return CrawlResult(url=url, ok=True, title=title, text=text, metadata=_shrink(metadata), images=images)


def _shrink(metadata: dict[str, Any]) -> dict[str, Any]:
    """Keep structured metadata small enough to store and to show an operator."""
    import json

    raw = json.dumps(metadata, ensure_ascii=False, default=str)
    if len(raw) <= 20_000:
        return metadata
    return {"truncated": True, "preview": raw[:20_000]}


def _image_urls(page_url: str, html: str) -> list[Media]:
    try:
        document = lhtml.fromstring(html)
    except Exception:  # noqa: BLE001
        return []
    found: list[Media] = []
    seen: set[str] = set()
    for src in document.xpath("//img/@src"):
        if not isinstance(src, str):
            continue
        absolute = urljoin(page_url, src.strip())
        if absolute in seen or absolute.startswith("data:"):
            continue
        seen.add(absolute)
        alt = ""
        found.append(Media(url=absolute, alt=alt or None))
        if len(found) >= MAX_IMAGES:
            break
    return found


def _store_images(images: list[Media]) -> list[Media]:
    settings = get_settings()
    if not images:
        return []
    try:
        from minio import Minio
    except Exception:  # noqa: BLE001
        return images
    client = Minio(
        settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=settings.minio_secure,
    )
    stored: list[Media] = []
    for image in images:
        try:
            response = _http_get(rewrite_for_fetch(image.url))
        except Exception:  # noqa: BLE001
            continue
        content_type = response.headers.get("content-type", "").split(";")[0].strip().lower()
        if not content_type.startswith("image/"):
            continue
        data = response.content
        if not data or len(data) > MAX_IMAGE_BYTES:
            continue
        ext = mimetypes.guess_extension(content_type) or ".bin"
        if ext == ".jpe":
            ext = ".jpg"
        key = f"images/{uuid.uuid4().hex}{ext}"
        try:
            client.put_object(
                settings.minio_bucket,
                key,
                io.BytesIO(data),
                length=len(data),
                content_type=content_type,
            )
        except Exception as exc:  # noqa: BLE001
            logger.info("minio put failed: %s", exc)
            continue
        public = settings.public_base_url.rstrip("/")
        stored.append(Media(url=f"{public}/media/{key}", alt=image.alt, kind="image"))
    return stored


class UrlCrawlSource:
    key = "url_crawl"

    def fetch(self, url: str) -> CrawlResult:
        settings = get_settings()
        target = rewrite_for_fetch(url)
        if settings.crawl_backend in ("auto", "crawl4ai"):
            rich = fetch_markdown(target)
            if rich is not None:
                html = rich.get("html") or ""
                text = rich.get("markdown") or ""
                if html:
                    parsed = parse_document(url, html.encode("utf-8"))
                    if text and len(text) > len(parsed.text):
                        parsed.text = text
                    if rich.get("title"):
                        parsed.title = rich["title"]
                    parsed.images = _store_images(parsed.images)
                    parsed.ok = bool(parsed.text)
                    return parsed
                if text:
                    return CrawlResult(url=url, ok=True, title=rich.get("title") or "", text=text)
            if settings.crawl_backend == "crawl4ai":
                return CrawlResult(url=url, ok=False, error="Crawl4AI is not available or failed")
        try:
            response = _http_get(target)
        except Exception as exc:  # noqa: BLE001
            return CrawlResult(url=url, ok=False, error=str(exc))
        parsed = parse_document(url, response.content, response.headers.get("content-type", ""))
        parsed.images = _store_images(parsed.images)
        return parsed


class UrlCrawlPlugin:
    @hookimpl
    def catalog_ingestion(self) -> UrlCrawlSource:
        return UrlCrawlSource()


def plugin() -> UrlCrawlPlugin:
    return UrlCrawlPlugin()


def fetch_url(url: str) -> CrawlResult:
    from app.adapters.registry import ingestion_map

    source = ingestion_map().get("url_crawl")
    if source is None:
        return UrlCrawlSource().fetch(url)
    return source.fetch(url)
