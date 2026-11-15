"""Phone verification with one-time codes (OTP).

The code lives only in the key-value store (Redis in production), with a 5-minute
expiry and at most 5 guesses. Only an HMAC of it is stored, so a peek at Redis doesn't
reveal live codes.
"""

import hashlib
import hmac
import json
import secrets

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import kv
from app.core.config import get_settings
from app.models import User
from app.schemas.common import utc_now
from app.services import sms
from app.services.errors import ConflictError, DomainError

OTP_TTL_SECONDS = 300
MAX_ATTEMPTS = 5


def _key(user_id: int) -> str:
    return f"otp:{user_id}"


def _code_hash(user_id: int, code: str) -> str:
    # Keyed with the server secret: 6 digits are only a million guesses, so a plain hash
    # could be reversed instantly by anyone who read Redis.
    secret = get_settings().jwt_secret_key.encode()
    return hmac.new(secret, f"{user_id}:{code}".encode(), hashlib.sha256).hexdigest()


async def send_code(user: User, phone: str) -> str | None:
    """Text a fresh code to `phone`. Returns the code only in dev-echo mode."""
    code = f"{secrets.randbelow(1_000_000):06d}"  # secrets, not random: unpredictable
    record = {"phone": phone, "hash": _code_hash(user.id, code), "attempts": 0}
    await kv.set(_key(user.id), json.dumps(record), OTP_TTL_SECONDS)
    await sms.send_sms(phone, f"Your RideMate code is {code}. It expires in 5 minutes.")
    return code if get_settings().otp_dev_echo else None


async def verify_code(db: AsyncSession, user: User, code: str) -> User:
    raw = await kv.get(_key(user.id))
    if raw is None:
        raise DomainError("Code expired. Request a new one.")
    record = json.loads(raw)

    # compare_digest takes the same time whether the first or the last character differs,
    # so response timing leaks nothing about how close a guess was.
    if not hmac.compare_digest(record["hash"], _code_hash(user.id, code)):
        record["attempts"] += 1
        if record["attempts"] >= MAX_ATTEMPTS:
            await kv.delete(_key(user.id))
            raise DomainError("Too many wrong codes. Request a new one.")
        await kv.set(_key(user.id), json.dumps(record), ttl_seconds=None)  # keep the expiry
        raise DomainError("Wrong code")

    await kv.delete(_key(user.id))  # a code works once
    taken = await db.scalar(
        select(User.id).where(
            User.phone == record["phone"], User.phone_verified_at.is_not(None), User.id != user.id
        )
    )
    if taken is not None:
        raise ConflictError("This number is already verified on another account")
    user.phone = record["phone"]
    user.phone_verified_at = utc_now()
    await db.commit()
    await db.refresh(user)
    return user
