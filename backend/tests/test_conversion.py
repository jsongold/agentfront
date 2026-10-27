"""Conversion payloads are checked against the point's JSON Schema."""

from __future__ import annotations

import pytest

from app.domain.conversion_templates import CONSTRUCTION_QUOTE_SCHEMA, VIDEO_QUOTE_SCHEMA, default_input_schema
from app.domain.validation import SchemaValidationError, validate_conversion_payload


def test_construction_quote_accepts_required_fields():
    validate_conversion_payload(
        CONSTRUCTION_QUOTE_SCHEMA,
        {
            "name": "田中",
            "email": "tanaka@example.com",
            "location": "鎌倉市",
            "floor_area_sqm": 120,
            "budget_jpy": 40000000,
            "timing": "来春",
        },
    )


def test_construction_quote_rejects_missing_floor_area():
    with pytest.raises(SchemaValidationError) as raised:
        validate_conversion_payload(
            CONSTRUCTION_QUOTE_SCHEMA,
            {"name": "田中", "email": "tanaka@example.com", "location": "鎌倉市", "budget_jpy": 1, "timing": "来春"},
        )
    assert any("floor_area_sqm" in message for message in raised.value.errors)


def test_video_quote_requires_purpose_length_deadline_budget():
    with pytest.raises(SchemaValidationError):
        validate_conversion_payload(
            VIDEO_QUOTE_SCHEMA,
            {"name": "佐藤", "email": "sato@example.com", "purpose": "採用"},
        )
    validate_conversion_payload(
        VIDEO_QUOTE_SCHEMA,
        {
            "name": "佐藤",
            "email": "sato@example.com",
            "purpose": "採用",
            "length": "90秒",
            "deadline": "3月",
            "budget_jpy": 800000,
            "reference": "静かなインタビュー",
        },
    )


def test_booking_requires_datetime():
    schema = default_input_schema("booking")
    with pytest.raises(SchemaValidationError):
        validate_conversion_payload(schema, {"name": "青木", "email": "aoki@example.com"})
    validate_conversion_payload(
        schema,
        {"name": "青木", "email": "aoki@example.com", "desired_datetime": "2026-11-02T10:00:00+09:00"},
    )


def test_payload_must_be_object():
    with pytest.raises(SchemaValidationError):
        validate_conversion_payload(default_input_schema("inquiry"), ["nope"])  # type: ignore[arg-type]
