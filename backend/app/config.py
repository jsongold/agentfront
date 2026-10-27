"""Runtime configuration. The process boots without an LLM key."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Dev-only Fernet key. docker-compose uses the same default so local data
# survives a restart. Production must override CREDENTIALS_KEY.
DEV_CREDENTIALS_KEY = "7mJHRuAJVVlLkUino67I2-wRhTFJdNBzbKKctA5HWgo="

# OpenCode Go is an OpenAI-compatible chat API. The inference host is the same service.
OPENCODE_GO_API_BASE = "https://opencode.ai/zen/go/v1"
OPENCODE_GO_API_BASE_ALIAS = "https://opencode.ai/inference/go/openai/v1"
DEFAULT_LLM_MODEL = "deepseek-v4.1-flash"

# These values mean "do not send api_base; let LiteLLM pick the provider from the model name".
_NATIVE_BASES = {"", "native", "off", "default", "litellm"}

_PROVIDER_ENV = (
    ("openai/", "OPENAI_API_KEY"),
    ("anthropic/", "ANTHROPIC_API_KEY"),
    ("gemini/", "GEMINI_API_KEY"),
    ("google/", "GEMINI_API_KEY"),
    ("vertex_ai/", "GOOGLE_APPLICATION_CREDENTIALS"),
    ("groq/", "GROQ_API_KEY"),
    ("mistral/", "MISTRAL_API_KEY"),
    ("openrouter/", "OPENROUTER_API_KEY"),
    ("deepseek/", "DEEPSEEK_API_KEY"),
    ("cohere/", "COHERE_API_KEY"),
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://catalog:catalog@localhost:54329/catalog"
    public_base_url: str = "http://localhost:8765"
    internal_base_url: str = "http://localhost:8765"

    minio_endpoint: str = "localhost:19000"
    minio_access_key: str = "catalog"
    minio_secret_key: str = "catalogsecret"
    minio_bucket: str = "catalog-media"
    minio_secure: bool = False

    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_from: str = "catalog@localhost"

    credentials_key: str = DEV_CREDENTIALS_KEY
    admin_token: str = ""

    # OpenAI-compatible base. "native" uses LiteLLM's own provider routing.
    llm_api_base: str = OPENCODE_GO_API_BASE
    llm_api_key: str = ""
    opencode_api_key: str = ""
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    gemini_api_key: str = ""
    llm_model: str = DEFAULT_LLM_MODEL
    # auto | crawl4ai | trafilatura. auto uses Crawl4AI when the extra is installed.
    crawl_backend: str = "auto"
    diagnostics_allow_private: bool = False

    @property
    def psycopg_conninfo(self) -> str:
        url = self.database_url
        return url.replace("postgresql+psycopg://", "postgresql://", 1).replace(
            "postgres+psycopg://", "postgresql://", 1
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


def uses_openai_compatible_base(settings: Settings | None = None) -> bool:
    settings = settings or get_settings()
    return settings.llm_api_base.strip().lower() not in _NATIVE_BASES


def _nonempty(*values: str) -> str:
    for value in values:
        text = (value or "").strip()
        if text:
            return text
    return ""


def provider_env_name(model: str) -> str:
    for prefix, name in _PROVIDER_ENV:
        if model.startswith(prefix):
            return name
    return "OPENAI_API_KEY"


def resolve_llm_api_key(settings: Settings | None = None) -> tuple[str, str]:
    """Return (api key, env var that supplied it or the one the operator should set)."""
    settings = settings or get_settings()
    if _nonempty(settings.llm_api_key):
        return settings.llm_api_key.strip(), "LLM_API_KEY"
    if uses_openai_compatible_base(settings):
        base = settings.llm_api_base.lower()
        if "api.openai.com" in base and _nonempty(settings.openai_api_key):
            return settings.openai_api_key.strip(), "OPENAI_API_KEY"
        if _nonempty(settings.opencode_api_key):
            return settings.opencode_api_key.strip(), "OPENCODE_API_KEY"
        return "", "OPENCODE_API_KEY"
    env_name = provider_env_name(settings.llm_model.strip())
    field = env_name.lower()
    value = _nonempty(str(getattr(settings, field, "") or ""))
    return value, env_name


def litellm_model_name(settings: Settings | None = None) -> str:
    """LiteLLM model. A custom base is called as an OpenAI-compatible client."""
    settings = settings or get_settings()
    model = settings.llm_model.strip() or DEFAULT_LLM_MODEL
    if not uses_openai_compatible_base(settings):
        return model
    model_id = model.split("/", 1)[1] if "/" in model else model
    return f"openai/{model_id}"


def llm_key_status(settings: Settings | None = None) -> tuple[bool, str, str]:
    """Return (configured, env var name, operator-facing hint)."""
    settings = settings or get_settings()
    key, env_name = resolve_llm_api_key(settings)
    if key:
        return True, env_name, ""
    model = settings.llm_model.strip() or DEFAULT_LLM_MODEL
    if uses_openai_compatible_base(settings):
        hint = (
            f"LLMのAPIキーが未設定です。OpenCode Go（{settings.llm_api_base}）のモデル {model} には"
            "環境変数 OPENCODE_API_KEY（または LLM_API_KEY）が必要です。"
            "キーを設定して backend と worker を再起動すると生成できます。アプリ自体は起動しています。"
        )
        return False, env_name, hint
    hint = (
        f"LLMのAPIキーが未設定です。モデル {model} には環境変数 {env_name} が必要です。"
        "キーを設定して backend と worker を再起動すると生成できます。アプリ自体は起動しています。"
    )
    return False, env_name, hint
