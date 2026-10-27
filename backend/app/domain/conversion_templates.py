"""Fallback input schemas when a model omits one. Operators can replace them."""

from __future__ import annotations

from typing import Any


def _contact_fields() -> dict[str, Any]:
    return {
        "name": {"type": "string", "title": "お名前"},
        "email": {"type": "string", "format": "email", "title": "メールアドレス"},
        "phone": {"type": "string", "title": "電話番号"},
        "notes": {"type": "string", "title": "補足"},
    }


def _object(properties: dict[str, Any], required: list[str], title: str) -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "title": title,
        "additionalProperties": False,
        "properties": properties,
        "required": required,
    }


def default_input_schema(conversion_type: str) -> dict[str, Any]:
    contact = _contact_fields()
    if conversion_type == "quote_request":
        props = {
            **contact,
            "location": {"type": "string", "title": "場所・エリア"},
            "budget_jpy": {"type": "integer", "title": "予算（円）"},
            "timing": {"type": "string", "title": "希望時期"},
        }
        return _object(props, ["name", "email", "location", "budget_jpy", "timing"], "見積依頼")
    if conversion_type == "booking":
        props = {
            **contact,
            "desired_datetime": {"type": "string", "format": "date-time", "title": "希望日時"},
        }
        return _object(props, ["name", "email", "desired_datetime"], "予約")
    if conversion_type == "document_request":
        props = {**contact, "document": {"type": "string", "title": "希望する資料"}}
        return _object(props, ["name", "email"], "資料請求")
    if conversion_type == "purchase":
        props = {
            **contact,
            "quantity": {"type": "integer", "minimum": 1, "title": "数量", "default": 1},
            "offering": {"type": "string", "title": "希望する内容"},
        }
        return _object(props, ["name", "email", "offering"], "購入意向")
    if conversion_type == "external_link":
        return _object({"note": {"type": "string", "title": "メモ"}}, [], "外部リンク")
    props = {**contact, "message": {"type": "string", "title": "内容"}}
    return _object(props, ["name", "email", "message"], "問い合わせ")


CONSTRUCTION_QUOTE_SCHEMA = _object(
    {
        **_contact_fields(),
        "location": {"type": "string", "title": "建設地"},
        "floor_area_sqm": {"type": "number", "title": "延床面積（㎡）"},
        "budget_jpy": {"type": "integer", "title": "予算（円）"},
        "timing": {"type": "string", "title": "希望時期"},
    },
    ["name", "email", "location", "floor_area_sqm", "budget_jpy", "timing"],
    "建築の見積相談",
)

VIDEO_QUOTE_SCHEMA = _object(
    {
        **_contact_fields(),
        "purpose": {"type": "string", "title": "映像の目的"},
        "length": {"type": "string", "title": "尺"},
        "deadline": {"type": "string", "title": "納期"},
        "budget_jpy": {"type": "integer", "title": "予算（円）"},
        "reference": {"type": "string", "title": "参考にしたいイメージ"},
    },
    ["name", "email", "purpose", "length", "deadline", "budget_jpy"],
    "映像の見積依頼",
)
