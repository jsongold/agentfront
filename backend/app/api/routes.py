"""Operator API used by the Refine admin. Lists speak simple-rest."""

from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.adapters.registry import adapter_map
from app.config import get_settings, llm_key_status, uses_openai_compatible_base
from app.db import get_session
from app.diagnostics.service import diagnose_url
from app.domain.catalog import BusinessCatalog
from app.domain.completeness import compute_completeness, load_required_fields
from app.domain.validation import SchemaValidationError
from app.jobs import enqueue_generation
from app.models import (
    Business,
    Conversion,
    ConversionPoint,
    CrawlDocument,
    Delivery,
    DiagnosticReport,
    GenerationRun,
    McpCallLog,
    Offering,
    PageFetchLog,
    VerticalSchema,
    Work,
    utcnow,
)
from app.serialize import jsonable
from app.services.persistence import load_catalog, open_catalog
from app.services.review import latest_run, publish_business, save_review

def require_admin(request: Request) -> None:
    token = get_settings().admin_token
    if token and request.headers.get("x-admin-token") != token:
        raise HTTPException(status_code=401, detail="X-Admin-Token が一致しません")


router = APIRouter(prefix="/api", dependencies=[Depends(require_admin)])


def _uuid(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="ID の形式が正しくありません") from exc


def _page(start: int = 0, end: int = 20) -> tuple[int, int]:
    start = max(0, start)
    end = max(start, end)
    return start, min(end, start + 100)


def _listed(rows: list[dict[str, Any]], total: int) -> JSONResponse:
    return JSONResponse(
        content=jsonable(rows),
        headers={"X-Total-Count": str(total), "Access-Control-Expose-Headers": "X-Total-Count"},
    )


def _run_brief(run: GenerationRun | None) -> dict[str, Any] | None:
    if run is None:
        return None
    return {
        "id": run.id,
        "status": run.status,
        "step": run.step,
        "error": run.error,
        "model": run.model,
        "created_at": run.created_at,
        "finished_at": run.finished_at,
    }


def _business_dict(session: Session, row: Business) -> dict[str, Any]:
    base = get_settings().public_base_url.rstrip("/")
    run = latest_run(session, row.id)
    offerings = session.exec(select(Offering).where(Offering.business_id == row.id)).all()
    works = session.exec(select(Work).where(Work.business_id == row.id)).all()
    points = session.exec(select(ConversionPoint).where(ConversionPoint.business_id == row.id)).all()
    return {
        "id": row.id,
        "name": row.name,
        "slug": row.slug,
        "status": row.status,
        "summary": row.summary,
        "description": row.description,
        "service_area": row.service_area,
        "tags": row.tags,
        "vertical_key": row.vertical_key,
        "schema_org_type": row.schema_org_type,
        "seller": row.seller,
        "price_range": row.price_range,
        "trust": row.trust,
        "extension": row.extension,
        "completeness": row.completeness,
        "source_urls": row.source_urls,
        "source_description": row.source_description,
        "last_error": row.last_error,
        "offering_count": len(offerings),
        "work_count": len(works),
        "conversion_point_count": len(points),
        "public_url": f"{base}/b/{row.slug}" if row.status == "published" else None,
        "markdown_url": f"{base}/b/{row.slug}.md" if row.status == "published" else None,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
        "published_at": row.published_at,
        "latest_run": _run_brief(run),
    }


class BusinessCreate(BaseModel):
    name: str | None = None
    description: str = ""
    urls: list[str] = Field(default_factory=list)


class VerticalSchemaBody(BaseModel):
    key: str
    title: str = ""
    description: str = ""
    json_schema: dict[str, Any]


class ReviewBody(BaseModel):
    catalog: BusinessCatalog
    vertical_schema: VerticalSchemaBody | None = None


class AdapterBody(BaseModel):
    key: str
    config: dict[str, Any] = Field(default_factory=dict)


class DiagnosticBody(BaseModel):
    url: str


class PointBody(BaseModel):
    business_id: str | None = None
    key: str | None = None
    type: str = "inquiry"
    name: str
    description: str = ""
    input_schema: dict[str, Any] = Field(default_factory=dict)
    external_url: str | None = None
    enabled: bool = True
    adapters: list[AdapterBody] = Field(default_factory=list)


def _open_adapters(raw: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    from app.crypto import decrypt_json

    opened = []
    for item in raw or []:
        if item.get("config_encrypted"):
            try:
                config = decrypt_json(item["config_encrypted"])
            except Exception:  # noqa: BLE001
                config = {}
        else:
            config = item.get("config") or {}
        opened.append({"key": item.get("key"), "config": config})
    return opened


def _seal_adapters(bindings: list[AdapterBody]) -> list[dict[str, str]]:
    from app.crypto import encrypt_json

    return [{"key": item.key, "config_encrypted": encrypt_json(item.config)} for item in bindings]


@router.get("/meta")
def meta() -> dict[str, Any]:
    settings = get_settings()
    configured, env_name, hint = llm_key_status(settings)
    base = settings.public_base_url.rstrip("/")
    return {
        "public_base_url": base,
        "mcp_url": f"{base}/mcp",
        "llm_configured": configured,
        "llm_model": settings.llm_model,
        "llm_api_base": settings.llm_api_base if uses_openai_compatible_base(settings) else "",
        "llm_env": env_name,
        "llm_hint": hint,
        "mailpit_url": "http://localhost:8025",
    }


@router.get("/adapters")
def adapters() -> list[dict[str, Any]]:
    return [
        {"key": adapter.key, "title": adapter.title, "config_schema": adapter.config_schema()}
        for adapter in adapter_map().values()
    ]


@router.post("/diagnostics")
def run_diagnostic(body: DiagnosticBody, session: Session = Depends(get_session)) -> JSONResponse:
    try:
        report = diagnose_url(body.url)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    row = DiagnosticReport(
        url=str(report["url"]),
        score=int(report["score"]),
        grade=str(report["grade"]),
        report=report,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    data = dict(report)
    data["id"] = row.id
    data["created_at"] = row.created_at
    return JSONResponse(jsonable(data))


@router.get("/diagnostics")
def list_diagnostics(
    session: Session = Depends(get_session),
    _start: int = 0,
    _end: int = 20,
) -> JSONResponse:
    rows = list(session.exec(select(DiagnosticReport).order_by(DiagnosticReport.created_at.desc())).all())
    start, end = _page(_start, _end)
    items = [
        {
            "id": row.id,
            "url": row.url,
            "score": row.score,
            "grade": row.grade,
            "created_at": row.created_at,
        }
        for row in rows[start:end]
    ]
    return _listed(items, len(rows))


@router.get("/businesses")
def list_businesses(
    session: Session = Depends(get_session),
    _start: int = 0,
    _end: int = 20,
    _sort: str = "updated_at",
    _order: str = "desc",
) -> JSONResponse:
    start, end = _page(_start, _end)
    rows = list(session.exec(select(Business)).all())
    reverse = _order.lower() != "asc"
    key_name = _sort if _sort in {"name", "status", "updated_at", "created_at", "slug"} else "updated_at"
    rows.sort(key=lambda row: (getattr(row, key_name) is None, getattr(row, key_name) or ""), reverse=reverse)
    page = rows[start:end]
    return _listed([_business_dict(session, row) for row in page], len(rows))


@router.post("/businesses")
def create_business(body: BusinessCreate, session: Session = Depends(get_session)) -> JSONResponse:
    urls = [url.strip() for url in body.urls if url and url.strip()]
    for url in urls:
        if not url.startswith(("http://", "https://")):
            raise HTTPException(status_code=422, detail=f"URL は http(s) で始めてください: {url}")
    if not urls and len(body.description.strip()) < 10:
        raise HTTPException(status_code=422, detail="URL を入れるか、10文字以上の説明を書いてください")
    business = Business(
        slug=f"draft-{uuid.uuid4().hex[:8]}",
        name=(body.name or "（生成前）")[:300],
        summary="",
        description=body.description.strip(),
        source_description=body.description.strip(),
        source_urls=urls,
        status="queued",
        seller={"name": body.name or ""},
    )
    session.add(business)
    session.flush()
    session.add(
        GenerationRun(
            business_id=business.id,
            status="queued",
            step="queued",
            model=get_settings().llm_model,
        )
    )
    session.commit()
    session.refresh(business)
    try:
        enqueue_generation(str(business.id))
    except Exception as exc:  # noqa: BLE001
        business.status = "failed"
        business.last_error = f"ジョブを投入できませんでした: {exc}"
        session.commit()
    return JSONResponse(jsonable(_business_dict(session, business)), status_code=201)


@router.get("/businesses/{business_id}")
def get_business(business_id: str, session: Session = Depends(get_session)) -> JSONResponse:
    row = session.get(Business, _uuid(business_id))
    if row is None:
        raise HTTPException(status_code=404, detail="事業者が見つかりません")
    return JSONResponse(jsonable(_business_dict(session, row)))


@router.get("/businesses/{business_id}/completeness")
def get_completeness(business_id: str, session: Session = Depends(get_session)) -> JSONResponse:
    row = session.get(Business, _uuid(business_id))
    if row is None:
        raise HTTPException(status_code=404, detail="事業者が見つかりません")
    report = compute_completeness(load_catalog(session, row, include_adapter_config=False))
    row.completeness = report
    row.updated_at = utcnow()
    session.commit()
    return JSONResponse(jsonable(report))


@router.get("/required-fields")
def required_fields() -> JSONResponse:
    return JSONResponse(jsonable(load_required_fields()))


@router.delete("/businesses/{business_id}")
def delete_business(business_id: str, session: Session = Depends(get_session)) -> dict[str, str]:
    row = session.get(Business, _uuid(business_id))
    if row is None:
        raise HTTPException(status_code=404, detail="事業者が見つかりません")
    session.delete(row)
    session.commit()
    return {"id": business_id}


@router.post("/businesses/{business_id}/generate")
def generate_business(business_id: str, session: Session = Depends(get_session)) -> JSONResponse:
    row = session.get(Business, _uuid(business_id))
    if row is None:
        raise HTTPException(status_code=404, detail="事業者が見つかりません")
    run = latest_run(session, row.id)
    if run is not None and run.status in {"queued", "running"}:
        raise HTTPException(status_code=409, detail="すでに生成中です")
    session.add(GenerationRun(business_id=row.id, status="queued", step="queued", model=get_settings().llm_model))
    if row.status != "published":
        row.status = "queued"
    row.last_error = None
    row.updated_at = utcnow()
    session.commit()
    try:
        enqueue_generation(str(row.id))
    except Exception as exc:  # noqa: BLE001
        if row.status != "published":
            row.status = "failed"
        row.last_error = f"ジョブを投入できませんでした: {exc}"
        session.commit()
        raise HTTPException(status_code=503, detail=row.last_error) from exc
    session.refresh(row)
    return JSONResponse(jsonable(_business_dict(session, row)))


@router.get("/businesses/{business_id}/review")
def get_review(business_id: str, session: Session = Depends(get_session)) -> JSONResponse:
    row = session.get(Business, _uuid(business_id))
    if row is None:
        raise HTTPException(status_code=404, detail="事業者が見つかりません")
    run = latest_run(session, row.id)
    sources: list[dict[str, Any]] = []
    schema = None
    catalog = None
    if run is not None:
        docs = session.exec(select(CrawlDocument).where(CrawlDocument.generation_run_id == run.id)).all()
        sources = [
            {
                "url": doc.url,
                "ok": doc.ok,
                "title": doc.title,
                "text": doc.text,
                "metadata": doc.metadata_json,
                "error": doc.error,
            }
            for doc in docs
        ]
        if run.vertical_schema_id:
            schema_row = session.get(VerticalSchema, run.vertical_schema_id)
            if schema_row is not None:
                schema = {
                    "id": schema_row.id,
                    "key": schema_row.key,
                    "version": schema_row.version,
                    "title": schema_row.title,
                    "description": schema_row.description,
                    "json_schema": schema_row.json_schema,
                }
        if run.extracted:
            catalog = open_catalog(run.extracted).model_dump(mode="json")
    return JSONResponse(
        jsonable(
            {
                "business": _business_dict(session, row),
                "run": _run_brief(run),
                "sources": sources,
                "vertical_schema": schema,
                "catalog": catalog,
            }
        )
    )


@router.put("/businesses/{business_id}/review")
def put_review(business_id: str, body: ReviewBody, session: Session = Depends(get_session)) -> JSONResponse:
    row = session.get(Business, _uuid(business_id))
    if row is None:
        raise HTTPException(status_code=404, detail="事業者が見つかりません")
    schema = body.vertical_schema
    try:
        save_review(
            session,
            row,
            body.catalog,
            schema_key=schema.key if schema else None,
            schema_title=schema.title if schema else "",
            schema_description=schema.description if schema else "",
            schema_document=schema.json_schema if schema else None,
        )
    except SchemaValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors) from exc
    return get_review(business_id, session)


@router.post("/businesses/{business_id}/publish")
def publish(business_id: str, session: Session = Depends(get_session)) -> JSONResponse:
    row = session.get(Business, _uuid(business_id))
    if row is None:
        raise HTTPException(status_code=404, detail="事業者が見つかりません")
    try:
        publish_business(session, row)
    except SchemaValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors) from exc
    session.refresh(row)
    return JSONResponse(jsonable(_business_dict(session, row)))


def _point_dict(session: Session, row: ConversionPoint) -> dict[str, Any]:
    business = session.get(Business, row.business_id)
    return {
        "id": row.id,
        "business_id": row.business_id,
        "business_name": business.name if business else "",
        "business_slug": business.slug if business else "",
        "key": row.key,
        "type": row.type,
        "name": row.name,
        "description": row.description,
        "input_schema": row.input_schema,
        "external_url": row.external_url,
        "enabled": row.enabled,
        "adapters": _open_adapters(row.adapters),
    }


@router.get("/conversion-points")
def list_points(
    session: Session = Depends(get_session),
    _start: int = 0,
    _end: int = 50,
    business_id: str | None = None,
) -> JSONResponse:
    stmt = select(ConversionPoint)
    if business_id:
        stmt = stmt.where(ConversionPoint.business_id == _uuid(business_id))
    rows = list(session.exec(stmt).all())
    start, end = _page(_start, _end)
    page = rows[start:end]
    return _listed([_point_dict(session, row) for row in page], len(rows))


@router.get("/conversion-points/{point_id}")
def get_point(point_id: str, session: Session = Depends(get_session)) -> JSONResponse:
    row = session.get(ConversionPoint, _uuid(point_id))
    if row is None:
        raise HTTPException(status_code=404, detail="コンバージョン地点が見つかりません")
    return JSONResponse(jsonable(_point_dict(session, row)))


@router.patch("/conversion-points/{point_id}")
def patch_point(point_id: str, body: PointBody, session: Session = Depends(get_session)) -> JSONResponse:
    row = session.get(ConversionPoint, _uuid(point_id))
    if row is None:
        raise HTTPException(status_code=404, detail="コンバージョン地点が見つかりません")
    row.name = body.name
    row.type = body.type
    row.description = body.description
    row.external_url = body.external_url
    row.enabled = body.enabled
    if body.input_schema:
        from app.domain.validation import check_schema_document, tighten_schema

        schema = tighten_schema(dict(body.input_schema))
        try:
            check_schema_document(schema)
        except SchemaValidationError as exc:
            raise HTTPException(status_code=422, detail=exc.errors) from exc
        row.input_schema = schema
    if body.adapters:
        row.adapters = _seal_adapters(body.adapters)
    session.commit()
    session.refresh(row)
    return JSONResponse(jsonable(_point_dict(session, row)))


def _conversion_dict(session: Session, row: Conversion, *, with_deliveries: bool = False) -> dict[str, Any]:
    business = session.get(Business, row.business_id)
    point = session.get(ConversionPoint, row.conversion_point_id)
    data: dict[str, Any] = {
        "id": row.id,
        "business_id": row.business_id,
        "business_name": business.name if business else "",
        "conversion_point_id": row.conversion_point_id,
        "conversion_name": point.name if point else "",
        "conversion_type": point.type if point else "",
        "payload": row.payload,
        "agent_name": row.agent_name,
        "agent_class": row.agent_class,
        "request_text": row.request_text,
        "status": row.status,
        "created_at": row.created_at,
    }
    if with_deliveries:
        deliveries = session.exec(select(Delivery).where(Delivery.conversion_id == row.id)).all()
        data["deliveries"] = [
            {"id": item.id, "adapter_key": item.adapter_key, "status": item.status, "detail": item.detail, "created_at": item.created_at}
            for item in deliveries
        ]
    return data


@router.get("/conversions")
def list_conversions(session: Session = Depends(get_session), _start: int = 0, _end: int = 20) -> JSONResponse:
    rows = list(session.exec(select(Conversion).order_by(Conversion.created_at.desc())).all())
    start, end = _page(_start, _end)
    return _listed([_conversion_dict(session, row) for row in rows[start:end]], len(rows))


@router.get("/conversions/{conversion_id}")
def get_conversion(conversion_id: str, session: Session = Depends(get_session)) -> JSONResponse:
    row = session.get(Conversion, _uuid(conversion_id))
    if row is None:
        raise HTTPException(status_code=404, detail="コンバージョンが見つかりません")
    return JSONResponse(jsonable(_conversion_dict(session, row, with_deliveries=True)))


@router.get("/analytics/summary")
def analytics_summary(session: Session = Depends(get_session), days: int = Query(default=14, ge=1, le=90)) -> dict[str, Any]:
    since = utcnow() - timedelta(days=days)
    mcp_rows = session.exec(select(McpCallLog).where(McpCallLog.created_at >= since)).all()
    fetch_rows = session.exec(select(PageFetchLog).where(PageFetchLog.created_at >= since)).all()
    conversion_rows = session.exec(select(Conversion).where(Conversion.created_at >= since)).all()
    points = {row.id: row for row in session.exec(select(ConversionPoint)).all()}

    def bucket(items, key_fn):
        counts: dict[tuple[str, str], int] = {}
        for item in items:
            day = item.created_at.date().isoformat()
            label = key_fn(item)
            counts[(day, label)] = counts.get((day, label), 0) + 1
        return [{"day": day, "label": label, "count": count} for (day, label), count in sorted(counts.items())]

    published_count = len(session.exec(select(Business).where(Business.status == "published")).all())
    return {
        "days": days,
        "businesses_published": published_count,
        "totals": {
            "mcp_calls": len(mcp_rows),
            "page_fetches": len(fetch_rows),
            "conversions": len(conversion_rows),
        },
        "mcp_calls": bucket(mcp_rows, lambda row: row.tool_name),
        "page_fetches": bucket(fetch_rows, lambda row: row.agent_class),
        "conversions": bucket(conversion_rows, lambda row: points.get(row.conversion_point_id).type if points.get(row.conversion_point_id) else "unknown"),
        "recent_conversions": [
            _conversion_dict(session, row)
            for row in session.exec(select(Conversion).order_by(Conversion.created_at.desc()).limit(8)).all()
        ],
    }
