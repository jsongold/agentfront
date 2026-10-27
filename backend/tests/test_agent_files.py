"""agents.md and UCP profiles are projections of the same published catalog."""

from __future__ import annotations

from app.domain.catalog import ConversionPointDraft
from app.render.pages import render_agents_md, render_site_agents_md, view_business
from app.render.ucp import build_platform_profile, build_ucp_profile
from app.seed import aoba_catalog, kogaku_catalog
from app.services.persistence import prepare_catalog

BASE = "http://localhost:8765"


def _prepared(catalog):
    return prepare_catalog(catalog)


def test_agents_md_describes_business_and_query_surfaces():
    catalog = _prepared(aoba_catalog(BASE))
    text = render_agents_md(catalog, BASE)

    assert "# 青葉設計室" in text
    assert f"{BASE}/mcp" in text
    assert f"{BASE}/b/aoba-sekkei/agents.md" in text
    assert f"{BASE}/b/aoba-sekkei/.well-known/ucp" in text
    assert f"{BASE}/b/aoba-sekkei/feed.json" in text
    for tool in ("search_businesses", "get_business", "get_offering", "list_conversion_points", "submit_conversion"):
        assert tool in text
    for key in ("quote", "visit", "brochure"):
        assert key in text
    assert "floor_area_sqm" in text
    assert "custom-house" in text
    assert "Human authorization" in text
    assert "explicit authorization" in text
    assert "MUST confirm" in text


def test_site_agents_md_links_each_business_agents_md():
    catalog = _prepared(aoba_catalog(BASE))
    text = render_site_agents_md([view_business(catalog, BASE)], BASE)

    assert "青葉設計室" in text
    assert f"{BASE}/b/aoba-sekkei/agents.md" in text
    assert f"{BASE}/.well-known/ucp" in text


def test_ucp_profile_has_required_registries_and_mcp_binding():
    catalog = _prepared(aoba_catalog(BASE))
    profile = build_ucp_profile(catalog, BASE)
    ucp = profile["ucp"]

    assert ucp["version"] == "2026-08-25"
    assert "services" in ucp
    assert "capabilities" in ucp
    assert "payment_handlers" in ucp
    assert ucp["payment_handlers"] == {}
    bindings = ucp["services"]["com.agentfront.catalog"]
    assert any(item["transport"] == "mcp" and item["endpoint"] == f"{BASE}/mcp" for item in bindings)
    assert any(item["transport"] == "rest" and item["endpoint"] == f"{BASE}/b/aoba-sekkei/feed.json" for item in bindings)
    assert profile["com.agentfront.business"] == {
        "name": "青葉設計室",
        "slug": "aoba-sekkei",
        "html_url": f"{BASE}/b/aoba-sekkei",
        "agents_md": f"{BASE}/b/aoba-sekkei/agents.md",
        "llms_txt": f"{BASE}/llms.txt",
    }


def test_non_purchase_business_uses_vendor_conversion_capabilities():
    catalog = _prepared(aoba_catalog(BASE))
    ucp = build_ucp_profile(catalog, BASE)["ucp"]

    assert "dev.ucp.shopping" not in ucp["services"]
    assert "dev.ucp.shopping.checkout" not in ucp["capabilities"]
    for name in (
        "com.agentfront.conversion.quote_request",
        "com.agentfront.conversion.consultation_booking",
        "com.agentfront.conversion.document_request",
    ):
        assert name in ucp["capabilities"]
    quote = ucp["capabilities"]["com.agentfront.conversion.quote_request"][0]
    assert quote["config"]["key"] == "quote"
    assert quote["config"]["endpoint"] == f"{BASE}/b/aoba-sekkei/convert/quote"
    assert quote["config"]["method"] == "POST"
    assert quote["config"]["requires_human_authorization"] is True
    assert quote["config"]["input_schema"]["required"]


def test_external_link_maps_to_external_redirect():
    catalog = _prepared(kogaku_catalog(BASE))
    ucp = build_ucp_profile(catalog, BASE)["ucp"]

    assert "com.agentfront.conversion.inquiry" in ucp["capabilities"]
    redirect = ucp["capabilities"]["com.agentfront.conversion.external_redirect"][0]
    assert redirect["config"]["key"] == "showreel"
    assert redirect["config"]["endpoint"] == "https://example.com/kogaku-showreel"
    assert redirect["config"]["method"] == "GET"


def test_purchase_business_advertises_checkout():
    catalog = aoba_catalog(BASE)
    catalog.conversion_points.append(
        ConversionPointDraft(key="buy", type="purchase", name="購入", description="相談後に購入")
    )
    catalog = _prepared(catalog)
    ucp = build_ucp_profile(catalog, BASE)["ucp"]

    assert "dev.ucp.shopping" in ucp["services"]
    assert "dev.ucp.shopping.checkout" in ucp["capabilities"]
    checkout = ucp["capabilities"]["dev.ucp.shopping.checkout"][0]
    assert checkout["config"]["key"] == "buy"
    assert checkout["config"]["mode"] == "redirect"
    assert checkout["config"]["requires_human_authorization"] is True
    assert ucp["payment_handlers"]


def test_platform_profile_is_valid_without_capabilities():
    ucp = build_platform_profile(BASE)["ucp"]

    assert ucp["version"] == "2026-08-25"
    assert ucp["capabilities"] == {}
    assert ucp["payment_handlers"] == {}
    assert any(
        item["transport"] == "mcp" and item["endpoint"] == f"{BASE}/mcp"
        for item in ucp["services"]["com.agentfront.catalog"]
    )
