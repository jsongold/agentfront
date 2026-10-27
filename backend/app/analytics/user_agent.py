"""Classify crawler and assistant user agents. Unknown browsers stay 'browser'."""

from __future__ import annotations

# Longer tokens first so "ChatGPT-User" is not swallowed by a shorter prefix.
_RULES: tuple[tuple[str, str], ...] = (
    ("OAI-SearchBot", "OAI-SearchBot"),
    ("ChatGPT-User", "ChatGPT-User"),
    ("GPTBot", "GPTBot"),
    ("Google-Extended", "Google-Extended"),
    ("Googlebot", "Googlebot"),
    ("Claude-User", "Claude-User"),
    ("ClaudeBot", "ClaudeBot"),
    ("anthropic-ai", "anthropic-ai"),
    ("Perplexity-User", "Perplexity-User"),
    ("PerplexityBot", "PerplexityBot"),
    ("Bingbot", "Bingbot"),
    ("Applebot", "Applebot"),
    ("Amazonbot", "Amazonbot"),
    ("Bytespider", "Bytespider"),
    ("CCBot", "CCBot"),
    ("Meta-ExternalAgent", "Meta-ExternalAgent"),
    ("FacebookBot", "FacebookBot"),
    ("YouBot", "YouBot"),
    ("cohere-ai", "cohere-ai"),
    ("DuckAssistBot", "DuckAssistBot"),
    ("MistralAI-User", "MistralAI-User"),
    ("Gemini", "Gemini"),
)


def classify_user_agent(user_agent: str | None) -> str:
    raw = user_agent or ""
    lowered = raw.lower()
    for token, label in _RULES:
        if token.lower() in lowered:
            return label
    if not raw.strip():
        return "unknown"
    if "mozilla/" in lowered and "bot" not in lowered and "spider" not in lowered:
        return "browser"
    if "bot" in lowered or "spider" in lowered or "crawler" in lowered:
        return "other-bot"
    return "other"
