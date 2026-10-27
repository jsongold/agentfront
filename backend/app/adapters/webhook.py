"""JSON webhook adapter with retries."""

from __future__ import annotations

from typing import Any

import httpx
import pluggy
from tenacity import retry, stop_after_attempt, wait_exponential

from app.adapters.base import DeliveryContext, DeliveryResult

hookimpl = pluggy.HookimplMarker("agentfront")


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=0.2, min=0.2, max=2), reraise=True)
def post_json(url: str, body: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
    with httpx.Client(timeout=10) as client:
        response = client.post(url, json=body, headers=headers)
        response.raise_for_status()
        if not response.content:
            return {"status_code": response.status_code}
        try:
            parsed = response.json()
        except Exception:  # noqa: BLE001
            return {"status_code": response.status_code}
        return parsed if isinstance(parsed, dict) else {"status_code": response.status_code}


class WebhookAdapter:
    key = "webhook"
    title = "Webhook"

    def config_schema(self) -> dict:
        return {
            "type": "object",
            "title": "Webhook",
            "additionalProperties": False,
            "required": ["url"],
            "properties": {
                "url": {"type": "string", "title": "送信先URL"},
                "bearer_token": {"type": "string", "title": "Bearerトークン"},
            },
        }

    def send(self, ctx: DeliveryContext) -> DeliveryResult:
        url = str(ctx.config.get("url") or "").strip()
        if not url:
            raise ValueError("webhook adapter requires config.url")
        headers = {"Content-Type": "application/json", "User-Agent": "agentfront/0.1"}
        token = str(ctx.config.get("bearer_token") or "").strip()
        if token:
            headers["Authorization"] = f"Bearer {token}"
        body = {
            "conversion_id": ctx.conversion_id,
            "business_id": ctx.business_id,
            "business_slug": ctx.business_slug,
            "business_name": ctx.business_name,
            "conversion_point_id": ctx.conversion_point_id,
            "conversion_type": ctx.conversion_type,
            "conversion_name": ctx.conversion_name,
            "agent_name": ctx.agent_name,
            "request_text": ctx.request_text,
            "payload": ctx.payload,
        }
        post_json(url, body, headers)
        return DeliveryResult(status="sent", detail=url)

    def status(self, external_id: str) -> str:
        return "sent"


class WebhookPlugin:
    @hookimpl
    def catalog_adapter(self) -> WebhookAdapter:
        return WebhookAdapter()


def plugin() -> WebhookPlugin:
    return WebhookPlugin()
