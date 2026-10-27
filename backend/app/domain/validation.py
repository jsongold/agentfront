"""JSON Schema checks for vertical extensions and conversion payloads."""

from __future__ import annotations

from typing import Any

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import SchemaError

from app.domain.catalog import BusinessCatalog


class SchemaValidationError(Exception):
    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("; ".join(errors))


def tighten_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Default object schemas to closed so a typo does not silently pass."""

    def walk(node: Any) -> None:
        if not isinstance(node, dict):
            return
        if node.get("type") == "object":
            node.setdefault("additionalProperties", False)
            for prop in (node.get("properties") or {}).values():
                walk(prop)
        items = node.get("items")
        if isinstance(items, dict):
            walk(items)
        for key in ("$defs", "definitions"):
            for prop in (node.get(key) or {}).values():
                walk(prop)
        for key in ("anyOf", "oneOf", "allOf"):
            for prop in node.get(key) or []:
                walk(prop)

    walk(schema)
    schema.setdefault("type", "object")
    schema.setdefault("$schema", "https://json-schema.org/draft/2020-12/schema")
    return schema


def check_schema_document(schema: dict[str, Any]) -> None:
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as exc:
        raise SchemaValidationError([f"JSON Schema が不正です: {exc.message}"]) from exc


def schema_errors(schema: dict[str, Any], data: Any) -> list[str]:
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    found = sorted(validator.iter_errors(data), key=lambda err: list(err.path))
    messages: list[str] = []
    for err in found:
        path = "/".join(str(part) for part in err.path) or "(root)"
        messages.append(f"{path}: {err.message}")
    return messages


def validate_extension(schema: dict[str, Any] | None, data: Any) -> None:
    if not schema:
        if data in (None, {}, []):
            return
        raise SchemaValidationError(["拡張スキーマが無いのに拡張データがあります"])
    if not isinstance(data, dict):
        raise SchemaValidationError(["拡張データはオブジェクトである必要があります"])
    errors = schema_errors(schema, data)
    if errors:
        raise SchemaValidationError(errors)


def offering_extension_schema(schema: dict[str, Any] | None) -> dict[str, Any] | None:
    if not schema:
        return None
    defs = schema.get("$defs") or schema.get("definitions") or {}
    candidate = defs.get("offering")
    return candidate if isinstance(candidate, dict) else None


def validate_catalog_extensions(schema: dict[str, Any] | None, catalog: BusinessCatalog) -> None:
    """Validate extension JSON. Core fields are already typed by Pydantic."""
    errors: list[str] = []
    if schema:
        errors.extend(schema_errors(schema, catalog.extension or {}))
        nested = offering_extension_schema(schema)
        if nested:
            for offering in catalog.offerings:
                for message in schema_errors(nested, offering.extension or {}):
                    errors.append(f"{offering.slug or offering.name}: {message}")
    if errors:
        raise SchemaValidationError(errors)


def validate_conversion_payload(schema: dict[str, Any] | None, payload: Any) -> None:
    if not isinstance(payload, dict):
        raise SchemaValidationError(["payload はオブジェクトである必要があります"])
    if not schema:
        return
    errors = schema_errors(schema, payload)
    if errors:
        raise SchemaValidationError(errors)
