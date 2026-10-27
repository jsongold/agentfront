"""Typed shape of an agent visibility report."""

from __future__ import annotations

from pydantic import BaseModel, Field


class CheckResult(BaseModel):
    key: str
    label: str
    passed: bool
    weight: int
    detail: str


class FetchInfo(BaseModel):
    ok: bool
    status: int | None = None
    final_url: str = ""
    content_type: str = ""
    bytes: int = 0
    truncated: bool = False
    error: str | None = None


class MetaInfo(BaseModel):
    title: str = ""
    description: str = ""
    canonical: str = ""
    lang: str = ""


class StructuredDataInfo(BaseModel):
    count: int = 0
    types: list[str] = Field(default_factory=list)
    business_types: list[str] = Field(default_factory=list)
    has_business_entity: bool = False
    syntax_counts: dict[str, int] = Field(default_factory=dict)


class TextInfo(BaseModel):
    characters: int = 0
    words: int = 0
    ratio: float = 0.0
    js_shell: bool = False
    warning: str | None = None


class BotAccess(BaseModel):
    name: str
    allowed: bool
    detail: str


class RobotsInfo(BaseModel):
    url: str
    status: int | None = None
    error: str | None = None
    bots: list[BotAccess] = Field(default_factory=list)
    disallowed_bots: list[str] = Field(default_factory=list)


class AgentFileInfo(BaseModel):
    key: str
    label: str
    path: str
    url: str
    status: int | None = None
    present: bool = False
    detail: str = ""


class DiagnosticReport(BaseModel):
    url: str
    final_url: str
    score: int
    grade: str
    checks: list[CheckResult] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    fetch: FetchInfo
    meta: MetaInfo
    structured_data: StructuredDataInfo
    text: TextInfo
    robots: RobotsInfo
    agent_files: list[AgentFileInfo] = Field(default_factory=list)
