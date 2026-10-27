"""Record-only adapter. The conversion row itself is the store."""

from __future__ import annotations

import pluggy

from app.adapters.base import DeliveryContext, DeliveryResult

hookimpl = pluggy.HookimplMarker("agentfront")


class InternalAdapter:
    key = "internal"
    title = "内部記録"

    def config_schema(self) -> dict:
        return {
            "type": "object",
            "title": "内部記録",
            "additionalProperties": False,
            "properties": {},
        }

    def send(self, ctx: DeliveryContext) -> DeliveryResult:
        return DeliveryResult(status="stored", detail="conversion stored")

    def status(self, external_id: str) -> str:
        return "stored"


class InternalPlugin:
    @hookimpl
    def catalog_adapter(self) -> InternalAdapter:
        return InternalAdapter()


def plugin() -> InternalPlugin:
    return InternalPlugin()
