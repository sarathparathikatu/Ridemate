from functools import lru_cache
from typing import Literal, Self

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Free community servers: fine for development and small projects, not for real traffic.
PUBLIC_DEMO_SERVERS = ("nominatim.openstreetmap.org", "router.project-osrm.org")


class Settings(BaseSettings):
    """Typed app config, loaded from environment variables / backend/.env."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # "production" turns on the safety checks at the bottom of this class: the app refuses
    # to start with settings that are only acceptable on a developer's laptop.
    environment: Literal["development", "production"] = "development"

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

    # Phone verification. "console" prints codes to the server log instead of texting them
    # (no SMS account needed while developing). OTP_DEV_ECHO also returns the code in the
    # API response; both must be off in production.
    sms_provider: str = "console"
    otp_dev_echo: bool = True
    require_verified_phone: bool = False  # true in production: post/join only when verified

    # Browser origins allowed to call the API (the Vite dev server by default).
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # Outside map services, called by the API on the user's behalf (see services/geo_service).
    # Set either URL to an empty value to switch that feature off.
    # Address search: any server that speaks the Nominatim API.
    geocoder_url: str | None = "https://nominatim.openstreetmap.org"
    geocoder_country_codes: str | None = "in"  # limit results to these countries; empty = worldwide
    # Road routes: any server that speaks the OSRM API.
    routing_url: str | None = "https://router.project-osrm.org"
    # How this app introduces itself to those services. Their usage policies ask for a
    # name that identifies your app; put your site or a contact address here when you deploy.
    outbound_user_agent: str = "rideshare-web-app/0.1"

    @model_validator(mode="after")
    def refuse_unsafe_production_settings(self) -> Self:
        if self.environment == "production" and (problems := self.production_errors()):
            raise ValueError("Unsafe settings for ENVIRONMENT=production: " + "; ".join(problems))
        return self

    def production_errors(self) -> list[str]:
        """Settings that would put real users at risk. Any of these stops the app."""
        problems = []
        secret = self.jwt_secret_key
        if len(secret) < 32 or secret.lower().startswith(("change", "replace")):
            problems.append("JWT_SECRET_KEY must be a random string of at least 32 characters")
        if self.otp_dev_echo:
            problems.append("OTP_DEV_ECHO must be false (it shows phone codes to anyone who asks)")
        if self.require_verified_phone and self.sms_provider == "console":
            problems.append("REQUIRE_VERIFIED_PHONE needs a real SMS_PROVIDER (console sends nothing)")
        if "*" in self.cors_origins:
            problems.append("CORS_ORIGINS must list your site, not *")
        return problems

    def production_warnings(self) -> list[str]:
        """Settings that work but deserve a second look. Logged at startup in production."""
        warnings = []
        if self.sms_provider == "console":
            warnings.append("SMS_PROVIDER=console: nobody can verify a phone number")
        if not self.redis_url:
            warnings.append("REDIS_URL is not set: run a single API process only")
        for name, url in (("GEOCODER_URL", self.geocoder_url), ("ROUTING_URL", self.routing_url)):
            if url and any(server in url for server in PUBLIC_DEMO_SERVERS):
                warnings.append(f"{name} points at a free community server: check its usage policy")
        return warnings


@lru_cache
def get_settings() -> Settings:
    # Cached so .env is parsed once, and tests can override it via dependency_overrides.
    return Settings()
