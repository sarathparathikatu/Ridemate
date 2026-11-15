from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed app config, loaded from environment variables / backend/.env."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    database_url: str
    sql_echo: bool = False

    # No default on purpose: the app refuses to start without a real secret.
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 30
    # A rotated refresh token presented again within this window is treated as a harmless
    # race (two tabs refreshing at once), not theft.
    refresh_reuse_grace_seconds: int = 30

    # Optional. Without it, events/cache/rate limits live in this process's memory (fine for
    # one server on a laptop); with it, every server process shares them through Redis.
    redis_url: str | None = None

    rate_limit_enabled: bool = True

    # Browser origins allowed to call the API (the Vite dev server by default).
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]


@lru_cache
def get_settings() -> Settings:
    # Cached so .env is parsed once, and tests can override it via dependency_overrides.
    return Settings()
