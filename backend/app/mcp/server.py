"""Streamable HTTP tools. Filters are attributes; the agent does the interpretation."""

from __future__ import annotations

import uuid
from typing import Any

from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import BaseModel, Field
from sqlmodel import select

from app.analytics.log import log_mcp_call
from app.config import get_settings
from app.db import session_scope
from app.diagnostics.report import DiagnosticReport
from app.diagnostics.service import diagnose_url
from app.domain.catalog import BusinessCatalog, ConversionPointDraft, Offering
from app.domain.validation import SchemaValidationError
from app.models import ConversionPoint, Delivery
from app.services.conversions import ConversionNotFound, submit_conversion
from app.services.persistence import load_catalog
from app.services.search import find_offering, list_points, published_business, search_businesses

INSTRUCTIONS = (
    "公開済みの事業者カタログです。意味検索はありません。"
    "条件は search_businesses の引数（名称の部分一致、タグ、エリア、業種キー、提供種別、価格帯）で指定してください。"
    "提案する前に get_business で拡張属性・実績・信頼情報を読み、"
    "依頼は list_conversion_points の input_schema を満たす payload で submit_conversion してください。"
    "掲載されていない事業者を作らないでください。\n\n"
    "Published business catalog for agentic commerce. There is no vector search. "
    "Filter with search_businesses, read get_business before recommending, and submit_conversion "
    "only with a payload that validates against that conversion point's JSON Schema."
)

mcp = MCPServer(
    "agentfront",
    title="agentfront",
    instructions=INSTRUCTIONS,
)


class SearchHit(BaseModel):
    id: str
    name: str
    slug: str
    summary: str
    service_area: list[str]
    tags: list[str]
    vertical_key: str | None = None
    price_range: dict[str, Any] | None = None
    conversion_types: list[str] = Field(default_factory=list)
    public_url: str


class SearchResponse(BaseModel):
    businesses: list[SearchHit]


class BusinessDetail(BaseModel):
    id: str
    public_url: str
    markdown_url: str
    agents_md_url: str
    ucp_url: str
    catalog: BusinessCatalog


class OfferingDetail(BaseModel):
    id: str
    business_id: str
    business_name: str
    business_slug: str
    public_url: str
    offering: Offering
    conversion_points: list[ConversionPointDraft]


class PointInfo(BaseModel):
    id: str
    business_id: str
    business_slug: str
    business_name: str
    key: str
    type: str
    name: str
    description: str
    input_schema: dict[str, Any]
    external_url: str | None = None


class PointList(BaseModel):
    conversion_points: list[PointInfo]


class DeliveryInfo(BaseModel):
    adapter: str
    status: str
    detail: str = ""


class SubmitResult(BaseModel):
    conversion_id: str
    status: str
    deliveries: list[DeliveryInfo]


def _base() -> str:
    return get_settings().public_base_url.rstrip("/")


def _user_agent(ctx: Context) -> str:
    try:
        headers = ctx.headers or {}
    except Exception:  # noqa: BLE001
        return ""
    for key, value in dict(headers).items():
        if str(key).lower() == "user-agent":
            return str(value)
    return ""


def _log(tool: str, arguments: dict[str, Any], ids: list[str], agent_name: str, ctx: Context) -> None:
    log_mcp_call(tool, arguments, ids, agent_name=agent_name, user_agent=_user_agent(ctx))


@mcp.tool(name="search_businesses", description="Filter published businesses by attributes. This is not semantic search.")
def search_businesses_tool(
    q: str = "",
    tags: list[str] | None = None,
    area: str = "",
    vertical: str = "",
    kind: str = "",
    price_min: int | None = None,
    price_max: int | None = None,
    limit: int = 20,
    agent_name: str = "",
    ctx: Context = None,  # type: ignore[assignment]
) -> SearchResponse:
    with session_scope() as session:
        rows = search_businesses(
            session,
            q=q or None,
            tags=tags,
            area=area or None,
            vertical=vertical or None,
            kind=kind or None,
            price_min=price_min,
            price_max=price_max,
            limit=limit,
        )
        ids = [row.id for row in rows]
        type_map: dict[Any, list[str]] = {row.id: [] for row in rows}
        if ids:
            points = session.exec(
                select(ConversionPoint).where(
                    ConversionPoint.business_id.in_(ids),
                    ConversionPoint.enabled == True,  # noqa: E712
                )
            ).all()
            for point in points:
                type_map.setdefault(point.business_id, []).append(point.type)
        base = _base()
        hits = [
            SearchHit(
                id=str(row.id),
                name=row.name,
                slug=row.slug,
                summary=row.summary,
                service_area=list(row.service_area or []),
                tags=list(row.tags or []),
                vertical_key=row.vertical_key,
                price_range=row.price_range,
                conversion_types=sorted(set(type_map.get(row.id, []))),
                public_url=f"{base}/b/{row.slug}",
            )
            for row in rows
        ]
    _log(
        "search_businesses",
        {"q": q, "tags": tags, "area": area, "vertical": vertical, "kind": kind, "price_min": price_min, "price_max": price_max},
        [hit.id for hit in hits],
        agent_name,
        ctx,
    )
    return SearchResponse(businesses=hits)


@mcp.tool(description="Full typed detail for one published business, including extension fields, works, and trust.")
def get_business(
    business_id: str = "",
    slug: str = "",
    agent_name: str = "",
    ctx: Context = None,  # type: ignore[assignment]
) -> BusinessDetail:
    with session_scope() as session:
        row = None
        if business_id:
            try:
                row = published_business(session, business_id=uuid.UUID(business_id))
            except ValueError as exc:
                raise ToolError("business_id が UUID ではありません") from exc
        elif slug:
            row = published_business(session, slug=slug)
        if row is None:
            raise ToolError("公開中の事業者が見つかりません")
        catalog = load_catalog(session, row, include_adapter_config=False)
        base = _base()
        detail = BusinessDetail(
            id=str(row.id),
            public_url=f"{base}/b/{row.slug}",
            markdown_url=f"{base}/b/{row.slug}.md",
            agents_md_url=f"{base}/b/{row.slug}/agents.md",
            ucp_url=f"{base}/b/{row.slug}/.well-known/ucp",
            catalog=catalog,
        )
        found = str(row.id)
    _log("get_business", {"business_id": business_id, "slug": slug}, [found], agent_name, ctx)
    return detail


@mcp.tool(description="One offering, including its extension fields and the conversion points that apply.")
def get_offering(
    offering_id: str = "",
    business_slug: str = "",
    offering_slug: str = "",
    agent_name: str = "",
    ctx: Context = None,  # type: ignore[assignment]
) -> OfferingDetail:
    with session_scope() as session:
        try:
            parsed = uuid.UUID(offering_id) if offering_id else None
        except ValueError as exc:
            raise ToolError("offering_id が UUID ではありません") from exc
        business, row = find_offering(
            session,
            offering_id=parsed,
            business_slug=business_slug or None,
            offering_slug=offering_slug or None,
        )
        if business is None or row is None:
            raise ToolError("提供内容が見つかりません")
        catalog = load_catalog(session, business, include_adapter_config=False)
        offering = next((item for item in catalog.offerings if item.slug == row.slug), None)
        if offering is None:
            raise ToolError("提供内容が見つかりません")
        points = [
            point
            for point in catalog.conversion_points
            if point.enabled and (point.offering_slug in (None, "", offering.slug))
        ]
        detail = OfferingDetail(
            id=str(row.id),
            business_id=str(business.id),
            business_name=business.name,
            business_slug=business.slug,
            public_url=f"{_base()}/b/{business.slug}/o/{offering.slug}",
            offering=offering,
            conversion_points=points,
        )
        found = str(row.id)
    _log("get_offering", {"offering_id": offering_id, "business_slug": business_slug, "offering_slug": offering_slug}, [found], agent_name, ctx)
    return detail


@mcp.tool(description="Conversion points and the JSON Schema of the inputs each one requires.")
def list_conversion_points(
    business_id: str = "",
    business_slug: str = "",
    agent_name: str = "",
    ctx: Context = None,  # type: ignore[assignment]
) -> PointList:
    with session_scope() as session:
        parsed = None
        if business_id:
            try:
                parsed = uuid.UUID(business_id)
            except ValueError as exc:
                raise ToolError("business_id が UUID ではありません") from exc
        rows = list_points(session, business_id=parsed, business_slug=business_slug or None)
        infos = []
        for point in rows:
            business = published_business(session, business_id=point.business_id)
            if business is None:
                continue
            infos.append(
                PointInfo(
                    id=str(point.id),
                    business_id=str(business.id),
                    business_slug=business.slug,
                    business_name=business.name,
                    key=point.key,
                    type=point.type,
                    name=point.name,
                    description=point.description,
                    input_schema=point.input_schema or {},
                    external_url=point.external_url,
                )
            )
    _log(
        "list_conversion_points",
        {"business_id": business_id, "business_slug": business_slug},
        [item.id for item in infos],
        agent_name,
        ctx,
    )
    return PointList(conversion_points=infos)


@mcp.tool(name="submit_conversion", description="Record a conversion. payload must validate against the point's JSON Schema.")
def submit_conversion_tool(
    conversion_point_id: str,
    payload: dict[str, Any],
    agent_name: str = "",
    request_text: str = "",
    ctx: Context = None,  # type: ignore[assignment]
) -> SubmitResult:
    try:
        point_id = uuid.UUID(conversion_point_id)
    except ValueError as exc:
        raise ToolError("conversion_point_id が UUID ではありません") from exc
    if not isinstance(payload, dict):
        raise ToolError("payload はオブジェクトである必要があります")
    with session_scope() as session:
        try:
            conversion = submit_conversion(
                session,
                conversion_point_id=point_id,
                payload=payload,
                agent_name=agent_name,
                request_text=request_text,
                user_agent=_user_agent(ctx),
            )
        except SchemaValidationError as exc:
            raise ToolError("入力がスキーマを満たしていません: " + "; ".join(exc.errors)) from exc
        except ConversionNotFound as exc:
            raise ToolError(str(exc)) from exc
        deliveries = session.exec(select(Delivery).where(Delivery.conversion_id == conversion.id)).all()
        result = SubmitResult(
            conversion_id=str(conversion.id),
            status=conversion.status,
            deliveries=[DeliveryInfo(adapter=item.adapter_key, status=item.status, detail=item.detail) for item in deliveries],
        )
    _log(
        "submit_conversion",
        {"conversion_point_id": conversion_point_id, "agent_name": agent_name, "payload": payload, "request_text": request_text},
        [result.conversion_id],
        agent_name,
        ctx,
    )
    return result


@mcp.tool(
    name="diagnose_agent_visibility",
    description="Score how visible a URL is to AI agents: robots.txt, structured data, readable text, and agent files.",
)
def diagnose_agent_visibility_tool(
    url: str,
    agent_name: str = "",
    ctx: Context = None,  # type: ignore[assignment]
) -> DiagnosticReport:
    try:
        report = DiagnosticReport.model_validate(diagnose_url(url))
    except ValueError as exc:
        raise ToolError(str(exc)) from exc
    _log("diagnose_agent_visibility", {"url": url}, [], agent_name, ctx)
    return report


def streamable_app():
    """Build the Streamable HTTP ASGI app. Call once, then run its session manager."""
    return mcp.streamable_http_app(
        streamable_http_path="/mcp",
        json_response=True,
        stateless_http=True,
        host="0.0.0.0",
    )
