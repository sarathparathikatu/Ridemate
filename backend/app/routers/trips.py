from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from pydantic import AwareDatetime

from app.dependencies.auth import CurrentUser, VerifiedUser
from app.dependencies.db import DbSession
from app.dependencies.rate_limit import per_user
from app.models import Trip
from app.schemas.common import to_utc_naive, utc_now
from app.schemas.join_request import IncomingRequestOut, JoinRequestCreate, MyRequestOut
from app.schemas.pagination import DEFAULT_LIMIT, MAX_LIMIT, Page
from app.schemas.safety import RatingCreate, ShareLinkOut
from app.schemas.trip import SearchResult, TripCreate, TripDetail, TripOut, TripUpdate
from app.services import rating_service, request_service, share_service, trip_service
from app.services.errors import DomainError

router = APIRouter(prefix="/trips", tags=["trips"])


@router.post(
    "",
    response_model=TripOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(per_user("post-trip", limit=10, window_seconds=3600))],
)
async def post_trip(body: TripCreate, db: DbSession, current_user: VerifiedUser) -> Trip:
    return await trip_service.create_trip(db, current_user, body)


# Declared before "/{trip_id}" so "search" and "mine" aren't parsed as trip ids.
Limit = Annotated[int, Query(ge=1, le=MAX_LIMIT)]


Lat = Annotated[float | None, Query(ge=-90, le=90)]
Lng = Annotated[float | None, Query(ge=-180, le=180)]


async def _point(db, lat: float | None, lng: float | None, place_id: int | None, what: str):
    """A search end from coordinates (GPS / map pin) or, for older clients, a place id."""
    if lat is not None and lng is not None:
        return lat, lng
    if place_id is not None:
        return await trip_service.place_point(db, place_id)
    raise DomainError(f"Give the {what} as {what}_lat + {what}_lng (or a place id)")


@router.get("/search", response_model=Page[SearchResult])
async def search_trips(
    db: DbSession,
    current_user: CurrentUser,
    from_lat: Lat = None,
    from_lng: Lng = None,
    to_lat: Lat = None,
    to_lng: Lng = None,
    from_place_id: int | None = None,
    to_place_id: int | None = None,
    at: AwareDatetime | None = None,
    window_minutes: Annotated[int, Query(ge=5, le=180)] = 30,
    cursor: str | None = None,
    limit: Limit = DEFAULT_LIMIT,
) -> Page[SearchResult]:
    """Open rides from others starting near you (within 1 km) around a time, going to your
    destination or passing it on the way. Positions: coordinates, or known place ids."""
    origin = await _point(db, from_lat, from_lng, from_place_id, "from")
    destination = await _point(db, to_lat, to_lng, to_place_id, "to")
    when = to_utc_naive(at) if at else utc_now()
    return await trip_service.search_trips(
        db, current_user, origin, destination, when, window_minutes, cursor, limit
    )


@router.get("/mine", response_model=Page[TripOut])
async def my_trips(
    db: DbSession, current_user: CurrentUser, cursor: str | None = None, limit: Limit = DEFAULT_LIMIT
) -> Page[TripOut]:
    return await trip_service.list_my_trips(db, current_user, cursor, limit)


@router.get("/{trip_id}", response_model=TripDetail)
async def trip_detail(trip_id: int, db: DbSession, current_user: CurrentUser) -> TripDetail:
    return await trip_service.get_trip_detail(db, current_user, trip_id)


@router.patch("/{trip_id}", response_model=TripOut)
async def edit_trip(
    trip_id: int, body: TripUpdate, db: DbSession, current_user: CurrentUser
) -> Trip:
    return await trip_service.update_trip(db, current_user, trip_id, body)


@router.post("/{trip_id}/cancel", response_model=TripOut)
async def cancel_trip(trip_id: int, db: DbSession, current_user: CurrentUser) -> Trip:
    # A soft delete: the row stays (history, riders can see what happened), status changes.
    return await trip_service.cancel_trip(db, current_user, trip_id)


# Stops one account from spamming every host at the station with join requests.
@router.post(
    "/{trip_id}/requests",
    response_model=MyRequestOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(per_user("join-request", limit=10, window_seconds=60))],
)
async def request_to_join(
    trip_id: int, body: JoinRequestCreate, db: DbSession, current_user: VerifiedUser
) -> MyRequestOut:
    req = await request_service.create_request(db, current_user, trip_id, body.seats)
    return MyRequestOut.build(req)


@router.get("/{trip_id}/requests", response_model=list[IncomingRequestOut])
async def trip_requests(
    trip_id: int, db: DbSession, current_user: CurrentUser
) -> list[IncomingRequestOut]:
    reqs = await request_service.list_trip_requests(db, current_user, trip_id)
    return [IncomingRequestOut.build(r) for r in reqs]


@router.post("/{trip_id}/complete", response_model=TripOut)
async def complete_trip(trip_id: int, db: DbSession, current_user: CurrentUser) -> Trip:
    """Host marks the ride done, which lets everyone in it rate each other."""
    return await trip_service.complete_trip(db, current_user, trip_id)


@router.post("/{trip_id}/ratings", status_code=status.HTTP_201_CREATED)
async def rate_co_traveller(
    trip_id: int, body: RatingCreate, db: DbSession, current_user: CurrentUser
) -> dict[str, str]:
    await rating_service.rate(db, current_user, trip_id, body)
    return {"status": "saved"}


@router.post("/{trip_id}/share", response_model=ShareLinkOut, status_code=status.HTTP_201_CREATED)
async def share_with_family(trip_id: int, db: DbSession, current_user: CurrentUser) -> ShareLinkOut:
    return await share_service.create_link(db, current_user, trip_id)
