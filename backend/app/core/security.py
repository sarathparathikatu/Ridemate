import hashlib
import secrets
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


def decode_access_token(token: str) -> int:
    """Verify signature + expiry and return the user id. Raises jwt.InvalidTokenError
    or ValueError for anything wrong with the token."""
    settings = get_settings()
    # algorithms is an explicit allow-list, so a token claiming another algorithm
    # (e.g. "none") is rejected.
    payload = jwt.decode(
        token,
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
        options={"require": ["sub", "exp"]},
    )
    return int(payload["sub"])


def new_opaque_token() -> str:
    """A random, meaningless string (256 bits): refresh tokens, share links."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    # SHA-256, not bcrypt: the input is already 256 random bits, so nobody can brute-force
    # it, and a fast hash lets us look the token up by its hash on every refresh.
    return hashlib.sha256(token.encode()).hexdigest()
