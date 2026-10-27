"""FastAPI application: operator API, agent pages, and MCP on one process."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.analytics.log import log_page_fetch
from app.api.routes import router as api_router
from app.config import get_settings, llm_key_status
from app.db import session_scope
from app.domain.validation import SchemaValidationError
from app.jobs import procrastinate_app
from app.mcp.server import mcp, streamable_app
from app.public.routes import router as public_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)

_PUBLIC_EXACT = {"/", "/robots.txt", "/sitemap.xml", "/llms.txt", "/agents.md", "/.well-known/ucp", "/feed.json"}

mcp_http = streamable_app()
session_manager = mcp._lowlevel_server.session_manager


@asynccontextmanager
async def lifespan(_app: FastAPI):
    procrastinate_app.open()
    try:
        async with session_manager.run():
            configured, _env_name, hint = llm_key_status()
            if not configured:
                logger.warning(hint)
            yield
    finally:
        procrastinate_app.close()


app = FastAPI(title="Agent catalog", lifespan=lifespan)
app.include_router(public_router)
app.include_router(api_router)

for route in mcp_http.routes:
    if getattr(route, "path", None) == "/mcp":
        app.router.routes.append(route)
        break


@app.exception_handler(SchemaValidationError)
async def schema_error(_request, exc: SchemaValidationError):
    return JSONResponse(status_code=422, content={"detail": exc.errors})


@app.get("/health")
def health() -> dict:
    db = "ok"
    try:
        with session_scope() as session:
            session.exec(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001
        db = f"error: {exc}"
    minio = "ok"
    try:
        from minio import Minio

        settings = get_settings()
        client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )
        if not client.bucket_exists(settings.minio_bucket):
            minio = "missing-bucket"
    except Exception as exc:  # noqa: BLE001
        minio = f"error: {exc}"
    configured, env_name, hint = llm_key_status()
    return {
        "status": "ok" if db == "ok" else "degraded",
        "database": db,
        "minio": minio,
        "llm_configured": configured,
        "llm_env": env_name,
        "llm_hint": hint,
    }


@app.middleware("http")
async def log_agent_pages(request, call_next):
    response = await call_next(request)
    path = request.url.path
    if request.method == "GET" and (path in _PUBLIC_EXACT or path.startswith("/b/")):
        log_page_fetch(path, request.headers.get("user-agent", ""), response.status_code)
    return response


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)
