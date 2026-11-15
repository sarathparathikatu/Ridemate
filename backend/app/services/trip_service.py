from datetime import datetime, timedelta

from sqlalchemy import select, tuple_, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core import kv
from app.models import JoinRequest, Place, RequestStatus, Trip, TripStatus, User
from app.realtime import broker
from app.schemas.common import utc_now
from app.schemas.pagination import DEFAULT_LIMIT, Page, decode_cursor, make_page
from app.schemas.trip import RiderOut, TripCreate, TripDetail, TripOut, TripUpdate, check_seats
from app.schemas.user import ContactOut
from app.services.errors import ConflictError, DomainError, ForbiddenError, NotFoundError

# A trip is always shown with its host and both places. Loading them in the SAME query
# (JOINs) avoids the N+1 problem: 20 search results = 1 query, not 1 + 20 x 3.
WITH_DETAILS = (joinedload(Trip.host), joinedload(Trip.from_place), joinedload(Trip.to_place))

ACTIVE = (TripStatus.OPEN, TripStatus.FULL)

SEARCH_CACHE_SECONDS = 30


async def invalidate_search(from_place_id: int) -> None:
    """Call after any change that could alter search results for this pickup point.

    Every cached search key contains the pickup point's version number. Bumping it makes
    all old entries unreachable at once (they expire by themselves), so there is no need
    to find and delete each key.
    """
    await kv.incr(f"search-ver:{from_place_id}")


async def get_trip(db: AsyncSession, trip_id: int, *, lock: bool = False) -> Trip:
    # populate_existing: always take fresh column values from MySQL, even if this
    # session already holds the object from earlier in the request.
    stmt = (
        select(Trip)
        .options(*WITH_DETAILS)
        .where(Trip.id == trip_id)
        .execution_options(populate_existing=True)
    )
    if lock:
        stmt = stmt.with_for_update(of=Trip)  # lock only the trips row, not the joined ones
    trip = await db.scalar(stmt)
    if trip is None:
        raise NotFoundError("Trip not found")
    return trip


async def _riders_waiting_on(db: AsyncSession, trip_id: int) -> list[int]:
    """Users with a pending or accepted request: the people to notify about changes."""
    return list(
        await db.scalars(
            select(JoinRequest.requester_id).where(
                JoinRequest.trip_id == trip_id,
                JoinRequest.status.in_((RequestStatus.PENDING, RequestStatus.ACCEPTED)),
            )
        )
    )


async def _get_own_trip(db: AsyncSession, user: User, trip_id: int) -> Trip:
    trip = await get_trip(db, trip_id, lock=True)
    if trip.host_id != user.id:
        raise ForbiddenError("Only the host can change this trip")
    if trip.status not in ACTIVE:
        raise ConflictError(f"Trip is already {trip.status}")
    return trip


async def create_trip(db: AsyncSession, host: User, data: TripCreate) -> Trip:
    for place_id in (data.from_place_id, data.to_place_id):
        if await db.get(Place, place_id) is None:
            raise NotFoundError(f"Place {place_id} not found")
    # host_id comes from the verified token, never from the request body.
    trip = Trip(host_id=host.id, **data.model_dump())
    db.add(trip)
    await db.commit()
    await invalidate_search(trip.from_place_id)
    return await get_trip(db, trip.id)


async def list_my_trips(
    db: AsyncSession, user: User, cursor: str | None = None, limit: int = DEFAULT_LIMIT
) -> Page[TripOut]:
    stmt = (
        select(Trip)
        .options(*WITH_DETAILS)
        .where(Trip.host_id == user.id)
        .order_by(Trip.depart_at.desc(), Trip.id.desc())
        .limit(limit + 1)
    )
    if cursor:
        # Keyset pagination: "rows after the last one you saw", not OFFSET n. Stays fast
        # on page 500 and never skips or repeats rows when new trips are added.
        stmt = stmt.where(tuple_(Trip.depart_at, Trip.id) < tuple_(*decode_cursor(cursor)))
    trips = list(await db.scalars(stmt))
    return make_page(trips, limit, lambda t: (t.depart_at, t.id), TripOut.model_validate)


async def _search_page(
    db: AsyncSession,
    from_place_id: int,
    to_place_id: int,
    at: datetime,
    window_minutes: int,
    cursor: str | None,
    limit: int,
) -> Page[TripOut]:
    """The database part of search. Nothing user-specific here, so the result is cacheable."""
    window = timedelta(minutes=window_minutes)
    earliest = max(at - window, utc_now() - timedelta(minutes=10))  # never show departed rides
    stmt = (
        select(Trip)
        .options(*WITH_DETAILS)
        .where(
            Trip.from_place_id == from_place_id,
            Trip.to_place_id == to_place_id,
            Trip.status == TripStatus.OPEN,
            Trip.depart_at.between(earliest, at + window),
        )
        .order_by(Trip.depart_at, Trip.id)
        .limit(limit + 1)
    )
    if cursor:
        stmt = stmt.where(tuple_(Trip.depart_at, Trip.id) > tuple_(*decode_cursor(cursor)))
    trips = list(await db.scalars(stmt))
    return make_page(trips, limit, lambda t: (t.depart_at, t.id), TripOut.model_validate)


async def search_trips(
    db: AsyncSession,
    user: User,
    from_place_id: int,
    to_place_id: int,
    at: datetime,
    window_minutes: int,
    cursor: str | None = None,
    limit: int = DEFAULT_LIMIT,
) -> Page[TripOut]:
    """Cache-aside: read the cache, on a miss query MySQL and fill the cache.

    When a full train arrives, hundreds of people run the same search within a minute;
    only the first one reaches MySQL.
    """
    at = at.replace(second=0, microsecond=0)  # same-minute searches share one cache entry
    version = await kv.get(f"search-ver:{from_place_id}") or "0"
    key = (
        f"search:{from_place_id}:v{version}:{to_place_id}:{at.isoformat()}"
        f":{window_minutes}:{limit}:{cursor or ''}"
    )
    if (cached := await kv.get(key)) is not None:
        page = Page[TripOut].model_validate_json(cached)
    else:
        page = await _search_page(db, from_place_id, to_place_id, at, window_minutes, cursor, limit)
        await kv.set(key, page.model_dump_json(), SEARCH_CACHE_SECONDS)
    # Per-user filtering after the cache, so one cached page serves every rider.
    page.items = [trip for trip in page.items if trip.host.id != user.id]
    return page


async def get_trip_detail(db: AsyncSession, user: User, trip_id: int) -> TripDetail:
    trip = await get_trip(db, trip_id)
    riders = list(
        await db.scalars(
            select(JoinRequest)
            .options(joinedload(JoinRequest.requester))
            .where(JoinRequest.trip_id == trip.id, JoinRequest.status == RequestStatus.ACCEPTED)
        )
    )
    detail = TripDetail.model_validate(trip)
    # The privacy rule: contacts only for people inside this ride (host + accepted riders).
    if trip.host_id == user.id or any(r.requester_id == user.id for r in riders):
        detail.host_contact = ContactOut.model_validate(trip.host)
        detail.riders = [
            RiderOut(**ContactOut.model_validate(r.requester).model_dump(), seats=r.seats)
            for r in riders
        ]
    return detail


async def update_trip(db: AsyncSession, user: User, trip_id: int, data: TripUpdate) -> Trip:
    trip = await _get_own_trip(db, user, trip_id)
    # exclude_unset: only fields the client actually sent. None is allowed only for the
    # optional columns (clearing a note); required columns ignore an explicit null.
    changes = {
        field: value
        for field, value in data.model_dump(exclude_unset=True).items()
        if value is not None or field in ("note", "fare_estimate")
    }
    if "seats_total" in changes:
        if changes["seats_total"] < trip.seats_taken:
            raise ConflictError(f"{trip.seats_taken} seat(s) are already taken")
        try:
            check_seats(changes["seats_total"], trip.vehicle)
        except ValueError as exc:
            raise DomainError(str(exc)) from None
    for field, value in changes.items():
        setattr(trip, field, value)
    trip.status = TripStatus.FULL if trip.seats_left == 0 else TripStatus.OPEN
    riders = await _riders_waiting_on(db, trip.id)
    await db.commit()
    await invalidate_search(trip.from_place_id)
    await broker.publish(
        riders,
        {
            "type": "trip.updated",
            "trip_id": trip.id,
            "message": f"{user.display_name} changed the details of your ride",
        },
    )
    return await get_trip(db, trip.id)


async def cancel_trip(db: AsyncSession, user: User, trip_id: int) -> Trip:
    trip = await _get_own_trip(db, user, trip_id)
    riders = await _riders_waiting_on(db, trip.id)
    trip.status = TripStatus.CANCELLED
    # One UPDATE statement for all pending requests (Core-style), no objects loaded.
    await db.execute(
        update(JoinRequest)
        .where(JoinRequest.trip_id == trip.id, JoinRequest.status == RequestStatus.PENDING)
        .values(status=RequestStatus.DECLINED)
    )
    await db.commit()
    await invalidate_search(trip.from_place_id)
    await broker.publish(
        riders,
        {
            "type": "trip.cancelled",
            "trip_id": trip.id,
            "message": f"{user.display_name} cancelled the ride to {trip.to_place.name}",
        },
    )
    return await get_trip(db, trip.id)
