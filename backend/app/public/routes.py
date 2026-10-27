"""HTML, Markdown, feeds, robots, sitemap, fixtures, and conversion entry points."""

from __future__ import annotations

import mimetypes
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, Response
from sqlmodel import Session, select

from app.config import get_settings
from app.db import get_session
from app.domain.validation import SchemaValidationError
from app.models import Business, ConversionPoint
from app.render.pages import (
    render_business,
    render_feed,
    render_index,
    render_llms,
    render_markdown,
    render_offering,
    render_robots,
    render_sitemap,
    render_work,
    view_business,
)
from app.services.conversions import ConversionNotFound, submit_conversion
from app.services.persistence import load_catalog

router = APIRouter()
FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def _base() -> str:
    return get_settings().public_base_url.rstrip("/")


def _split_md(value: str) -> tuple[str, bool]:
    if value.endswith(".md"):
        return value[: -3], True
    return value, False


def _cards(session: Session) -> tuple[list, list[dict]]:
    rows = session.exec(select(Business).where(Business.status == "published").order_by(Business.name)).all()
    catalogs = []
    cards = []
    base = _base()
    for row in rows:
        catalog = load_catalog(session, row, include_adapter_config=False)
        catalogs.append(catalog)
        view = view_business(catalog, base)
        cards.append(
            {
                "name": catalog.name,
                "summary": catalog.summary,
                "service_area": list(catalog.service_area),
                "tags": list(catalog.tags),
                "html_url": view["html_url"],
                "md_url": view["md_url"],
                "slug": catalog.slug,
            }
        )
    return catalogs, cards


def _one(session: Session, slug: str) -> tuple[Business, object]:
    row = session.exec(select(Business).where(Business.slug == slug, Business.status == "published")).first()
    if row is None:
        raise HTTPException(status_code=404, detail="事業者が見つかりません")
    return row, load_catalog(session, row, include_adapter_config=False)


@router.get("/", response_class=HTMLResponse)
def index(session: Session = Depends(get_session)) -> HTMLResponse:
    _catalogs, cards = _cards(session)
    return HTMLResponse(render_index(cards, _base()))


@router.get("/llms.txt", response_class=PlainTextResponse)
def llms_txt(session: Session = Depends(get_session)) -> PlainTextResponse:
    _catalogs, cards = _cards(session)
    return PlainTextResponse(render_llms(cards, _base()), media_type="text/plain; charset=utf-8")


@router.get("/robots.txt", response_class=PlainTextResponse)
def robots() -> PlainTextResponse:
    return PlainTextResponse(render_robots(_base()), media_type="text/plain; charset=utf-8")


@router.get("/sitemap.xml")
def sitemap(session: Session = Depends(get_session)) -> Response:
    catalogs, _ignored = _cards(session)
    base = _base()
    urls = [base + "/", base + "/llms.txt", base + "/feed.json"]
    for catalog in catalogs:
        urls.append(f"{base}/b/{catalog.slug}")
        urls.append(f"{base}/b/{catalog.slug}.md")
        for offering in catalog.offerings:
            urls.append(f"{base}/b/{catalog.slug}/o/{offering.slug}")
        for work in catalog.works:
            urls.append(f"{base}/b/{catalog.slug}/w/{work.slug}")
    return Response(render_sitemap(urls), media_type="application/xml")


@router.get("/feed.json")
def feed(session: Session = Depends(get_session)) -> JSONResponse:
    catalogs, _ignored = _cards(session)
    return JSONResponse(render_feed(catalogs, _base()))


@router.get("/b/{slug}/feed.json")
def business_feed(slug: str, session: Session = Depends(get_session)) -> JSONResponse:
    _row, catalog = _one(session, slug)
    return JSONResponse(render_feed([catalog], _base()))


@router.get("/b/{slug}/o/{offering_slug}")
def offering_page(slug: str, offering_slug: str, session: Session = Depends(get_session)):
    offering_slug, as_md = _split_md(offering_slug)
    _row, catalog = _one(session, slug)
    if as_md:
        body = render_markdown(catalog, _base(), offering_slug=offering_slug)
        if body is None:
            raise HTTPException(status_code=404, detail="提供内容が見つかりません")
        return PlainTextResponse(body, media_type="text/markdown; charset=utf-8")
    body = render_offering(catalog, offering_slug, _base())
    if body is None:
        raise HTTPException(status_code=404, detail="提供内容が見つかりません")
    return HTMLResponse(body)


@router.get("/b/{slug}/w/{work_slug}")
def work_page(slug: str, work_slug: str, session: Session = Depends(get_session)):
    work_slug, as_md = _split_md(work_slug)
    _row, catalog = _one(session, slug)
    if as_md:
        body = render_markdown(catalog, _base(), work_slug=work_slug)
        if body is None:
            raise HTTPException(status_code=404, detail="実績が見つかりません")
        return PlainTextResponse(body, media_type="text/markdown; charset=utf-8")
    body = render_work(catalog, work_slug, _base())
    if body is None:
        raise HTTPException(status_code=404, detail="実績が見つかりません")
    return HTMLResponse(body)


@router.get("/b/{slug}/convert/{key}")
def conversion_schema(slug: str, key: str, session: Session = Depends(get_session)) -> JSONResponse:
    row, _catalog = _one(session, slug)
    point = session.exec(
        select(ConversionPoint).where(
            ConversionPoint.business_id == row.id,
            ConversionPoint.key == key,
            ConversionPoint.enabled == True,  # noqa: E712
        )
    ).first()
    if point is None:
        raise HTTPException(status_code=404, detail="コンバージョン地点が見つかりません")
    return JSONResponse(
        {
            "id": str(point.id),
            "business_slug": row.slug,
            "key": point.key,
            "type": point.type,
            "name": point.name,
            "description": point.description,
            "input_schema": point.input_schema,
            "external_url": point.external_url,
            "submit": {"method": "POST", "url": f"{_base()}/b/{row.slug}/convert/{point.key}"},
        }
    )


@router.post("/b/{slug}/convert/{key}")
async def conversion_submit(slug: str, key: str, request: Request, session: Session = Depends(get_session)) -> JSONResponse:
    row, _catalog = _one(session, slug)
    point = session.exec(
        select(ConversionPoint).where(
            ConversionPoint.business_id == row.id,
            ConversionPoint.key == key,
            ConversionPoint.enabled == True,  # noqa: E712
        )
    ).first()
    if point is None:
        raise HTTPException(status_code=404, detail="コンバージョン地点が見つかりません")
    try:
        payload = await request.json()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail="JSON ボディが必要です") from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="payload はオブジェクトである必要があります")
    body = payload.get("payload") if isinstance(payload.get("payload"), dict) else payload
    try:
        conversion = submit_conversion(
            session,
            conversion_point_id=point.id,
            payload=body,
            agent_name=str(payload.get("agent_name") or ""),
            request_text=str(payload.get("request_text") or ""),
            user_agent=request.headers.get("user-agent", ""),
        )
    except SchemaValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors) from exc
    except ConversionNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return JSONResponse({"conversion_id": str(conversion.id), "status": conversion.status})


@router.get("/b/{slug}")
def business_page(slug: str, session: Session = Depends(get_session)):
    slug, as_md = _split_md(slug)
    _row, catalog = _one(session, slug)
    if as_md:
        body = render_markdown(catalog, _base())
        return PlainTextResponse(body or "", media_type="text/markdown; charset=utf-8")
    html = render_business(catalog, _base())
    return HTMLResponse(html, headers={"Link": f'<{_base()}/b/{slug}.md>; rel="alternate"; type="text/markdown"'})


@router.get("/fixtures/{name}")
def fixture_page(name: str) -> HTMLResponse:
    if name not in {"aoba", "kogaku"}:
        raise HTTPException(status_code=404, detail="fixture not found")
    return HTMLResponse((FIXTURES / f"{name}.html").read_text(encoding="utf-8"))


@router.get("/fixtures/assets/{filename}")
def fixture_asset(filename: str) -> Response:
    path = (FIXTURES / "assets" / filename).resolve()
    if not str(path).startswith(str((FIXTURES / "assets").resolve())) or not path.is_file():
        raise HTTPException(status_code=404, detail="asset not found")
    media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return Response(path.read_bytes(), media_type=media_type)


@router.get("/media/{object_name:path}")
def media(object_name: str) -> Response:
    if ".." in object_name or object_name.startswith("/"):
        raise HTTPException(status_code=400, detail="invalid media key")
    settings = get_settings()
    try:
        from minio import Minio
        from minio.error import S3Error

        client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )
        obj = client.get_object(settings.minio_bucket, object_name)
        try:
            data = obj.read()
        finally:
            obj.close()
            obj.release_conn()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=404, detail="media not found") from exc
    media_type = mimetypes.guess_type(object_name)[0] or "application/octet-stream"
    return Response(data, media_type=media_type)
