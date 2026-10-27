"""Adapter interface shared by internal store, email, and webhook."""

from __future__ import annotations

from typing import Any, Protocol

from pydantic import BaseModel, Field


class DeliveryContext(BaseModel):
    conversion_id: str
    business_id: str
    business_name: str
    business_slug: str
    conversion_point_id: str
    conversion_type: str
    conversion_name: str
    payload: dict[str, Any]
    agent_name: str = ""
    request_text: str = ""
    config: dict[str, Any] = Field(default_factory=dict)


class DeliveryResult(BaseModel):
    status: str
    detail: str = ""


class Adapter(Protocol):
    key: str
    title: str

    def config_schema(self) -> dict[str, Any]: ...

    def send(self, ctx: DeliveryContext) -> DeliveryResult: ...

    def status(self, external_id: str) -> str: ...
