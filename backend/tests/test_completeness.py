"""Required fields are data, and completeness is a pure projection of the catalog."""

from __future__ import annotations

from app.domain.catalog import BusinessCatalog, Offering, PriceRange, Seller
from app.domain.completeness import (
    compute_completeness,
    ensure_required_properties,
    load_profiles,
    load_verticals,
    required_fields_text,
    resolve_profile,
)
from app.domain.validation import check_schema_document
from app.seed import ARCHITECTURE_SCHEMA, aoba_catalog, kogaku_catalog
from app.services.persistence import prepare_catalog

BASE = "http://localhost:8765"


def test_profiles_load_from_data_file():
    profiles = load_profiles()
    assert {"services", "goods"} <= set(profiles)
    assert profiles["services"]["fields"]
    assert profiles["goods"]["fields"]
    assert load_verticals()["architecture"]["extends"] == "services"


def test_services_vs_goods_resolution():
    aoba = prepare_catalog(aoba_catalog(BASE))
    kogaku = prepare_catalog(kogaku_catalog(BASE))
    goods = BusinessCatalog(
        name="工房ショップ",
        seller=Seller(name="工房ショップ"),
        schema_org_type="Product",
        offerings=[Offering(name="木の皿", kind="product")],
    )

    aoba_profile = resolve_profile(aoba)
    assert aoba_profile["key"] in {"services", "architecture"}
    assert any(field["key"] == "price_estimate_basis" for field in aoba_profile["fields"])
    assert resolve_profile(kogaku)["key"] == "services"
    assert resolve_profile(goods)["key"] == "goods"


def test_ensure_required_properties_adds_missing_and_stays_valid():
    profile = resolve_profile(
        {
            "vertical_key": "architecture",
            "schema_org_type": "HomeAndConstructionBusiness",
            "offerings": [],
        }
    )
    document = ensure_required_properties(ARCHITECTURE_SCHEMA, profile)

    check_schema_document(document)
    properties = document["properties"]
    assert "structure_types" in properties
    assert "lead_time" in properties
    assert "contract_terms" in properties
    assert "price_estimate_basis" not in properties
    assert properties["structure_types"] == ARCHITECTURE_SCHEMA["properties"]["structure_types"]
    assert document["additionalProperties"] is False


def test_ensure_required_properties_does_not_mutate_input():
    profile = resolve_profile({"vertical_key": "architecture", "offerings": []})
    original = {"type": "object", "additionalProperties": False, "properties": {}}
    result = ensure_required_properties(original, profile)

    assert original["properties"] == {}
    assert "lead_time" in result["properties"]


def test_aoba_completeness_is_sane_and_blank_fields_show_up():
    catalog = prepare_catalog(aoba_catalog(BASE))
    report = compute_completeness(catalog)

    assert report["profile"] in {"services", "architecture"}
    assert report["total"] >= 4
    assert 0 < report["score"] < 100
    assert report["filled"] + len(report["missing"]) + len(report["empty"]) == report["total"]

    catalog.extension["structure_types"] = []
    blanked = compute_completeness(catalog)
    structure = next(field for field in resolve_profile(catalog)["fields"] if field["key"] == "structure")
    assert any(item["key"] == structure["key"] for item in blanked["empty"] + blanked["missing"])


def test_goods_catalog_reports_price_stock_shipping_and_returns():
    catalog = BusinessCatalog(
        name="工房ショップ",
        seller=Seller(name="工房ショップ"),
        schema_org_type="Product",
        price_range=PriceRange(min_amount=3000, max_amount=12000),
        offerings=[Offering(name="木の皿", kind="product")],
        extension={"stock": "在庫あり", "shipping_cost": "全国一律800円", "return_policy": "到着後7日以内"},
    )
    report = compute_completeness(catalog)

    assert report["profile"] == "goods"
    assert report["score"] == 100
    assert report["missing"] == []
    assert report["empty"] == []


def test_required_fields_text_lists_titles_and_paths():
    text = required_fields_text(resolve_profile(aoba_catalog(BASE)))

    assert "価格帯・見積の算定根拠" in text
    assert "extension.contract_terms" in text
