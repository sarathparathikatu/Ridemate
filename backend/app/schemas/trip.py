from datetime import timedelta
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models import TripStatus, Vehicle
from app.schemas.common import UTCInput, UTCOutput, utc_now
from app.schemas.user import ContactOut, PersonOut

# Co-travellers a host can take besides themselves: an auto seats 3, a cab 4.
MAX_SEATS = {Vehicle.AUTO: 2, Vehicle.CAB: 3, Vehicle.ANY: 2}
MAX_DAYS_AHEAD = 7


def check_departure(depart_at) -> None:
    now = utc_now()
    if depart_at < now - timedelta(minutes=5):
        raise ValueError("departure time is in the past")
    if depart_at > now + timedelta(days=MAX_DAYS_AHEAD):
        raise ValueError(f"departure must be within {MAX_DAYS_AHEAD} days")


def check_seats(seats_total: int, vehicle: Vehicle) -> None:
    if seats_total > MAX_SEATS[vehicle]:
        raise ValueError(f"a '{vehicle}' ride can take at most {MAX_SEATS[vehicle]} co-travellers")


class LocationIn(BaseModel):
    """Any point: from the phone's GPS, a pin dropped on the map, or a known place."""

    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    label: str = Field(min_length=1, max_length=120)  # what people see, e.g. "Station main exit"


class LocationOut(BaseModel):
    lat: float
    lng: float
    label: str


class TripCreate(BaseModel):
    # Each end is EITHER a known place (from_place_id / to_place_id) OR any point
    # (start / end). The service turns places into points, so trips always have both.
    from_place_id: int | None = None
    to_place_id: int | None = None
    start: LocationIn | None = None
    end: LocationIn | None = None
    depart_at: UTCInput
    flex_minutes: int = Field(default=15, ge=0, le=60)
    seats_total: int = Field(ge=1, le=3)
    vehicle: Vehicle = Vehicle.ANY
    fare_estimate: int | None = Field(default=None, ge=0, le=5000)
    note: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def check_rules(self) -> "TripCreate":
        if (self.from_place_id is None) == (self.start is None):
            raise ValueError("give the pickup as either from_place_id or start")
        if (self.to_place_id is None) == (self.end is None):
            raise ValueError("give the destination as either to_place_id or end")
        if self.from_place_id is not None and self.from_place_id == self.to_place_id:
            raise ValueError("pickup and destination must be different")
        check_departure(self.depart_at)
        check_seats(self.seats_total, self.vehicle)
        return self


class TripUpdate(BaseModel):
    """PATCH body: every field optional; only the ones sent are changed."""

    depart_at: UTCInput | None = None
    flex_minutes: int | None = Field(default=None, ge=0, le=60)
    seats_total: int | None = Field(default=None, ge=1, le=3)
    fare_estimate: int | None = Field(default=None, ge=0, le=5000)
    note: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def check_rules(self) -> "TripUpdate":
        if self.depart_at is not None:
            check_departure(self.depart_at)
        return self


class TripOut(BaseModel):
    """Public view of a trip, safe to show in search results."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    host: PersonOut
    start: LocationOut
    end: LocationOut
    depart_at: UTCOutput
    flex_minutes: int
    seats_total: int
    seats_taken: int
    seats_left: int
    vehicle: Vehicle
    fare_estimate: int | None
    note: str | None
    status: TripStatus
    created_at: UTCOutput


class SearchResult(TripOut):
    """A search hit, plus how it matches the rider's destination."""

    match: Literal["same_destination", "on_the_way"]
    # How far the ride's start is from the rider (they walk this far to meet the host).
    pickup_distance_m: int
    # Extra distance the host drives to drop the rider (only for "on_the_way" matches).
    detour_km: float | None = None


class RiderOut(ContactOut):
    seats: int


class TripDetail(TripOut):
    """Trip plus private details, filled in only for the host and accepted riders."""

    host_contact: ContactOut | None = None
    riders: list[RiderOut] = []
