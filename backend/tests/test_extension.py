"""Vertical extensions are JSON Schema, not new columns on the core model."""

from __future__ import annotations

import copy

import pytest

from app.domain.catalog import BusinessCatalog, Seller
from app.domain.validation import SchemaValidationError, tighten_schema, validate_catalog_extensions, validate_extension
from app.seed import ARCHITECTURE_SCHEMA, VIDEO_SCHEMA, aoba_catalog, kogaku_catalog
from app.services.persistence import prepare_catalog

BASE = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "structure_types": {"type": "array", "items": {"type": "string"}, "title": "構造"},
        "handles_construction": {"type": "boolean", "title": "施工"},
    },
}


def test_extension_accepts_valid_payload():
    validate_extension(tighten_schema(copy.deepcopy(BASE)), {"structure_types": ["木造"], "handles_construction": True})


def test_extension_rejects_wrong_type():
    with pytest.raises(SchemaValidationError) as raised:
        validate_extension(tighten_schema(copy.deepcopy(BASE)), {"handles_construction": "yes"})
    assert raised.value.errors


def test_new_field_does_not_require_a_core_model_change():
    schema = tighten_schema(copy.deepcopy(BASE))
    schema["properties"]["seismic_grade"] = {"type": "string", "title": "耐震等級"}
    assert "seismic_grade" not in BusinessCatalog.model_fields
    catalog = BusinessCatalog(
        name="青葉設計室",
        slug="aoba",
        seller=Seller(name="青葉設計室"),
        extension={"structure_types": ["木造"], "handles_construction": True, "seismic_grade": "3"},
    )
    validate_catalog_extensions(schema, catalog)
    assert catalog.extension["seismic_grade"] == "3"


def test_unknown_extension_property_is_rejected():
    with pytest.raises(SchemaValidationError):
        validate_extension(tighten_schema(copy.deepcopy(BASE)), {"not_a_field": 1})


def test_seed_catalogs_validate_against_their_schemas():
    pairs = (
        (ARCHITECTURE_SCHEMA, aoba_catalog("http://localhost:8765")),
        (VIDEO_SCHEMA, kogaku_catalog("http://localhost:8765")),
    )
    for document, catalog in pairs:
        schema = tighten_schema(copy.deepcopy(document))
        prepared = prepare_catalog(catalog)
        validate_catalog_extensions(schema, prepared)
        assert prepared.slug
        assert prepared.conversion_points
