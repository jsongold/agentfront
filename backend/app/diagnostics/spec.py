"""Diagnostics configuration loaded from the adjacent YAML data file."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml


@dataclass(frozen=True)
class CheckSpec:
    key: str
    label: str
    weight: int
    recommendation: str


@dataclass(frozen=True)
class AgentFileSpec:
    key: str
    path: str
    label: str
    validator: str


@dataclass(frozen=True)
class DiagnosticsConfig:
    user_agent: str
    timeout_seconds: float
    max_bytes: int
    robots_max_bytes: int
    agent_file_max_bytes: int
    bots: tuple[str, ...]
    agent_files: tuple[AgentFileSpec, ...]
    business_types: frozenset[str]
    min_text_chars: int
    min_text_ratio: float
    shell_max_chars: int
    grades: tuple[tuple[int, str], ...]
    checks: tuple[CheckSpec, ...]


@lru_cache(maxsize=1)
def load_config() -> DiagnosticsConfig:
    path = Path(__file__).with_name("config.yaml")
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    text = raw.get("text") or {}
    return DiagnosticsConfig(
        user_agent=str(raw.get("user_agent") or ""),
        timeout_seconds=float(raw.get("timeout_seconds") or 15),
        max_bytes=int(raw.get("max_bytes") or 2_000_000),
        robots_max_bytes=int(raw.get("robots_max_bytes") or 200_000),
        agent_file_max_bytes=int(raw.get("agent_file_max_bytes") or 200_000),
        bots=tuple(str(item) for item in raw.get("bots") or []),
        agent_files=tuple(
            AgentFileSpec(
                key=str(item["key"]),
                path=str(item["path"]),
                label=str(item.get("label") or item["path"]),
                validator=str(item.get("validator") or "text"),
            )
            for item in raw.get("agent_files") or []
        ),
        business_types=frozenset(str(item) for item in raw.get("business_types") or []),
        min_text_chars=int(text.get("min_chars") or 500),
        min_text_ratio=float(text.get("min_ratio") or 0.01),
        shell_max_chars=int(text.get("shell_max_chars") or 300),
        grades=tuple(
            (int(item["min"]), str(item["grade"])) for item in raw.get("grades") or []
        ),
        checks=tuple(
            CheckSpec(
                key=str(item["key"]),
                label=str(item.get("label") or item["key"]),
                weight=int(item.get("weight") or 0),
                recommendation=str(item.get("recommendation") or ""),
            )
            for item in raw.get("checks") or []
        ),
    )
