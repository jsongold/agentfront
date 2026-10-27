"""SMTP adapter. Local compose routes this to Mailpit."""

from __future__ import annotations

import json
import smtplib
from email.message import EmailMessage

import pluggy

from app.adapters.base import DeliveryContext, DeliveryResult
from app.config import get_settings

hookimpl = pluggy.HookimplMarker("agentfront")


class EmailAdapter:
    key = "email"
    title = "メール"

    def config_schema(self) -> dict:
        return {
            "type": "object",
            "title": "メール送信",
            "additionalProperties": False,
            "required": ["to"],
            "properties": {
                "to": {"type": "string", "format": "email", "title": "送信先"},
                "subject_prefix": {
                    "type": "string",
                    "title": "件名の接頭辞",
                    "default": "[カタログ]",
                },
            },
        }

    def send(self, ctx: DeliveryContext) -> DeliveryResult:
        settings = get_settings()
        recipient = str(ctx.config.get("to") or "").strip()
        if not recipient:
            raise ValueError("email adapter requires config.to")
        prefix = str(ctx.config.get("subject_prefix") or "[カタログ]")
        message = EmailMessage()
        message["Subject"] = f"{prefix} {ctx.business_name} / {ctx.conversion_name}"
        message["From"] = settings.smtp_from
        message["To"] = recipient
        body = "\n".join(
            [
                f"事業者: {ctx.business_name} ({ctx.business_slug})",
                f"コンバージョン: {ctx.conversion_name} ({ctx.conversion_type})",
                f"エージェント: {ctx.agent_name or '不明'}",
                "",
                "依頼文:",
                ctx.request_text or "（なし）",
                "",
                "入力:",
                json.dumps(ctx.payload, ensure_ascii=False, indent=2),
            ]
        )
        message.set_content(body)
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
            smtp.send_message(message)
        return DeliveryResult(status="sent", detail=f"smtp {recipient}")

    def status(self, external_id: str) -> str:
        return "sent"


class EmailPlugin:
    @hookimpl
    def catalog_adapter(self) -> EmailAdapter:
        return EmailAdapter()


def plugin() -> EmailPlugin:
    return EmailPlugin()
