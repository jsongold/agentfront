"""Fetch a target page and parse the signals used by the visibility score."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any
from urllib.robotparser import RobotFileParser

import httpx
from lxml import html as lhtml

from app.diagnostics.errors import BlockedAddressError
from app.diagnostics.report import (
    AgentFileInfo,
    BotAccess,
    FetchInfo,
    MetaInfo,
    RobotsInfo,
    StructuredDataInfo,
    TextInfo,
)
from app.diagnostics.spec import AgentFileSpec, DiagnosticsConfig

_TRACKED_SYNTAXES = ("json-ld", "microdata", "opengraph", "rdfa")
_TYPE_SYNTAXES = ("json-ld", "microdata", "rdfa")


@dataclass
class FetchResult:
    url: str
    final_url: str
    status: int | None
    content_type: str
    text: str
    size: int
    truncated: bool
    error: str | None

    @property
    def ok(self) -> bool:
        return self.status is not None and 200 <= self.status < 300


def fetch(
    client: httpx.Client,
    url: str,
    *,
    max_bytes: int,
    timeout_seconds: float,
    user_agent: str,
) -> FetchResult:
    headers = {
        "User-Agent": user_agent,
        "Accept": "text/html,application/xhtml+xml,application/json,text/plain,*/*",
    }
    try:
        with client.stream(
            "GET",
            url,
            headers=headers,
            follow_redirects=True,
            timeout=timeout_seconds,
        ) as response:
            chunks: list[bytes] = []
            total = 0
            truncated = False
            for chunk in response.iter_bytes():
                if not chunk:
                    continue
                remaining = max_bytes - total
                if remaining <= 0:
                    truncated = True
                    break
                if len(chunk) > remaining:
                    chunks.append(chunk[:remaining])
                    total += remaining
                    truncated = True
                    break
                chunks.append(chunk)
                total += len(chunk)
            raw = b"".join(chunks)
            return FetchResult(
                url=url,
                final_url=str(response.url),
                status=response.status_code,
                content_type=response.headers.get("content-type", ""),
                text=raw.decode("utf-8", errors="replace"),
                size=len(raw),
                truncated=truncated,
                error=None,
            )
    except BlockedAddressError:
        raise
    except Exception as exc:  # noqa: BLE001
        return FetchResult(
            url=url,
            final_url=url,
            status=None,
            content_type="",
            text="",
            size=0,
            truncated=False,
            error=str(exc),
        )


def fetch_info(result: FetchResult) -> FetchInfo:
    return FetchInfo(
        ok=result.ok,
        status=result.status,
        final_url=result.final_url,
        content_type=result.content_type,
        bytes=result.size,
        truncated=result.truncated,
        error=result.error,
    )


def parse_document(html: str):
    if not html.strip():
        return None
    try:
        return lhtml.fromstring(html)
    except Exception:  # noqa: BLE001
        return None


def extract_meta(document) -> MetaInfo:
    if document is None:
        return MetaInfo()
    title = _first(document.xpath("//title/text()"))
    description = ""
    fallback = ""
    for node in document.xpath("//meta"):
        name = (node.get("name") or node.get("property") or "").strip().lower()
        content = (node.get("content") or "").strip()
        if not content:
            continue
        if name == "description":
            description = content
            break
        if name == "og:description" and not fallback:
            fallback = content
    if not title:
        title = _first(document.xpath("//meta[translate(@property,'OG:TITLE','og:title')='og:title']/@content"))
    return MetaInfo(
        title=title,
        description=description or fallback,
        canonical=_first(document.xpath("//link[contains(translate(@rel,'CANONICAL','canonical'),'canonical')]/@href")),
        lang=_first(document.xpath("//html/@lang")),
    )


def extract_structured_data(html: str, base_url: str, config: DiagnosticsConfig) -> StructuredDataInfo:
    raw: dict[str, Any] = {}
    if html.strip():
        try:
            import extruct

            raw = extruct.extract(
                html,
                base_url=base_url,
                syntaxes=list(_TRACKED_SYNTAXES),
                uniform=False,
            )
        except Exception:  # noqa: BLE001
            raw = {}
    counts = {syntax: len(raw.get(syntax) or []) for syntax in _TRACKED_SYNTAXES}
    found: set[str] = set()
    for syntax in _TYPE_SYNTAXES:
        for item in raw.get(syntax) or []:
            _collect_types(item, found)
    business = sorted(item for item in found if item in config.business_types)
    return StructuredDataInfo(
        count=sum(counts[syntax] for syntax in _TYPE_SYNTAXES),
        types=sorted(found),
        business_types=business,
        has_business_entity=bool(business),
        syntax_counts=counts,
    )


def extract_text(html: str, url: str, document, config: DiagnosticsConfig) -> TextInfo:
    text = ""
    if html.strip():
        try:
            import trafilatura

            text = trafilatura.extract(
                html,
                url=url,
                include_comments=False,
                include_tables=True,
            ) or ""
        except Exception:  # noqa: BLE001
            text = ""
    text = text.strip()
    characters = len(text)
    words = len(text.split())
    raw_characters = _visible_text_length(document)
    ratio = round(characters / raw_characters, 4) if raw_characters else 0.0
    js_shell = _looks_like_shell(document, characters, config)
    warning = None
    if js_shell:
        warning = "本文がほとんどなく、JavaScriptで描画されるページの可能性があります。"
    return TextInfo(
        characters=characters,
        words=words,
        ratio=ratio,
        js_shell=js_shell,
        warning=warning,
    )


def fetch_robots(
    client: httpx.Client,
    origin: str,
    target_url: str,
    config: DiagnosticsConfig,
) -> RobotsInfo:
    robots_url = f"{origin}/robots.txt"
    result = fetch(
        client,
        robots_url,
        max_bytes=config.robots_max_bytes,
        timeout_seconds=config.timeout_seconds,
        user_agent=config.user_agent,
    )
    if result.status == 404:
        return RobotsInfo(
            url=robots_url,
            status=404,
            error=None,
            bots=[BotAccess(name=bot, allowed=True, detail="robots.txt なし（全許可）") for bot in config.bots],
            disallowed_bots=[],
        )
    if not result.ok or not result.text.strip():
        reason = result.error or (f"HTTP {result.status}" if result.status is not None else "取得できません")
        return RobotsInfo(
            url=robots_url,
            status=result.status,
            error=result.error,
            bots=[
                BotAccess(name=bot, allowed=True, detail=f"robots.txt を確認できないため許可として扱います（{reason}）")
                for bot in config.bots
            ],
            disallowed_bots=[],
        )
    parser = RobotFileParser()
    parser.parse(result.text.splitlines())
    bots: list[BotAccess] = []
    for bot in config.bots:
        try:
            allowed = parser.can_fetch(bot, target_url)
        except Exception:  # noqa: BLE001
            allowed = True
        bots.append(
            BotAccess(
                name=bot,
                allowed=allowed,
                detail="許可" if allowed else "拒否（Disallow 対象）",
            )
        )
    return RobotsInfo(
        url=robots_url,
        status=result.status,
        error=None,
        bots=bots,
        disallowed_bots=[item.name for item in bots if not item.allowed],
    )


def fetch_agent_files(
    client: httpx.Client,
    origin: str,
    config: DiagnosticsConfig,
) -> list[AgentFileInfo]:
    return [
        _fetch_agent_file(client, origin, spec, config)
        for spec in config.agent_files
    ]


def _fetch_agent_file(
    client: httpx.Client,
    origin: str,
    spec: AgentFileSpec,
    config: DiagnosticsConfig,
) -> AgentFileInfo:
    url = f"{origin}{spec.path}"
    result = fetch(
        client,
        url,
        max_bytes=config.agent_file_max_bytes,
        timeout_seconds=config.timeout_seconds,
        user_agent=config.user_agent,
    )
    present = False
    if result.status != 200:
        detail = f"HTTP {result.status}" if result.status is not None else (result.error or "取得できません")
    elif not result.text.strip():
        detail = "空のファイルです"
    elif spec.validator == "ucp":
        present, detail = _validate_ucp(result.text)
    else:
        present = True
        detail = f"{len(result.text.strip())}文字"
    return AgentFileInfo(
        key=spec.key,
        label=spec.label,
        path=spec.path,
        url=url,
        status=result.status,
        present=present,
        detail=detail,
    )


def _validate_ucp(text: str) -> tuple[bool, str]:
    try:
        data = json.loads(text)
    except Exception:  # noqa: BLE001
        return False, "JSONとして読み取れません"
    ucp = data.get("ucp") if isinstance(data, dict) else None
    if not isinstance(ucp, dict):
        return False, "ucp オブジェクトがありません"
    if not ucp.get("version"):
        return False, "ucp.version がありません"
    services = ucp.get("services")
    if not isinstance(services, dict):
        return False, "ucp.services がありません"
    return True, f"UCP {ucp.get('version')} / サービス {len(services)}件"


def _collect_types(value: Any, found: set[str]) -> None:
    if isinstance(value, dict):
        for key in ("@type", "type"):
            if key in value:
                _add_types(value[key], found)
        for key, nested in value.items():
            if key in ("@type", "type"):
                continue
            _collect_types(nested, found)
    elif isinstance(value, list):
        for item in value:
            _collect_types(item, found)


def _add_types(value: Any, found: set[str]) -> None:
    if isinstance(value, (list, tuple)):
        for item in value:
            _add_types(item, found)
        return
    if not isinstance(value, str):
        return
    name = value.strip().rsplit("/", 1)[-1].rsplit("#", 1)[-1]
    if ":" in name:
        name = name.rsplit(":", 1)[-1]
    if name:
        found.add(name)


def _visible_text_length(document) -> int:
    if document is None:
        return 0
    parts = document.xpath(
        "//body//text()[not(ancestor::script) and not(ancestor::style) and not(ancestor::noscript)]"
    )
    text = " ".join(str(part) for part in parts if isinstance(part, str))
    text = re.sub(r"\s+", " ", text).strip()
    return len(text)


def _looks_like_shell(document, characters: int, config: DiagnosticsConfig) -> bool:
    if document is None or characters > config.shell_max_chars:
        return False
    root = document.xpath('//*[@id="root" or @id="app" or @id="__next" or @id="__nuxt"]')
    noscript = document.xpath("//noscript")
    return bool(root or noscript)


def _first(values: Any) -> str:
    if not values:
        return ""
    return str(values[0]).strip()
