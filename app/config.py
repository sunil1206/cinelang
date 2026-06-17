from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ── App ──────────────────────────────────────────────────────────────────
    app_name: str    = "CineLang API"
    app_version: str = "3.0.0"
    debug: bool      = False

    # ── Database ─────────────────────────────────────────────────────────────
    db_path: str = "cinelang.db"

    @property
    def database_url(self) -> str:
        return f"sqlite:///{self.db_path}"

    # ── Redis ─────────────────────────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379/0"
    cache_ttl_seconds: int = 86400        # 24 h default

    # ── JWT ───────────────────────────────────────────────────────────────────
    jwt_secret: str               = "change-me-in-production"
    jwt_algorithm: str            = "HS256"
    access_token_expire_minutes: int  = 60 * 24
    refresh_token_expire_days: int    = 30

    # ── Google OAuth ──────────────────────────────────────────────────────────
    google_client_id: str = ""

    # ── AI Provider 0: Anthropic Claude Haiku (PRIMARY) ─────────────────────
    anthropic_api_key: str = ""

    # ── AI Provider 1: OpenAI gpt-4o-mini ───────────────────────────────────
    openai_api_key: str = ""

    # ── AI Provider 1: Groq (PRIMARY) ─────────────────────────────────────────
    groq_api_key: str   = ""
    groq_model: str     = "llama-3.3-70b-versatile"
    groq_timeout: int   = 8

    # ── AI Provider 1: Gemini 2.5 Flash (PRIMARY) ────────────────────────────
    gemini_api_key: str = ""
    gemini_model: str   = "gemini-1.5-flash"
    gemini_timeout: int = 15

    # ── AI Provider 3: OpenRouter (free models, no CC needed) ───────────────
    openrouter_api_key: str = ""

    # ── AI Provider 4: Ollama (local FALLBACK) ────────────────────────────────
    ollama_base_url:    str = "http://localhost:11434"
    ollama_model:       str = "gemma2:2b"
    ollama_embed_model: str = "nomic-embed-text"
    ollama_timeout: int     = 15

    # ── Translation ───────────────────────────────────────────────────────────
    deepl_api_key: str = ""

    # ── OpenSubtitles ─────────────────────────────────────────────────────────
    opensubs_api_key:   str = ""
    opensubs_base_url:  str = "https://api.opensubtitles.com/api/v1"
    opensubs_user_agent:str = "CineLang/3.0"

    # ── CORS ──────────────────────────────────────────────────────────────────
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:5173"]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
