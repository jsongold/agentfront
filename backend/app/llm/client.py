"""Provider-switchable structured calls. Missing keys raise a clear error.

The default target is OpenCode Go, an OpenAI-compatible chat endpoint. LiteLLM
is called as `openai/<model-id>` with `api_base` set. Every call sends a
User-Agent and `x-opencode-session` (required by OpenCode Go).
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from app.config import (
    get_settings,
    litellm_model_name,
    llm_key_status,
    resolve_llm_api_key,
    uses_openai_compatible_base,
)

logger = logging.getLogger(__name__)
PROMPTS = Path(__file__).resolve().parents[1] / "prompts"
USER_AGENT = "agentfront/0.1"

_session_id: ContextVar[str | None] = ContextVar("opencode_session_id", default=None)


class LLMNotConfigured(RuntimeError):
    pass


class SchemaProposal(BaseModel):
    action: str = Field(description="reuse, extend, or create")
    schema_key: str
    title: str
    description: str = ""
    document: dict[str, Any] = Field(description="JSON Schema draft 2020-12")
    rationale: str = ""


@contextmanager
def generation_llm_session(session_id: str | None = None) -> Iterator[str]:
    """One OpenCode session id for every LLM call in a generation job."""
    current = (session_id or "").strip() or str(uuid.uuid4())
    token = _session_id.set(current)
    try:
        yield current
    finally:
        _session_id.reset(token)


def current_session_id() -> str:
    current = _session_id.get()
    if current:
        return current
    return str(uuid.uuid4())


def opencode_headers(session_id: str | None = None) -> dict[str, str]:
    return {
        "User-Agent": USER_AGENT,
        "x-opencode-session": (session_id or current_session_id()).strip(),
    }


def litellm_kwargs(settings: Any | None = None, session_id: str | None = None) -> dict[str, Any]:
    """Arguments that must reach LiteLLM, including the OpenCode headers."""
    settings = settings or get_settings()
    key, _source = resolve_llm_api_key(settings)
    payload: dict[str, Any] = {
        "model": litellm_model_name(settings),
        "extra_headers": opencode_headers(session_id),
    }
    if uses_openai_compatible_base(settings):
        payload["api_base"] = settings.llm_api_base.strip().rstrip("/")
    if key:
        payload["api_key"] = key
    return payload


def load_prompt(name: str) -> str:
    return (PROMPTS / name).read_text(encoding="utf-8")


def render_prompt(name: str, **values: str) -> str:
    text = load_prompt(name)
    for key, value in values.items():
        text = text.replace("{{ " + key + " }}", value)
    return text


def _merge_headers(kwargs: dict[str, Any], session_id: str) -> dict[str, Any]:
    merged = dict(kwargs.get("extra_headers") or {})
    merged.update(opencode_headers(session_id))
    kwargs["extra_headers"] = merged
    return kwargs


def guarded_completion(**kwargs: Any) -> Any:
    """LiteLLM completion with the OpenCode session headers forced on."""
    from litellm import completion

    session_id = current_session_id()
    request = litellm_kwargs(session_id=session_id)
    kwargs["model"] = request["model"]
    if "api_base" in request:
        kwargs["api_base"] = request["api_base"]
    if "api_key" in request:
        kwargs["api_key"] = request["api_key"]
    _merge_headers(kwargs, session_id)
    return completion(**kwargs)


def _json_mode_rejected(exc: BaseException) -> bool:
    text = str(exc).lower()
    return any(token in text for token in ("response_format", "json_object", "json_schema", "json mode"))


def structured_call(response_model: type[BaseModel], system: str, user: str) -> Any:
    configured, _env_name, hint = llm_key_status()
    if not configured:
        raise LLMNotConfigured(hint)
    import instructor
    from instructor.v2.core.errors import InstructorRetryException

    modes = [instructor.Mode.JSON]
    if uses_openai_compatible_base():
        modes.append(instructor.Mode.TOOLS)
    else:
        modes = [instructor.Mode.TOOLS]
    last_error: BaseException | None = None
    for index, mode in enumerate(modes):
        client = instructor.from_litellm(guarded_completion, mode=mode)
        try:
            return client.chat.completions.create(
                model=litellm_model_name(),
                response_model=response_model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=0.2,
                max_retries=2,
                strict=False,
                extra_headers=opencode_headers(),
            )
        except InstructorRetryException:
            raise
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if index == 0 and len(modes) > 1 and _json_mode_rejected(exc):
                logger.warning("JSON mode was rejected by the endpoint; retrying with tools")
                continue
            raise
    if last_error is not None:
        raise last_error
    raise RuntimeError("structured call did not run")
