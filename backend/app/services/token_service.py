import uuid
from datetime import timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import create_access_token, hash_token, new_opaque_token
from app.models import RefreshToken
from app.schemas.common import utc_now
from app.services.errors import DomainError


class InvalidRefreshTokenError(DomainError):
    status_code = 401


async def issue_tokens(
    db: AsyncSession, user_id: int, family_id: str | None = None
) -> tuple[str, str]:
    """Create an access token + refresh token pair. A new login starts a new family."""
    refresh = new_opaque_token()
    db.add(
        RefreshToken(
            user_id=user_id,
            family_id=family_id or uuid.uuid4().hex,
            token_hash=hash_token(refresh),
            expires_at=utc_now() + timedelta(days=get_settings().refresh_token_expire_days),
        )
    )
    await db.commit()
    return create_access_token(user_id), refresh


async def _revoke_family(db: AsyncSession, family_id: str, reason: str) -> None:
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=utc_now(), revoked_reason=reason)
    )


async def rotate(db: AsyncSession, refresh_token: str) -> tuple[str, str]:
    """Swap a valid refresh token for a fresh pair; the old token stops working."""
    # FOR UPDATE: two simultaneous refreshes with the same token are serialised.
    row = await db.scalar(
        select(RefreshToken)
        .where(RefreshToken.token_hash == hash_token(refresh_token))
        .with_for_update()
    )
    if row is None:
        raise InvalidRefreshTokenError("Invalid refresh token")

    now = utc_now()
    if row.revoked_at is not None:
        grace = timedelta(seconds=get_settings().refresh_reuse_grace_seconds)
        # `grace and ...`: a zero window never excuses reuse. (Needed because MySQL DATETIME
        # rounds to whole seconds, so now - revoked_at can be slightly negative.)
        just_rotated = row.revoked_reason == "rotated" and grace and now - row.revoked_at < grace
        if not just_rotated:
            # A replaced token came back long afterwards: assume it was stolen and end the
            # whole login, for the thief and the real user alike (they simply log in again).
            await _revoke_family(db, row.family_id, "reuse")
            await db.commit()
        raise InvalidRefreshTokenError("Refresh token is no longer valid")
    if row.expires_at <= now:
        raise InvalidRefreshTokenError("Refresh token expired")

    row.revoked_at, row.revoked_reason = now, "rotated"
    return await issue_tokens(db, row.user_id, row.family_id)  # one commit for both changes


async def revoke(db: AsyncSession, refresh_token: str) -> None:
    """Logout: kill every token from this login. Unknown tokens are silently ignored."""
    row = await db.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == hash_token(refresh_token))
    )
    if row is not None:
        await _revoke_family(db, row.family_id, "logout")
        await db.commit()
