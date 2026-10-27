"""Agent visibility diagnostics run against a mocked site without network."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from app.diagnostics.service import BlockedAddressError, InvalidTargetError, diagnose_url

FIXTURE = Path(__file__).resolve().parents[1] / "app" / "fixtures" / "aoba.html"
AOBAA_HTML = FIXTURE.read_text(encoding="utf-8")

JS_SHELL = """<!DOCTYPE html>
<html lang="en">
<head><title>App</title><script src="/app.js"></script></head>
<body><div id="root"></div><noscript>Enable JavaScript to view this site.</noscript></body>
</html>"""

BAD_ROBOTS = """User-agent: GPTBot
Disallow: /

User-agent: ClaudeBot
Disallow: /

User-agent: *
Allow: /
"""

GOOD_ROBOTS = "User-agent: *\nAllow: /\n"

UCP = {
    "ucp": {
        "version": "2026-08-25",
        "services": {"com.example.catalog": []},
    }
}

PUBLIC_ADDRESS = "93.184.216.34"


@pytest.fixture(autouse=True)
def _stub_dns(monkeypatch):
    monkeypatch.setattr(
        "app.diagnostics.service.resolve_host",
        lambda host: [PUBLIC_ADDRESS],
    )


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)


def _good_site(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if path == "/":
        return httpx.Response(200, text=AOBAA_HTML, headers={"content-type": "text/html; charset=utf-8"})
    if path == "/robots.txt":
        return httpx.Response(200, text=GOOD_ROBOTS)
    if path == "/llms.txt":
        return httpx.Response(200, text="# 青葉設計室\n\nサイト案内")
    if path == "/agents.md":
        return httpx.Response(200, text="# 青葉設計室\n\n問い合わせ方法")
    if path == "/.well-known/ucp":
        return httpx.Response(200, json=UCP)
    return httpx.Response(404, text="not found")


def _bad_site(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if path == "/":
        return httpx.Response(200, text=JS_SHELL, headers={"content-type": "text/html; charset=utf-8"})
    if path == "/robots.txt":
        return httpx.Response(200, text=BAD_ROBOTS)
    return httpx.Response(404, text="not found")


def test_good_site_scores_high():
    with _client(_good_site) as client:
        report = diagnose_url("https://good.example/", client=client)

    assert report["score"] >= 90
    assert report["grade"] in {"A", "B"}
    assert all(check["passed"] for check in report["checks"])
    assert report["structured_data"]["has_business_entity"] is True
    assert "ProfessionalService" in report["structured_data"]["types"]
    assert report["text"]["characters"] >= 500
    assert report["robots"]["disallowed_bots"] == []
    assert {item["key"] for item in report["agent_files"]} == {"llms_txt", "agents_md", "ucp"}
    assert all(item["present"] for item in report["agent_files"])


def test_js_shell_and_blocked_bots_score_low():
    with _client(_bad_site) as client:
        report = diagnose_url("https://bad.example/", client=client)

    assert report["score"] <= 25
    assert report["grade"] in {"D", "E"}
    assert report["text"]["js_shell"] is True
    bots = {item["name"]: item["allowed"] for item in report["robots"]["bots"]}
    assert bots["GPTBot"] is False
    assert bots["ClaudeBot"] is False
    assert set(report["robots"]["disallowed_bots"]) == {"GPTBot", "ClaudeBot"}
    assert any("GPTBot" in item and "ClaudeBot" in item for item in report["recommendations"])
    assert any(check["key"] == "readable_text" and not check["passed"] for check in report["checks"])


def test_robots_404_allows_every_bot():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/":
            return httpx.Response(200, text=AOBAA_HTML, headers={"content-type": "text/html; charset=utf-8"})
        return httpx.Response(404, text="not found")

    with _client(handler) as client:
        report = diagnose_url("https://no-robots.example/", client=client)

    assert report["robots"]["status"] == 404
    assert report["robots"]["disallowed_bots"] == []
    assert all(item["allowed"] for item in report["robots"]["bots"])


def test_non_http_scheme_is_rejected():
    with pytest.raises(InvalidTargetError):
        diagnose_url("ftp://example.com/")


def test_private_ip_is_rejected_by_default():
    with pytest.raises(BlockedAddressError):
        diagnose_url("http://127.0.0.1/")


def test_hostname_resolving_to_private_ip_is_rejected(monkeypatch):
    monkeypatch.setattr(
        "app.diagnostics.service.resolve_host",
        lambda host: ["10.0.0.5"],
    )

    with pytest.raises(BlockedAddressError):
        diagnose_url("https://internal.example/")


def test_redirect_to_private_ip_is_rejected():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/":
            return httpx.Response(302, headers={"location": "http://127.0.0.1/"})
        return httpx.Response(200, text=AOBAA_HTML, headers={"content-type": "text/html"})

    with _client(handler) as client:
        with pytest.raises(BlockedAddressError):
            diagnose_url("https://public.example/", client=client)


def test_private_ip_can_be_allowed_for_tests():
    with _client(_bad_site) as client:
        report = diagnose_url("http://127.0.0.1/", client=client, allow_private=True)

    assert report["url"] == "http://127.0.0.1/"
    assert report["score"] <= 25
