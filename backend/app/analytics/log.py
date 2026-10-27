"""Write touch logs. Failures here must not break the request they describe."""

from __future__ import annotations

import logging
from typing import Any

from app.analytics.user_agent import classify_user_agent
from app.db import session_scope
from app.models import McpCallLog, PageFetchLog

logger = logging.getLogger(__name__)


def log_page_fetch(path: str, user_agent: str, status_code: int) -> None:
    try:
        with session_scope() as session:
            session.add(
                PageFetchLog(
                    path=path[:2000],
                    user_agent=user_agent[:2000],
                    agent_class=classify_user_agent(user_agent),
                    status_code=status_code,
                )
            )
            session.commit()
    except Exception:  # noqa: BLE001
        logger.exception("page fetch log failed")


def log_mcp_call(
    tool_name: str,
    arguments: dict[str, Any],
    result_ids: list[str],
    agent_name: str = "",
    user_agent: str = "",
) -> None:
    try:
        with session_scope() as session:
            session.add(
                McpCallLog(
                    tool_name=tool_name,
                    arguments=_scrub(arguments),
                    result_ids=result_ids,
                    agent_name=(agent_name or "")[:200],
                    user_agent=(user_agent or "")[:2000],
                    agent_class=classify_user_agent(user_agent) if user_agent else (agent_name or "unknown"),
                )
            )
            session.commit()
    except Exception:  # noqa: BLE001
        logger.exception("mcp call log failed")


def _scrub(arguments: dict[str, Any]) -> dict[str, Any]:
    """Drop bulky free text from the log while keeping filters and ids."""
    cleaned: dict[str, Any] = {}
    for key, value in arguments.items():
        if key in {"payload", "request_text"} and isinstance(value, str) and len(value) > 500:
            cleaned[key] = value[:500] + "…"
        elif key == "payload" and isinstance(value, dict):
            cleaned[key] = {"keys": sorted(value.keys())}
        else:
            cleaned[key] = value
    return cleaned
