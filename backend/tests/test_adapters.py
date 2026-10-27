"""Adapter plugins fan out, and one failure does not cancel the others."""

from __future__ import annotations

import pytest

from app.adapters.base import DeliveryContext
from app.adapters.dispatch import dispatch
from app.adapters.registry import adapter_map
from app.crypto import decrypt_json, encrypt_json
from app.domain.catalog import AdapterBinding


def _context() -> DeliveryContext:
    return DeliveryContext(
        conversion_id="c1",
        business_id="b1",
        business_name="青葉設計室",
        business_slug="aoba-sekkei",
        conversion_point_id="p1",
        conversion_type="quote_request",
        conversion_name="見積",
        payload={"name": "田中", "email": "tanaka@example.com"},
        agent_name="test-agent",
        request_text="木造で相談したい",
    )


def test_registry_exposes_mvp_adapters():
    assert {"internal", "email", "webhook"} <= set(adapter_map())


def test_credentials_roundtrip_does_not_store_plaintext():
    token = encrypt_json({"bearer_token": "abc"})
    assert "abc" not in token
    assert decrypt_json(token)["bearer_token"] == "abc"


def test_dispatch_fans_out(monkeypatch: pytest.MonkeyPatch):
    sent: dict = {}

    class DummySMTP:
        def __init__(self, host, port, timeout=None):
            sent["smtp"] = (host, port)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def send_message(self, message):
            sent["message"] = message

    def fake_post(url, body, headers):
        sent["webhook"] = (url, body, headers)
        return {"ok": True}

    monkeypatch.setattr("app.adapters.email.smtplib.SMTP", DummySMTP)
    monkeypatch.setattr("app.adapters.webhook.post_json", fake_post)
    results = dispatch(
        [
            AdapterBinding(key="internal"),
            AdapterBinding(key="email", config={"to": "owner@example.com"}),
            AdapterBinding(key="webhook", config={"url": "http://example.test/hook", "bearer_token": "s3cret"}),
        ],
        _context(),
    )
    assert [item.status for _, item in results] == ["stored", "sent", "sent"]
    assert sent["webhook"][2]["Authorization"] == "Bearer s3cret"
    assert "木造で相談したい" in sent["message"].get_content()


def test_dispatch_continues_after_email_failure(monkeypatch: pytest.MonkeyPatch):
    class BrokenSMTP:
        def __init__(self, *args, **kwargs):
            raise OSError("smtp down")

    monkeypatch.setattr("app.adapters.email.smtplib.SMTP", BrokenSMTP)
    monkeypatch.setattr("app.adapters.webhook.post_json", lambda url, body, headers: {"ok": True})
    results = dispatch(
        [
            AdapterBinding(key="internal"),
            AdapterBinding(key="email", config={"to": "owner@example.com"}),
            AdapterBinding(key="webhook", config={"url": "http://example.test/hook"}),
            AdapterBinding(key="missing"),
        ],
        _context(),
    )
    assert [item.status for _, item in results] == ["stored", "failed", "sent", "failed"]


def test_user_agent_classification():
    from app.analytics.user_agent import classify_user_agent

    assert classify_user_agent("Mozilla/5.0 GPTBot/1.0") == "GPTBot"
    assert classify_user_agent("Mozilla/5.0 ChatGPT-User") == "ChatGPT-User"
    assert classify_user_agent("ClaudeBot") == "ClaudeBot"
    assert classify_user_agent("PerplexityBot/1.0") == "PerplexityBot"
    assert classify_user_agent("Mozilla/5.0 (Macintosh) AppleWebKit/605") == "browser"
