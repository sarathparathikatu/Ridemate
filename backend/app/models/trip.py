import enum
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import Computed, Enum, ForeignKey, Index, Numeric, SmallInteger, String, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import UserDefinedType

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


class Point(UserDefinedType):
    """MySQL POINT, stored as x = longitude, y = latitude. The column's "SRID 0" attribute
    (needed for MySQL to use a SPATIAL index) is set in the migration, because for a
    generated column it must come after NOT NULL, which a type name can't express."""

    cache_ok = True

    def get_col_spec(self, **kw: Any) -> str:
        return "POINT"


class Trip(Base):
    """A host's ride: "from <start> around <depart_at>, going to <end>, N seats free".

    Start and end are any points (GPS, a pin on the map, or a known place), so RideMate
    works in every city. from_place_id/to_place_id are set only when a known place was used.
    """

    __tablename__ = "trips"
    __table_args__ = (
        # "Rides starting near me": a SPATIAL index (an R-tree) answers "which points lie
        # inside this box?" without scanning every ride. See scripts/explain_search.py.
        Index("ix_trips_from_point", "from_point", mysql_prefix="SPATIAL"),
        # The other half of search: open rides in a time window.
        Index("ix_trips_open_by_time", "status", "depart_at"),
        # Originally the place-based search index; now mainly backs the from_place_id FK.
        Index("ix_trips_search", "from_place_id", "status", "depart_at"),
        MYSQL_TABLE_ARGS,
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    host_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    # Where the ride starts and ends: any point, with a label people recognise.
    from_lat: Mapped[Decimal] = mapped_column(Numeric(9, 6))
    from_lng: Mapped[Decimal] = mapped_column(Numeric(9, 6))
    from_label: Mapped[str] = mapped_column(String(120))
    to_lat: Mapped[Decimal] = mapped_column(Numeric(9, 6))
    to_lng: Mapped[Decimal] = mapped_column(Numeric(9, 6))
    to_label: Mapped[str] = mapped_column(String(120))
    # Computed and stored by MySQL from from_lng/from_lat; it exists only to carry the
    # SPATIAL index. Never loaded into Python (deferred, and raises if touched).
    from_point: Mapped[Any] = mapped_column(
        Point(),
        Computed("point(`from_lng`,`from_lat`)", persisted=True),
        deferred=True,
        deferred_raiseload=True,
    )
    # Set only when the user picked a known place. No ondelete: MySQL's default RESTRICT
    # stops anyone deleting a place that trips use.
    from_place_id: Mapped[int | None] = mapped_column(ForeignKey("places.id"))
    to_place_id: Mapped[int | None] = mapped_column(ForeignKey("places.id"))
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
    from_place: Mapped["Place | None"] = relationship(foreign_keys=[from_place_id], lazy="raise")
    to_place: Mapped["Place | None"] = relationship(foreign_keys=[to_place_id], lazy="raise")
    requests: Mapped[list["JoinRequest"]] = relationship(
        back_populates="trip", lazy="raise", passive_deletes=True
    )

    @property
    def seats_left(self) -> int:
        return self.seats_total - self.seats_taken

    @property
    def start(self) -> dict:
        return {"lat": float(self.from_lat), "lng": float(self.from_lng), "label": self.from_label}

    @property
    def end(self) -> dict:
        return {"lat": float(self.to_lat), "lng": float(self.to_lng), "label": self.to_label}
