"""Universal Commerce Protocol profiles built from the central catalog."""

from __future__ import annotations

from typing import Any

from app.domain.catalog import BusinessCatalog, ConversionPointDraft

UCP_VERSION = "2026-08-25"
UCP_SPEC_URL = "https://ucp.dev/2026-08-25/specification/overview/"
UCP_SHOPPING_SCHEMA = "https://ucp.dev/2026-08-25/services/shopping/rest.openapi.json"
VENDOR_SERVICE = "com.agentfront.catalog"

# One row per conversion point type. New types only need a row here; the rest
# of the profile, agents.md, and URLs follow from it.
CONVERSION_CAPABILITIES: dict[str, dict[str, str]] = {
    "purchase": {"capability": "checkout", "label": "purchase"},
    "quote_request": {"capability": "quote_request", "label": "quote request"},
    "inquiry": {"capability": "inquiry", "label": "inquiry"},
    "booking": {"capability": "consultation_booking", "label": "consultation booking"},
    "document_request": {"capability": "document_request", "label": "document request"},
    "external_link": {"capability": "external_redirect", "label": "external redirect"},
}


def conversion_meta(conversion_type: str) -> dict[str, str]:
    return CONVERSION_CAPABILITIES.get(
        conversion_type,
        {"capability": conversion_type or "conversion", "label": conversion_type or "conversion"},
    )


def conversion_label(conversion_type: str) -> str:
    return conversion_meta(conversion_type)["label"]


def conversion_target(
    base: str,
    slug: str,
    *,
    conversion_type: str,
    key: str,
    external_url: str | None = None,
) -> tuple[str, str]:
    if conversion_type == "external_link" and external_url:
        return external_url, "GET"
    return f"{base}/b/{slug}/convert/{key}", "POST"


def _binding(endpoint: str, transport: str, schema: str) -> dict[str, Any]:
    return {
        "version": UCP_VERSION,
        "spec": UCP_SPEC_URL,
        "transport": transport,
        "endpoint": endpoint,
        "schema": schema,
    }


def _business_urls(base: str, slug: str) -> dict[str, str]:
    return {
        "html_url": f"{base}/b/{slug}",
        "agents_md": f"{base}/b/{slug}/agents.md",
        "ucp_url": f"{base}/b/{slug}/.well-known/ucp",
        "llms_txt": f"{base}/llms.txt",
        "feed_json": f"{base}/b/{slug}/feed.json",
    }


def _point_config(base: str, slug: str, point: ConversionPointDraft) -> dict[str, Any]:
    endpoint, method = conversion_target(
        base,
        slug,
        conversion_type=point.type,
        key=point.key,
        external_url=point.external_url,
    )
    return {
        "key": point.key,
        "label": conversion_label(point.type),
        "endpoint": endpoint,
        "method": method,
        "input_schema": point.input_schema,
        "requires_human_authorization": True,
    }


def build_ucp_profile(catalog: BusinessCatalog, base: str) -> dict[str, Any]:
    base = base.rstrip("/")
    urls = _business_urls(base, catalog.slug)
    services: dict[str, list[dict[str, Any]]] = {
        VENDOR_SERVICE: [
            _binding(f"{base}/mcp", "mcp", urls["agents_md"]),
            _binding(urls["feed_json"], "rest", urls["feed_json"]),
        ]
    }
    capabilities: dict[str, list[dict[str, Any]]] = {}
    payment_handlers: dict[str, list[dict[str, Any]]] = {}

    points = [point for point in catalog.conversion_points if point.enabled]
    for point in points:
        config = _point_config(base, catalog.slug, point)
        if point.type == "purchase":
            services.setdefault("dev.ucp.shopping", []).append(
                _binding(config["endpoint"], "rest", UCP_SHOPPING_SCHEMA)
            )
            capabilities.setdefault("dev.ucp.shopping.checkout", []).append(
                {
                    "version": UCP_VERSION,
                    "spec": UCP_SPEC_URL,
                    "schema": UCP_SHOPPING_SCHEMA,
                    "config": {**config, "mode": "redirect"},
                }
            )
            payment_handlers.setdefault("com.agentfront.purchase", []).append(
                {
                    "version": UCP_VERSION,
                    "spec": UCP_SPEC_URL,
                    "schema": UCP_SHOPPING_SCHEMA,
                    "config": {
                        "mode": "redirect",
                        "endpoint": config["endpoint"],
                        "requires_human_authorization": True,
                    },
                }
            )
            continue
        name = f"com.agentfront.conversion.{conversion_meta(point.type)['capability']}"
        capabilities.setdefault(name, []).append(
            {
                "version": UCP_VERSION,
                "spec": UCP_SPEC_URL,
                "schema": urls["ucp_url"],
                "config": config,
            }
        )

    return {
        "ucp": {
            "version": UCP_VERSION,
            "services": services,
            "capabilities": capabilities,
            "payment_handlers": payment_handlers,
        },
        "com.agentfront.business": {
            "name": catalog.name,
            "slug": catalog.slug,
            "html_url": urls["html_url"],
            "agents_md": urls["agents_md"],
            "llms_txt": urls["llms_txt"],
        },
    }


def build_platform_profile(base: str) -> dict[str, Any]:
    base = base.rstrip("/")
    return {
        "ucp": {
            "version": UCP_VERSION,
            "services": {
                VENDOR_SERVICE: [_binding(f"{base}/mcp", "mcp", f"{base}/agents.md")]
            },
            "capabilities": {},
            "payment_handlers": {},
        },
        "com.agentfront.platform": {
            "name": "agentfront",
            "agents_md": f"{base}/agents.md",
            "llms_txt": f"{base}/llms.txt",
        },
    }
