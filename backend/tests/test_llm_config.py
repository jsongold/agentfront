"""OpenCode Go is the default generation endpoint, and the session header is required."""

from __future__ import annotations

from app.config import Settings, litellm_model_name, llm_key_status, uses_openai_compatible_base
from app.llm.client import USER_AGENT, generation_llm_session, guarded_completion, opencode_headers


def _settings(**overrides: str) -> Settings:
    values = {
        "llm_api_base": "https://opencode.ai/zen/go/v1",
        "llm_model": "deepseek-v4.1-flash",
        "llm_api_key": "",
        "opencode_api_key": "",
        "openai_api_key": "",
        "anthropic_api_key": "",
        "gemini_api_key": "",
    }
    values.update(overrides)
    return Settings(**values)


def test_defaults_point_at_opencode_go():
    assert Settings.model_fields["llm_api_base"].default == "https://opencode.ai/zen/go/v1"
    assert Settings.model_fields["llm_model"].default == "deepseek-v4.1-flash"


def test_custom_base_uses_openai_compatible_model_id():
    settings = _settings()
    assert uses_openai_compatible_base(settings)
    assert litellm_model_name(settings) == "openai/deepseek-v4.1-flash"
    prefixed = _settings(llm_model="openai/grok-4.7")
    assert litellm_model_name(prefixed) == "openai/grok-4.7"


def test_opencode_key_is_preferred_after_llm_api_key():
    from_opencode = _settings(opencode_api_key="oc-key")
    configured, source, hint = llm_key_status(from_opencode)
    assert configured and source == "OPENCODE_API_KEY" and hint == ""
    from_override = _settings(llm_api_key="explicit", opencode_api_key="oc-key")
    configured, source, _hint = llm_key_status(from_override)
    assert configured and source == "LLM_API_KEY"


def test_missing_key_names_opencode(monkeypatch):
    monkeypatch.delenv("OPENCODE_API_KEY", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    configured, source, hint = llm_key_status(_settings())
    assert not configured
    assert source == "OPENCODE_API_KEY"
    assert "OPENCODE_API_KEY" in hint
    assert "deepseek-v4.1-flash" in hint


def test_native_base_keeps_provider_prefix():
    settings = _settings(llm_api_base="native", llm_model="openai/gpt-4o-mini", openai_api_key="sk-test")
    assert not uses_openai_compatible_base(settings)
    assert litellm_model_name(settings) == "openai/gpt-4o-mini"
    configured, source, _hint = llm_key_status(settings)
    assert configured and source == "OPENAI_API_KEY"


def test_session_header_is_stable_for_a_job(monkeypatch):
    seen: list[dict[str, str]] = []

    def fake_completion(**kwargs):
        seen.append(dict(kwargs["extra_headers"]))
        return {"id": "test"}

    monkeypatch.setattr("litellm.completion", fake_completion)

    with generation_llm_session("job-session-1"):
        guarded_completion(messages=[])
        guarded_completion(messages=[])

    assert [item["x-opencode-session"] for item in seen] == ["job-session-1", "job-session-1"]
    assert all(item["User-Agent"] == USER_AGENT for item in seen)
    assert opencode_headers("job-session-1")["x-opencode-session"] == "job-session-1"
