import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, SmallInteger, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import MYSQL_TABLE_ARGS, Base, enum_values

if TYPE_CHECKING:
    from app.models.trip import Trip
    from app.models.user import User


class RequestStatus(enum.StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    CANCELLED = "cancelled"


class JoinRequest(Base):
    """A rider asking a host "can I join your ride?"."""

    __tablename__ = "join_requests"
    __table_args__ = (
        # One request per rider per trip. InnoDB also reuses this index for the trip_id FK
        # (trip_id is its leftmost column), so no separate trip_id index is created.
        UniqueConstraint("trip_id", "requester_id"),
        MYSQL_TABLE_ARGS,
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    trip_id: Mapped[int] = mapped_column(ForeignKey("trips.id", ondelete="CASCADE"))
    requester_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    seats: Mapped[int] = mapped_column(SmallInteger, default=1, server_default=text("1"))
    status: Mapped[RequestStatus] = mapped_column(
        Enum(RequestStatus, values_callable=enum_values),
        default=RequestStatus.PENDING,
        server_default="pending",
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    trip: Mapped["Trip"] = relationship(back_populates="requests", lazy="raise")
    requester: Mapped["User"] = relationship(lazy="raise")
