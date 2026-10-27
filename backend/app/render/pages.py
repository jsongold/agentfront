"""Jinja projections: HTML, Markdown, llms.txt, sitemap, robots, and the JSON feed."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.domain.catalog import BusinessCatalog
from app.render.jsonld import business_jsonld, offering_jsonld, work_jsonld
from app.render.ucp import conversion_label, conversion_target

TEMPLATES = Path(__file__).resolve().parents[1] / "templates"
env = Environment(loader=FileSystemLoader(TEMPLATES), autoescape=select_autoescape(["html"]))


def _pretty_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


env.filters["prettyjson"] = _pretty_json


def dumps(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False).replace("<", "\\u003c")


def _action_target(base: str, slug: str, point: dict[str, Any]) -> tuple[str, str]:
    return conversion_target(
        base,
        slug,
        conversion_type=point.get("type", ""),
        key=point["key"],
        external_url=point.get("external_url"),
    )


def view_business(catalog: BusinessCatalog, base: str) -> dict[str, Any]:
    data = catalog.model_dump(mode="json")
    data["html_url"] = f"{base}/b/{catalog.slug}"
    data["md_url"] = f"{base}/b/{catalog.slug}.md"
    data["feed_url"] = f"{base}/b/{catalog.slug}/feed.json"
    data["agents_md_url"] = f"{base}/b/{catalog.slug}/agents.md"
    data["ucp_url"] = f"{base}/b/{catalog.slug}/.well-known/ucp"
    for offering in data["offerings"]:
        offering["html_url"] = f"{base}/b/{catalog.slug}/o/{offering['slug']}"
        offering["md_url"] = offering["html_url"] + ".md"
    for work in data["works"]:
        work["html_url"] = f"{base}/b/{catalog.slug}/w/{work['slug']}"
        work["md_url"] = work["html_url"] + ".md"
    for point in data["conversion_points"]:
        point["action_url"], point["action_method"] = _action_target(base, catalog.slug, point)
    data["extension_json"] = dumps(catalog.extension)
    data["jsonld"] = dumps(business_jsonld(catalog, base))
    return data


def render_index(cards: list[dict[str, Any]], base: str) -> str:
    return env.get_template("index.html").render(businesses=cards, base=base)


def render_business(catalog: BusinessCatalog, base: str) -> str:
    return env.get_template("business.html").render(page=view_business(catalog, base), base=base)


def render_offering(catalog: BusinessCatalog, offering_slug: str, base: str) -> str | None:
    offering = next((item for item in catalog.offerings if item.slug == offering_slug), None)
    if offering is None:
        return None
    page = view_business(catalog, base)
    current = next(item for item in page["offerings"] if item["slug"] == offering_slug)
    current["jsonld"] = dumps(offering_jsonld(offering, base, catalog.slug))
    return env.get_template("offering.html").render(page=page, offering=current, base=base)


def render_work(catalog: BusinessCatalog, work_slug: str, base: str) -> str | None:
    work = next((item for item in catalog.works if item.slug == work_slug), None)
    if work is None:
        return None
    page = view_business(catalog, base)
    current = next(item for item in page["works"] if item["slug"] == work_slug)
    current["jsonld"] = dumps(work_jsonld(work, base, catalog.slug))
    return env.get_template("work.html").render(page=page, work=current, base=base)


def render_markdown(catalog: BusinessCatalog, base: str, *, offering_slug: str | None = None, work_slug: str | None = None) -> str | None:
    page = view_business(catalog, base)
    offering = None
    work = None
    if offering_slug:
        offering = next((item for item in page["offerings"] if item["slug"] == offering_slug), None)
        if offering is None:
            return None
    if work_slug:
        work = next((item for item in page["works"] if item["slug"] == work_slug), None)
        if work is None:
            return None
    return env.get_template("page.md.j2").render(page=page, offering=offering, work=work, base=base)


def render_agents_md(catalog: BusinessCatalog, base: str) -> str:
    return env.get_template("agents.md.j2").render(
        page=view_business(catalog, base),
        base=base,
        conversion_label=conversion_label,
    )


def render_site_agents_md(cards: list[dict[str, Any]], base: str) -> str:
    return env.get_template("agents_site.md.j2").render(businesses=cards, base=base)


def render_llms(cards: list[dict[str, Any]], base: str) -> str:
    return env.get_template("llms.txt.j2").render(businesses=cards, base=base)


def render_robots(base: str) -> str:
    lines = [
        "User-agent: *",
        "Allow: /",
        "",
        "User-agent: GPTBot",
        "Allow: /",
        "",
        "User-agent: OAI-SearchBot",
        "Allow: /",
        "",
        "User-agent: ChatGPT-User",
        "Allow: /",
        "",
        "User-agent: Google-Extended",
        "Allow: /",
        "",
        "User-agent: ClaudeBot",
        "Allow: /",
        "",
        "User-agent: Claude-User",
        "Allow: /",
        "",
        "User-agent: PerplexityBot",
        "Allow: /",
        "",
        "User-agent: Amazonbot",
        "Allow: /",
        "",
        "User-agent: CCBot",
        "Allow: /",
        "",
        f"Sitemap: {base}/sitemap.xml",
        "",
    ]
    return "\n".join(lines)


def render_sitemap(urls: list[str]) -> str:
    body = "\n".join(f"  <url><loc>{url}</loc></url>" for url in urls)
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{body}\n</urlset>\n'


def render_feed(catalogs: list[BusinessCatalog], base: str) -> dict[str, Any]:
    from datetime import datetime, timezone

    return {
        "version": "1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "businesses": [view_business(catalog, base) for catalog in catalogs],
    }
