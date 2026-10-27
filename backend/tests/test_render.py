"""Agent pages are projections of the same catalog the admin edits."""

from __future__ import annotations

from app.render.pages import render_business, render_markdown
from app.seed import aoba_catalog
from app.services.persistence import prepare_catalog


def test_business_page_embeds_jsonld_and_markdown():
    catalog = prepare_catalog(aoba_catalog("http://localhost:8765"))
    html = render_business(catalog, "http://localhost:8765")
    assert "青葉設計室" in html
    assert "application/ld+json" in html
    assert "HomeAndConstructionBusiness" in html
    assert "AskAction" in html
    markdown = render_markdown(catalog, "http://localhost:8765")
    assert markdown is not None
    assert "custom-house" in markdown
    assert "floor_area_sqm" in markdown


def test_fixture_parse_reads_jsonld():
    from pathlib import Path

    from app.crawl.url_crawl import parse_document

    html = Path("app/fixtures/kogaku.html").read_bytes()
    parsed = parse_document("http://localhost:8765/fixtures/kogaku", html)
    assert parsed.ok
    assert "光枠" in (parsed.title + parsed.text)
    assert parsed.metadata.get("json-ld")
