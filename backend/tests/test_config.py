"""ENVIRONMENT=production refuses settings that are only acceptable on a laptop."""

import pytest
from pydantic import ValidationError

from app.core.config import Settings

SAFE = {
    "environment": "production",
    "database_url": "mysql+aiomysql://u:p@db/ridemate",
    "jwt_secret_key": "k9Zr2vQ7mX4pL8sT1wN6yB3cF5hJ0dGa",  # 32 random characters
    "otp_dev_echo": False,
    "sms_provider": "acme-sms",
    "require_verified_phone": True,
    "redis_url": "redis://redis:6379/0",
    "cors_origins": ["https://ridemate.example.com"],
    "geocoder_url": "https://geocoder.internal",
    "routing_url": "https://router.internal",
}


def settings(**changes) -> Settings:
    # _env_file=None: ignore the developer's own .env, so the test means the same everywhere.
    return Settings(_env_file=None, **(SAFE | changes))


def test_safe_production_settings_start_without_complaints():
    assert settings().production_warnings() == []


@pytest.mark.parametrize(
    ("changes", "complaint"),
    [
        ({"jwt_secret_key": "short"}, "JWT_SECRET_KEY"),
        ({"jwt_secret_key": "change-me-to-a-long-random-string-please"}, "JWT_SECRET_KEY"),
        ({"otp_dev_echo": True}, "OTP_DEV_ECHO"),
        ({"sms_provider": "console"}, "REQUIRE_VERIFIED_PHONE"),
        ({"cors_origins": ["*"]}, "CORS_ORIGINS"),
    ],
)
def test_unsafe_production_settings_stop_the_app(changes, complaint):
    with pytest.raises(ValidationError, match=complaint):
        settings(**changes)


def test_the_same_settings_are_fine_while_developing():
    dev = settings(environment="development", jwt_secret_key="short", otp_dev_echo=True, sms_provider="console")
    assert dev.environment == "development"


def test_production_warnings_point_at_things_worth_a_second_look():
    relaxed = settings(
        sms_provider="console",
        require_verified_phone=False,
        redis_url=None,
        geocoder_url="https://nominatim.openstreetmap.org",
    )
    warnings = " ".join(relaxed.production_warnings())
    assert "SMS_PROVIDER" in warnings and "REDIS_URL" in warnings and "GEOCODER_URL" in warnings
    assert "ROUTING_URL" not in warnings  # that one points at our own server
