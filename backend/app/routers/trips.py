from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from pydantic import AwareDatetime

from app.dependencies.auth import CurrentUser
from app.dependencies.db import DbSession
from app.dependencies.rate_limit import per_user
from app.models import Trip
from app.schemas.common import to_utc_naive, utc_now
from app.schemas.join_request import IncomingRequestOut, JoinRequestCreate, MyRequestOut
from app.schemas.pagination import DEFAULT_LIMIT, MAX_LIMIT, Page
from app.schemas.trip import SearchResult, TripCreate, TripDetail, TripOut, TripUpdate
from app.services import request_service, trip_service

router = APIRouter(prefix="/trips", tags=["trips"])


@router.post(
    "",
    response_model=TripOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(per_user("post-trip", limit=10, window_seconds=3600))],
)
async def post_trip(body: TripCreate, db: DbSession, current_user: CurrentUser) -> Trip:
    return await trip_service.create_trip(db, current_user, body)


# Declared before "/{trip_id}" so "search" and "mine" aren't parsed as trip ids.
Limit = Annotated[int, Query(ge=1, le=MAX_LIMIT)]


@router.get("/search", response_model=Page[SearchResult])
async def search_trips(
    db: DbSession,
    current_user: CurrentUser,
    from_place_id: int,
    to_place_id: int,
    at: AwareDatetime | None = None,
    window_minutes: Annotated[int, Query(ge=5, le=180)] = 30,
    cursor: str | None = None,
    limit: Limit = DEFAULT_LIMIT,
) -> Page[SearchResult]:
    """Open trips from others leaving the same pickup within the window, going to your
    destination or passing it on the way."""
    when = to_utc_naive(at) if at else utc_now()
    return await trip_service.search_trips(
        db, current_user, from_place_id, to_place_id, when, window_minutes, cursor, limit
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
    trip_id: int, body: JoinRequestCreate, db: DbSession, current_user: CurrentUser
) -> MyRequestOut:
    req = await request_service.create_request(db, current_user, trip_id, body.seats)
    return MyRequestOut.build(req)


@router.get("/{trip_id}/requests", response_model=list[IncomingRequestOut])
async def trip_requests(
    trip_id: int, db: DbSession, current_user: CurrentUser
) -> list[IncomingRequestOut]:
    reqs = await request_service.list_trip_requests(db, current_user, trip_id)
    return [IncomingRequestOut.build(r) for r in reqs]
