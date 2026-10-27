"""Crawl, propose a vertical schema, extract a catalog, and leave it for review."""

from __future__ import annotations

import json
import logging
import uuid

from sqlmodel import select

from app.config import get_settings
from app.crawl.url_crawl import CrawlResult, fetch_url
from app.db import session_scope
from app.domain.catalog import BusinessCatalog
from app.domain.validation import SchemaValidationError
from app.llm.client import LLMNotConfigured, SchemaProposal, generation_llm_session, render_prompt, structured_call
from app.models import Business, CrawlDocument, GenerationRun, utcnow
from app.services.persistence import prepare_catalog, seal_catalog
from app.services.schemas import find_schema, latest_schemas, save_schema_version

logger = logging.getLogger(__name__)


def execute_generation(business_id: str) -> None:
    try:
        with generation_llm_session() as session_id:
            logger.info("generation llm session %s", session_id)
            _execute(uuid.UUID(business_id))
    except Exception as exc:
        _mark_failed(uuid.UUID(business_id), exc)
        raise


def _latest_run(session, business_id: uuid.UUID) -> GenerationRun | None:
    rows = session.exec(
        select(GenerationRun).where(GenerationRun.business_id == business_id).order_by(GenerationRun.created_at.desc())
    ).all()
    return rows[0] if rows else None


def _mark_failed(business_id: uuid.UUID, exc: Exception) -> None:
    message = str(exc) or exc.__class__.__name__
    if not isinstance(exc, LLMNotConfigured):
        message = f"生成に失敗しました: {message}"
    logger.exception("generation failed for %s", business_id)
    try:
        with session_scope() as session:
            business = session.get(Business, business_id)
            run = _latest_run(session, business_id)
            if run is not None and run.status in {"queued", "running"}:
                run.status = "failed"
                run.error = message
                run.finished_at = utcnow()
            if business is not None and business.status != "published":
                business.status = "failed"
            if business is not None:
                business.last_error = message
                business.updated_at = utcnow()
            session.commit()
    except Exception:
        logger.exception("could not record generation failure")


def _execute(business_id: uuid.UUID) -> None:
    with session_scope() as session:
        business = session.get(Business, business_id)
        if business is None:
            return
        run = _latest_run(session, business_id)
        if run is None or run.status not in {"queued", "running"}:
            run = GenerationRun(business_id=business.id, status="queued", step="queued", model=get_settings().llm_model)
            session.add(run)
            session.flush()
        run.status = "running"
        run.step = "crawl"
        run.error = None
        run.model = get_settings().llm_model
        if business.status != "published":
            business.status = "crawling"
        business.last_error = None
        session.commit()
        run_id = run.id

        results = _crawl(list(business.source_urls or []))
        for result in results:
            session.add(
                CrawlDocument(
                    business_id=business.id,
                    generation_run_id=run_id,
                    url=result.url,
                    ok=result.ok,
                    title=result.title[:500],
                    text=result.text[:50_000],
                    metadata_json=result.metadata or {},
                    error=result.error,
                )
            )
        session.commit()

        business = session.get(Business, business_id)
        assert business is not None
        packed = _pack(business.source_description or "", results)
        if len(packed.strip()) < 20:
            raise RuntimeError("取得できた文章がありません。URL と説明を確認してください。")

        run = session.get(GenerationRun, run_id)
        assert run is not None
        run.step = "propose_schema"
        if business.status != "published":
            business.status = "generating"
        session.commit()

        proposal = _propose(session, packed, business.source_description or "")
        schema_row = _schema_from_proposal(session, proposal)
        run = session.get(GenerationRun, run_id)
        assert run is not None
        run.schema_proposal = proposal.model_dump(mode="json")
        run.vertical_schema_id = schema_row.id
        run.step = "extract"
        session.commit()

        catalog, warning = _extract(packed, business.source_description or "", schema_row.json_schema)
        catalog.source_urls = list(business.source_urls or [])
        catalog.source_description = business.source_description or ""
        catalog.vertical_key = schema_row.key
        if not catalog.name:
            catalog.name = business.name
        if not catalog.images:
            images = []
            for result in results:
                images.extend(result.images)
            catalog.images = images[:6]
        catalog = prepare_catalog(catalog)

        run = session.get(GenerationRun, run_id)
        business = session.get(Business, business_id)
        assert run is not None and business is not None
        run.extracted = seal_catalog(catalog)
        run.status = "review"
        run.step = "done"
        run.error = warning
        run.finished_at = utcnow()
        if business.status != "published":
            business.status = "review"
            business.name = catalog.name
            business.summary = catalog.summary or business.summary
            business.vertical_key = schema_row.key
            business.vertical_schema_id = schema_row.id
        business.last_error = warning
        business.updated_at = utcnow()
        session.commit()


def _crawl(urls: list[str]) -> list[CrawlResult]:
    results: list[CrawlResult] = []
    for url in urls:
        cleaned = (url or "").strip()
        if not cleaned:
            continue
        try:
            results.append(fetch_url(cleaned))
        except Exception as exc:  # noqa: BLE001
            results.append(CrawlResult(url=cleaned, ok=False, error=str(exc)))
    return results


def _pack(description: str, results: list[CrawlResult]) -> str:
    parts = [f"## Operator description\n{description}".strip()]
    for result in results:
        if not result.ok and not result.text:
            parts.append(f"## URL {result.url}\nERROR: {result.error or 'fetch failed'}")
            continue
        meta = json.dumps(result.metadata, ensure_ascii=False, default=str)[:2500]
        parts.append(f"## URL {result.url}\nTITLE: {result.title}\nJSON-LD/OGP:\n{meta}\n\nTEXT:\n{result.text[:5000]}")
    return "\n\n".join(parts)[:16_000]


def _propose(session, packed: str, description: str) -> SchemaProposal:
    existing = [
        {
            "key": row.key,
            "version": row.version,
            "title": row.title,
            "description": row.description,
            "document": row.json_schema,
        }
        for row in latest_schemas(session)
    ]
    user = render_prompt(
        "propose_schema.md",
        existing=json.dumps(existing, ensure_ascii=False)[:12_000],
        description=description,
        sources=packed,
    )
    proposal = structured_call(
        SchemaProposal,
        "You propose a JSON Schema for one business vertical. Answer with the structured object only.",
        user,
    )
    action = (proposal.action or "").strip().lower()
    proposal.action = action if action in {"reuse", "extend", "create"} else "create"
    return proposal


def _schema_from_proposal(session, proposal: SchemaProposal):
    if proposal.action == "reuse":
        found = find_schema(session, proposal.schema_key)
        if found is not None:
            return found
    document = proposal.document or {"type": "object", "additionalProperties": False, "properties": {}}
    return save_schema_version(
        session,
        key=proposal.schema_key,
        title=proposal.title,
        description=proposal.description,
        document=document,
    )


def _extract(packed: str, description: str, schema: dict, retry_note: str = "") -> tuple[BusinessCatalog, str | None]:
    user = render_prompt(
        "extract_catalog.md",
        schema=json.dumps(schema, ensure_ascii=False)[:8_000],
        description=description,
        sources=packed,
        retry_note=retry_note,
    )
    catalog = structured_call(
        BusinessCatalog,
        "You extract a factual business catalog for AI agents. Do not invent facts.",
        user,
    )
    if not isinstance(catalog, BusinessCatalog):
        catalog = BusinessCatalog.model_validate(catalog)
    try:
        prepare_catalog(catalog)
        from app.domain.validation import validate_catalog_extensions

        validate_catalog_extensions(schema, catalog)
        return catalog, None
    except SchemaValidationError as exc:
        if retry_note:
            note = "拡張データの検証エラーがあります。直してから公開してください。\n" + "\n".join(exc.errors)
            return catalog, note
        return _extract(
            packed,
            description,
            schema,
            retry_note="The previous output failed schema validation:\n"
            + "\n".join(exc.errors)
            + "\nReturn corrected extension objects.",
        )
