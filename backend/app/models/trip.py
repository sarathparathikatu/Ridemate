import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, Index, SmallInteger, String, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import MYSQL_TABLE_ARGS, Base, enum_values

if TYPE_CHECKING:
    from app.models.join_request import JoinRequest
    from app.models.place import Place
    from app.models.user import User


class Vehicle(enum.StrEnum):
    AUTO = "auto"
    CAB = "cab"
    ANY = "any"


class TripStatus(enum.StrEnum):
    OPEN = "open"
    FULL = "full"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


class Trip(Base):
    """A host's ride: "at <from> around <depart_at>, going to <to>, N seats free"."""

    __tablename__ = "trips"
    __table_args__ = (
        # Serves the search query: equality columns first (from_place_id, status), the
        # range column last (depart_at), so MySQL can seek straight to the matching slice
        # and read it already sorted by depart_at (no filesort). See scripts/explain_search.py.
        Index("ix_trips_search", "from_place_id", "status", "depart_at"),
        MYSQL_TABLE_ARGS,
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    host_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    # No ondelete: MySQL's default RESTRICT stops anyone deleting a place that trips use.
    from_place_id: Mapped[int] = mapped_column(ForeignKey("places.id"))
    to_place_id: Mapped[int] = mapped_column(ForeignKey("places.id"))
    depart_at: Mapped[datetime]  # stored in UTC (the connection's time_zone is +00:00)
    flex_minutes: Mapped[int] = mapped_column(SmallInteger, default=15, server_default=text("15"))
    seats_total: Mapped[int] = mapped_column(SmallInteger)  # seats offered to others
    seats_taken: Mapped[int] = mapped_column(SmallInteger, default=0, server_default=text("0"))
    vehicle: Mapped[Vehicle] = mapped_column(
        Enum(Vehicle, values_callable=enum_values), default=Vehicle.ANY, server_default="any"
    )
    fare_estimate: Mapped[int | None] = mapped_column(SmallInteger)  # whole ride, in rupees
    note: Mapped[str | None] = mapped_column(String(200))
    status: Mapped[TripStatus] = mapped_column(
        Enum(TripStatus, values_callable=enum_values),
        default=TripStatus.OPEN,
        server_default="open",
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    # lazy="raise" everywhere: every query must say up front what it loads (no hidden N+1).
    host: Mapped["User"] = relationship(lazy="raise")
    # Two FKs point at places, so each relationship must say which column it follows.
    from_place: Mapped["Place"] = relationship(foreign_keys=[from_place_id], lazy="raise")
    to_place: Mapped["Place"] = relationship(foreign_keys=[to_place_id], lazy="raise")
    requests: Mapped[list["JoinRequest"]] = relationship(
        back_populates="trip", lazy="raise", passive_deletes=True
    )

    @property
    def seats_left(self) -> int:
        return self.seats_total - self.seats_taken
