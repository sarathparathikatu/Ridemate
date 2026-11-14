from datetime import UTC, datetime, timedelta

import bcrypt
import jwt

from app.core.config import get_settings


def hash_password(password: str) -> str:
    # gensalt() adds a random salt, so two users with the same password get different hashes.
    # Deliberately slow (~0.25s): fine for one login, ruinous for a brute-force attacker.
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed_password: str) -> bool:
    # Re-hashes the attempt using the salt stored inside hashed_password, then compares.
    return bcrypt.checkpw(password.encode(), hashed_password.encode())


def create_access_token(user_id: int) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),  # "subject": who the token is about (JWT spec says string)
        "iat": now,           # issued at
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
