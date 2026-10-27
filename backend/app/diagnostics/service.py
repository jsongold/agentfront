"""Run an agent visibility diagnostic for one public URL."""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

import httpx

from app.config import get_settings
from app.diagnostics.errors import BlockedAddressError, InvalidTargetError
from app.diagnostics.extract import (
    FetchResult,
    extract_meta,
    extract_structured_data,
    extract_text,
    fetch,
    fetch_agent_files,
    fetch_info,
    fetch_robots,
    parse_document,
)
from app.diagnostics.report import (
    AgentFileInfo,
    CheckResult,
    DiagnosticReport,
    MetaInfo,
    RobotsInfo,
    StructuredDataInfo,
    TextInfo,
)
from app.diagnostics.spec import CheckSpec, DiagnosticsConfig, load_config


def resolve_host(host: str) -> list[str]:
    """Return every address the system resolves for ``host``.

    Kept at module level so tests can replace it (or ``socket.getaddrinfo``)
    without making real DNS queries.
    """
    return [str(info[4][0]) for info in socket.getaddrinfo(host, None)]


def diagnose_url(
    url: str,
    *,
    client: httpx.Client | None = None,
    allow_private: bool | None = None,
) -> dict:
    config = load_config()
    settings = get_settings()
    allowed = settings.diagnostics_allow_private if allow_private is None else allow_private
    target = validate_url(url, allow_private=allowed)
    parsed = urlparse(target)
    origin = f"{parsed.scheme}://{parsed.netloc}"

    own_client = client is None
    if own_client:
        client = httpx.Client(follow_redirects=True)
    _install_request_guard(client, allow_private=allowed)
    try:
        page = fetch(
            client,
            target,
            max_bytes=config.max_bytes,
            timeout_seconds=config.timeout_seconds,
            user_agent=config.user_agent,
        )
        document = parse_document(page.text) if page.ok else None
        meta = extract_meta(document)
        structured = extract_structured_data(page.text, page.final_url or target, config)
        text = extract_text(page.text, page.final_url or target, document, config)
        robots = fetch_robots(client, origin, target, config)
        agent_files = fetch_agent_files(client, origin, config)
    finally:
        if own_client:
            client.close()

    report = _build_report(
        config,
        target,
        page=page,
        meta=meta,
        structured=structured,
        text=text,
        robots=robots,
        agent_files=agent_files,
    )
    return report.model_dump(mode="json")


def validate_url(url: str, *, allow_private: bool) -> str:
    text = (url or "").strip()
    if not text:
        raise InvalidTargetError("URLを入力してください")
    parsed = urlparse(text)
    if parsed.scheme not in {"http", "https"}:
        raise InvalidTargetError("URLは http:// または https:// で始めてください")
    host = parsed.hostname
    if not host:
        raise InvalidTargetError("URLにホスト名がありません")
    if not allow_private:
        _check_public_host(host)
    return text


def _install_request_guard(client: httpx.Client, *, allow_private: bool) -> None:
    """Check every request, including redirect hops and secondary fetches."""

    def guard(request: httpx.Request) -> None:
        validate_url(str(request.url), allow_private=allow_private)

    guard._agentfront_ssrf_guard = True  # type: ignore[attr-defined]
    hooks = [
        hook
        for hook in client.event_hooks.get("request", [])
        if not getattr(hook, "_agentfront_ssrf_guard", False)
    ]
    hooks.append(guard)
    client.event_hooks["request"] = hooks


def _check_public_host(host: str) -> None:
    lowered = host.strip().strip("[]").lower().rstrip(".")
    if lowered == "localhost" or lowered.endswith(".localhost"):
        raise BlockedAddressError("ローカルまたはプライベートなアドレスは診断できません")
    try:
        literal = ipaddress.ip_address(lowered)
    except ValueError:
        try:
            addresses = resolve_host(lowered)
        except OSError as exc:
            raise BlockedAddressError("ホスト名を解決できません") from exc
        if not addresses:
            raise BlockedAddressError("ホスト名を解決できません")
        for raw in addresses:
            try:
                address = ipaddress.ip_address(raw.split("%", 1)[0])
            except ValueError:
                continue
            if _is_blocked_address(address):
                raise BlockedAddressError("ローカルまたはプライベートなアドレスは診断できません")
        return
    if _is_blocked_address(literal):
        raise BlockedAddressError("ローカルまたはプライベートなアドレスは診断できません")


def _is_blocked_address(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return any(
        (
            address.is_private,
            address.is_loopback,
            address.is_link_local,
            address.is_reserved,
            address.is_multicast,
            address.is_unspecified,
        )
    )


def _build_report(
    config: DiagnosticsConfig,
    target: str,
    *,
    page: FetchResult,
    meta: MetaInfo,
    structured: StructuredDataInfo,
    text: TextInfo,
    robots: RobotsInfo,
    agent_files: list[AgentFileInfo],
) -> DiagnosticReport:
    files = {item.key: item for item in agent_files}
    disallowed = robots.disallowed_bots
    jsonld_count = structured.syntax_counts.get("json-ld", 0)
    text_ok = (
        text.characters >= config.min_text_chars
        and text.ratio >= config.min_text_ratio
        and not text.js_shell
    )
    outcomes = {
        "reachable": (
            page.ok,
            f"HTTP {page.status} / {page.size} bytes" if page.status is not None else (page.error or "取得できません"),
        ),
        "robots_ai": (
            bool(robots.bots) and not disallowed,
            _robots_detail(robots),
        ),
        "structured_data": (
            jsonld_count > 0,
            f"JSON-LD {jsonld_count}件 / 構造化データ {structured.count}件 / 型 {len(structured.types)}種",
        ),
        "business_entity": (
            structured.has_business_entity,
            "、".join(structured.business_types) if structured.business_types else "該当する型がありません",
        ),
        "readable_text": (
            text_ok,
            f"{text.characters}文字（{text.words}語、本文比率 {text.ratio:.1%}）",
        ),
        "meta": (
            bool(meta.title and meta.description),
            f"title: {'あり' if meta.title else 'なし'} / description: {'あり' if meta.description else 'なし'}",
        ),
        "llms_txt": _file_outcome(files, "llms_txt"),
        "agents_md": _file_outcome(files, "agents_md"),
        "ucp": _file_outcome(files, "ucp"),
    }

    checks: list[CheckResult] = []
    recommendations: list[str] = []
    earned = 0
    total = 0
    for spec in config.checks:
        passed, detail = outcomes.get(spec.key, (False, "未評価"))
        checks.append(
            CheckResult(
                key=spec.key,
                label=spec.label,
                passed=passed,
                weight=spec.weight,
                detail=detail,
            )
        )
        total += spec.weight
        if passed:
            earned += spec.weight
        else:
            recommendations.append(_recommendation(spec, disallowed))

    score = round(earned / total * 100) if total else 0
    return DiagnosticReport(
        url=target,
        final_url=page.final_url or target,
        score=score,
        grade=_grade(score, config),
        checks=checks,
        recommendations=recommendations,
        fetch=fetch_info(page),
        meta=meta,
        structured_data=structured,
        text=text,
        robots=robots,
        agent_files=agent_files,
    )


def _file_outcome(files: dict[str, AgentFileInfo], key: str) -> tuple[bool, str]:
    item = files.get(key)
    if item is None:
        return False, "確認していません"
    return item.present, item.detail


def _robots_detail(robots: RobotsInfo) -> str:
    if robots.status == 404:
        return "robots.txt なし（全許可）"
    if robots.status is None or robots.error:
        return robots.error or "robots.txt を取得できません"
    allowed = sum(1 for item in robots.bots if item.allowed)
    total = len(robots.bots)
    if robots.disallowed_bots:
        return f"{allowed}/{total} 許可 / 拒否: {'、'.join(robots.disallowed_bots)}"
    return f"{allowed}/{total} 許可"


def _recommendation(spec: CheckSpec, disallowed: list[str]) -> str:
    bots = "、".join(disallowed) if disallowed else "一部のAIクローラ"
    return spec.recommendation.replace("{bots}", bots)


def _grade(score: int, config: DiagnosticsConfig) -> str:
    for minimum, grade in config.grades:
        if score >= minimum:
            return grade
    return config.grades[-1][1] if config.grades else "E"
