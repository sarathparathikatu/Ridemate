from datetime import datetime

from sqlalchemy import ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import MYSQL_TABLE_ARGS, Base


class RefreshToken(Base):
    """One issued refresh token. Only its SHA-256 hash is stored, never the token itself.

    Tokens from one login share a family_id: every refresh replaces the token with a new
    one in the same family, so logout (or detected theft) can revoke the whole chain.
    """

    __tablename__ = "refresh_tokens"
    __table_args__ = MYSQL_TABLE_ARGS

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    family_id: Mapped[str] = mapped_column(String(32), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime]
    revoked_at: Mapped[datetime | None]
    revoked_reason: Mapped[str | None] = mapped_column(String(20))  # rotated | logout | reuse
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
