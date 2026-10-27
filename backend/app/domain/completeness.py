"""Industry required fields and the completeness report.

Profiles live in ``required_fields.yaml`` so a new trade is a data change, not a
code change. The functions here are pure and can be tested without a database.
"""

from __future__ import annotations

import copy
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

import yaml

from app.domain.catalog import BusinessCatalog

DATA_FILE = Path(__file__).with_name("required_fields.yaml")


def _read_data() -> dict[str, Any]:
    raw = yaml.safe_load(DATA_FILE.read_text(encoding="utf-8")) or {}
    return {
        "default": str(raw.get("default") or "services"),
        "profiles": dict(raw.get("profiles") or {}),
        "verticals": dict(raw.get("verticals") or {}),
    }


@lru_cache(maxsize=1)
def load_data() -> dict[str, Any]:
    return _read_data()


def load_profiles() -> dict[str, dict[str, Any]]:
    return load_data()["profiles"]


def load_verticals() -> dict[str, dict[str, Any]]:
    return load_data()["verticals"]


def load_required_fields() -> dict[str, Any]:
    """Everything the admin UI and callers need in one JSON-friendly payload."""
    return load_data()


def _normalize_key(value: Any) -> str:
    return str(value or "").strip().lower().replace("-", "_")


def _as_mapping(catalog: BusinessCatalog | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(catalog, BusinessCatalog):
        return catalog.model_dump(mode="json")
    return dict(catalog or {})


def _coerce_profile(profile: Mapping[str, Any] | str | None) -> dict[str, Any] | None:
    if not isinstance(profile, str):
        return dict(profile) if profile else None
    definitions = load_data()
    for key, override in definitions["verticals"].items():
        if _normalize_key(key) == _normalize_key(profile):
            return _merge_profile(key, override, definitions["profiles"])
    base = definitions["profiles"].get(profile)
    return {**copy.deepcopy(base), "key": profile} if base else None


def _merge_profile(key: str, override: Mapping[str, Any], profiles: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    base_key = _normalize_key(override.get("extends") or key)
    base = copy.deepcopy(dict(profiles.get(base_key) or {}))
    merged = {**base, **{name: copy.deepcopy(value) for name, value in override.items() if name not in {"fields", "extends"}}}
    fields: dict[str, dict[str, Any]] = {}
    for field in base.get("fields") or []:
        fields[str(field.get("key") or "")] = copy.deepcopy(field)
    for field in override.get("fields") or []:
        name = str(field.get("key") or "")
        fields[name] = {**fields.get(name, {}), **copy.deepcopy(field)}
    merged["key"] = key
    merged["fields"] = list(fields.values())
    return merged


def _profile_matches(profile: Mapping[str, Any], data: Mapping[str, Any], vertical_key: str) -> bool:
    match = profile.get("match") or {}
    schema_org_type = str(data.get("schema_org_type") or "")
    if schema_org_type and schema_org_type in {str(item) for item in match.get("schema_org_types") or []}:
        return True
    keywords = [str(item).lower() for item in match.get("vertical_keys_contains") or []]
    if vertical_key and any(keyword in vertical_key for keyword in keywords):
        return True
    kinds = {str(item.get("kind") or "") for item in data.get("offerings") or [] if isinstance(item, Mapping)}
    wanted = {str(item) for item in match.get("offering_kinds") or []}
    return bool(kinds & wanted)


def resolve_profile(catalog: BusinessCatalog | Mapping[str, Any]) -> dict[str, Any]:
    """Vertical override first, then profile match, then the configured default."""
    data = _as_mapping(catalog)
    definitions = load_data()
    profiles = definitions["profiles"]
    verticals = definitions["verticals"]
    vertical_key = _normalize_key(data.get("vertical_key"))
    for key, override in verticals.items():
        if _normalize_key(key) == vertical_key:
            return _merge_profile(key, override, profiles)
    offering_kinds = {str(item.get("kind") or "") for item in data.get("offerings") or [] if isinstance(item, Mapping)}
    if offering_kinds and offering_kinds <= {"product"}:
        for key, profile in profiles.items():
            wanted = {str(item) for item in (profile.get("match") or {}).get("offering_kinds") or []}
            if "product" in wanted:
                return {**copy.deepcopy(profile), "key": key}
    for key, profile in profiles.items():
        if _profile_matches(profile, data, vertical_key):
            return {**copy.deepcopy(profile), "key": key}
    default_key = definitions["default"]
    profile = profiles.get(default_key) or next(iter(profiles.values()), {})
    return {**copy.deepcopy(profile), "key": default_key if default_key in profiles else next(iter(profiles), "default")}


def _segments(path: str) -> list[str]:
    return [part for part in path.split(".") if part]


def walk_path(data: Any, path: str) -> list[Any]:
    """Return every value reached by a dotted path. ``[]`` expands a list."""
    nodes: list[Any] = [data]
    for segment in _segments(path):
        is_list = segment.endswith("[]")
        name = segment[:-2] if is_list else segment
        found: list[Any] = []
        for node in nodes:
            if not isinstance(node, Mapping) or name not in node:
                continue
            value = node[name]
            if is_list:
                if isinstance(value, list):
                    found.extend(value)
                elif value is not None:
                    found.append(value)
            else:
                found.append(value)
        nodes = found
        if not nodes:
            return []
    return nodes


def _is_empty(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, tuple, dict, set)):
        return not value
    return False


def _field_status(field: Mapping[str, Any], data: Mapping[str, Any]) -> str:
    """Return ``filled``, ``empty``, or ``missing`` for one required field."""
    found = False
    for path in field.get("paths") or []:
        values = walk_path(data, str(path))
        if not values:
            continue
        found = True
        if any(not _is_empty(value) for value in values):
            return "filled"
    return "empty" if found else "missing"


def compute_completeness(
    catalog: BusinessCatalog | Mapping[str, Any],
    profile: Mapping[str, Any] | str | None = None,
) -> dict[str, Any]:
    data = _as_mapping(catalog)
    profile = _coerce_profile(profile) or resolve_profile(catalog)
    filled = 0
    missing: list[dict[str, Any]] = []
    empty: list[dict[str, Any]] = []
    fields = profile.get("fields") or []
    for field in fields:
        item = {
            "key": field.get("key"),
            "title": field.get("title") or field.get("key"),
            "paths": list(field.get("paths") or []),
        }
        status = _field_status(field, data)
        if status == "filled":
            filled += 1
        elif status == "empty":
            empty.append(item)
        else:
            missing.append(item)
    total = len(fields)
    score = round(filled * 100 / total) if total else 100
    return {
        "profile": profile.get("key"),
        "title": profile.get("title") or profile.get("key"),
        "score": score,
        "total": total,
        "filled": filled,
        "missing": missing,
        "empty": empty,
        "computed_at": datetime.now(timezone.utc).isoformat(),
    }


def _has_core_path(field: Mapping[str, Any]) -> bool:
    for path in field.get("paths") or []:
        text = str(path)
        if text.startswith("extension.") or ".extension." in text:
            continue
        return True
    return False


def _schema_property(field: Mapping[str, Any]) -> str:
    explicit = field.get("schema_property")
    if explicit:
        return str(explicit)
    property_name = str(field.get("key") or "")
    for path in field.get("paths") or []:
        text = str(path)
        if text.startswith("extension."):
            return text.split(".", 1)[1].split(".")[0].removesuffix("[]")
        if "extension." in text:
            return text.split("extension.", 1)[1].split(".")[0].removesuffix("[]")
    return property_name


def _schema_target(field: Mapping[str, Any]) -> str:
    explicit = field.get("schema_target")
    if explicit in {"root", "offering"}:
        return str(explicit)
    paths = [str(path) for path in field.get("paths") or []]
    has_root = any(path.startswith("extension.") for path in paths)
    has_offering = any(path.startswith("offerings[].") for path in paths)
    return "offering" if has_offering and not has_root else "root"


def _inject_property(target: dict[str, Any], name: str, schema: Mapping[str, Any], field: Mapping[str, Any]) -> None:
    target.setdefault("type", "object")
    target.setdefault("additionalProperties", False)
    properties = target.get("properties")
    if not isinstance(properties, dict):
        properties = {}
        target["properties"] = properties
    if name in properties:
        return
    prop = copy.deepcopy(dict(schema))
    prop.setdefault("title", field.get("title") or name)
    prop.setdefault("description", field.get("description") or "")
    properties[name] = prop


def ensure_required_properties(
    document: Mapping[str, Any] | None,
    profile: Mapping[str, Any] | str | None,
) -> dict[str, Any]:
    """Add profile properties the core catalog cannot carry to a vertical schema.

    Only fields with a ``schema`` and no core (non-extension) path are injected,
    and an existing property is never overwritten. A closed object stays valid.
    """
    result = copy.deepcopy(dict(document or {"type": "object", "additionalProperties": False, "properties": {}}))
    profile = _coerce_profile(profile)
    if not profile:
        return result
    result.setdefault("type", "object")
    result.setdefault("additionalProperties", False)
    if not isinstance(result.get("properties"), dict):
        result["properties"] = {}
    defs = result.get("$defs")
    if not isinstance(defs, dict):
        defs = result.get("definitions")
    if not isinstance(defs, dict):
        defs = {}
        result["$defs"] = defs
    for field in profile.get("fields") or []:
        schema = field.get("schema")
        if not isinstance(schema, Mapping) or _has_core_path(field):
            continue
        name = _schema_property(field)
        if not name:
            continue
        if _schema_target(field) == "offering":
            offering = defs.get("offering")
            if not isinstance(offering, dict):
                offering = {"type": "object", "additionalProperties": False, "properties": {}}
                defs["offering"] = offering
            _inject_property(offering, name, schema, field)
        else:
            _inject_property(result, name, schema, field)
    return result


def required_fields_text(profile: Mapping[str, Any] | str | None) -> str:
    """Plain-text field list for the propose and extract prompts."""
    profile = _coerce_profile(profile)
    if not profile:
        return "（指定なし）"
    lines = [
        f"業種プロファイル: {profile.get('title') or profile.get('key')}",
        "次の項目を、資料から読み取れる範囲で埋めてください。読み取れない項目は推測せず空のままにしてください。",
    ]
    for field in profile.get("fields") or []:
        key = field.get("key") or ""
        title = field.get("title") or key
        description = field.get("description") or ""
        paths = ", ".join(str(path) for path in field.get("paths") or [])
        lines.append(f"- {title} ({key}): {description} [paths: {paths}]")
    return "\n".join(lines)
