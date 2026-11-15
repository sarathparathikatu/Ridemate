"""Trust and safety: ratings after a ride, reports, blocks, and share-with-family links."""

import enum
from datetime import datetime

from sqlalchemy import Enum, ForeignKey, SmallInteger, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import MYSQL_TABLE_ARGS, Base, enum_values


class Rating(Base):
    """One person rating one co-traveller for one completed ride."""

    __tablename__ = "ratings"
    __table_args__ = (UniqueConstraint("trip_id", "rater_id", "rated_id"), MYSQL_TABLE_ARGS)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    trip_id: Mapped[int] = mapped_column(ForeignKey("trips.id", ondelete="CASCADE"))
    rater_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    rated_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    stars: Mapped[int] = mapped_column(SmallInteger)
    tags: Mapped[str | None] = mapped_column(String(200))  # comma-separated, from a fixed list
    comment: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class ReportReason(enum.StrEnum):
    NO_SHOW = "no_show"
    UNSAFE = "unsafe"
    HARASSMENT = "harassment"
    FAKE_PROFILE = "fake_profile"
    OTHER = "other"


class ReportStatus(enum.StrEnum):
    OPEN = "open"
    REVIEWED = "reviewed"


class Report(Base):
    """A user reporting another user. Reviewed by a person, never acted on automatically."""

    __tablename__ = "reports"
    __table_args__ = MYSQL_TABLE_ARGS

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    reporter_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    reported_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    trip_id: Mapped[int | None] = mapped_column(ForeignKey("trips.id", ondelete="SET NULL"))
    reason: Mapped[ReportReason] = mapped_column(Enum(ReportReason, values_callable=enum_values))
    details: Mapped[str | None] = mapped_column(String(1000))
    status: Mapped[ReportStatus] = mapped_column(
        Enum(ReportStatus, values_callable=enum_values),
        default=ReportStatus.OPEN,
        server_default="open",
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class Block(Base):
    """blocker never sees blocked's rides, and neither can request the other's."""

    __tablename__ = "blocks"
    __table_args__ = MYSQL_TABLE_ARGS

    # Composite primary key: one row per pair, and the PK index answers "whom did I block".
    blocker_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    blocked_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class TripShare(Base):
    """A secret read-only link to a ride for family. Only the token's hash is stored."""

    __tablename__ = "trip_shares"
    __table_args__ = MYSQL_TABLE_ARGS

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    trip_id: Mapped[int] = mapped_column(ForeignKey("trips.id", ondelete="CASCADE"))
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
