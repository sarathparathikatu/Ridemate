from datetime import datetime, timedelta

from sqlalchemy import and_, func, or_, select, tuple_, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core import kv
from app.core.geo import bounding_box_wkt, distance_m
from app.models import JoinRequest, Place, RequestStatus, Trip, TripStatus, User
from app.realtime import broker
from app.schemas.common import utc_now
from app.schemas.pagination import DEFAULT_LIMIT, Page, decode_cursor, make_page
from app.schemas.trip import (
    RiderOut,
    SearchResult,
    TripCreate,
    TripDetail,
    TripOut,
    TripUpdate,
    check_seats,
)
from app.schemas.user import ContactOut
from app.services import safety_service
from app.services.errors import ConflictError, DomainError, ForbiddenError, NotFoundError

# A trip is always shown with its host. Loading the host in the SAME query (a JOIN)
# avoids the N+1 problem: 20 search results = 1 query, not 1 + 20.
WITH_DETAILS = (joinedload(Trip.host),)

ACTIVE = (TripStatus.OPEN, TripStatus.FULL)

SEARCH_CACHE_SECONDS = 30
# Distances are straight-line metres: a rough stand-in for walking/road distance that is
# good enough at city scale.
PICKUP_RADIUS_M = 1000  # rides starting within this distance of the rider
DEST_RADIUS_M = 1000  # a ride ending this close to the rider's destination = same destination
MAX_DETOUR_METERS = 1500  # extra distance a host is assumed to accept to drop a rider
MIN_TRIP_METERS = 200  # shorter than this isn't a ride


async def invalidate_search() -> None:
    """Call after any change that could alter search results.

    Every cached search key contains this version number. Bumping it makes all old
    entries unreachable at once (they expire by themselves), so there is no need to find
    and delete each key. Trade-off: with free locations there is no natural "area" to
    version, so one change anywhere invalidates every search. Per-area versions (a grid of
    cells) would keep more of the cache warm in a large deployment.
    """
    await kv.incr("search-ver")


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


async def _resolve(
    db: AsyncSession, place_id: int | None, point
) -> tuple[float, float, str, int | None]:
    """One end of a ride as (lat, lng, label, place_id): a known place, or any point."""
    if place_id is not None:
        place = await db.get(Place, place_id)
        if place is None:
            raise NotFoundError(f"Place {place_id} not found")
        return float(place.lat), float(place.lng), place.name, place.id
    return point.lat, point.lng, point.label.strip(), None


async def create_trip(db: AsyncSession, host: User, data: TripCreate) -> Trip:
    from_lat, from_lng, from_label, from_place_id = await _resolve(db, data.from_place_id, data.start)
    to_lat, to_lng, to_label, to_place_id = await _resolve(db, data.to_place_id, data.end)
    if distance_m(from_lat, from_lng, to_lat, to_lng) < MIN_TRIP_METERS:
        raise DomainError("Pickup and destination are too close together")
    trip = Trip(
        host_id=host.id,  # from the verified token, never from the request body
        from_lat=from_lat,
        from_lng=from_lng,
        from_label=from_label,
        from_place_id=from_place_id,
        to_lat=to_lat,
        to_lng=to_lng,
        to_label=to_label,
        to_place_id=to_place_id,
        **data.model_dump(exclude={"from_place_id", "to_place_id", "start", "end"}),
    )
    db.add(trip)
    await db.commit()
    await invalidate_search()
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


def _distance(lat_a, lng_a, lat_b, lng_b):
    """Great-circle distance in metres, computed by MySQL. POINT takes (longitude, latitude)."""
    return func.ST_Distance_Sphere(func.POINT(lng_a, lat_a), func.POINT(lng_b, lat_b))


async def _search_page(
    db: AsyncSession,
    origin: tuple[float, float],
    destination: tuple[float, float],
    at: datetime,
    window_minutes: int,
    cursor: str | None,
    limit: int,
) -> Page[SearchResult]:
    """The database part of search. Nothing user-specific here, so the result is cacheable.

    1. SPATIAL index: rides whose start lies in a box around the rider (fast).
    2. Exact circle: keep those really within PICKUP_RADIUS_M.
    3. Destination: ends near the rider's destination, or passes it on the way.
    """
    o_lat, o_lng = origin
    d_lat, d_lng = destination
    pickup = _distance(Trip.from_lat, Trip.from_lng, o_lat, o_lng)  # how far the rider walks
    start_to_dest = _distance(Trip.from_lat, Trip.from_lng, d_lat, d_lng)
    dest_to_end = _distance(d_lat, d_lng, Trip.to_lat, Trip.to_lng)
    whole_trip = _distance(Trip.from_lat, Trip.from_lng, Trip.to_lat, Trip.to_lng)
    detour = start_to_dest + dest_to_end - whole_trip  # extra metres to drop the rider

    # MBRContains(box, point) can use the SPATIAL index on from_point; ST_Distance_Sphere
    # can't (it has to be computed per row), so the box narrows the candidates first.
    near_box = func.ST_GeomFromText(bounding_box_wkt(o_lat, o_lng, PICKUP_RADIUS_M), 0)
    window = timedelta(minutes=window_minutes)
    earliest = max(at - window, utc_now() - timedelta(minutes=10))  # never show departed rides
    stmt = (
        select(
            Trip,
            pickup.label("pickup_m"),
            dest_to_end.label("end_gap_m"),
            detour.label("detour_m"),
        )
        .options(*WITH_DETAILS)
        .where(
            func.MBRContains(near_box, Trip.from_point),
            pickup <= PICKUP_RADIUS_M,
            Trip.status == TripStatus.OPEN,
            Trip.depart_at.between(earliest, at + window),
            or_(
                dest_to_end <= DEST_RADIUS_M,
                # "On the way": a small detour for the host, and the rider gets off first.
                and_(detour <= MAX_DETOUR_METERS, start_to_dest < whole_trip),
            ),
        )
        .order_by(Trip.depart_at, Trip.id)
        .limit(limit + 1)
    )
    if cursor:
        stmt = stmt.where(tuple_(Trip.depart_at, Trip.id) > tuple_(*decode_cursor(cursor)))
    rows = (await db.execute(stmt)).all()

    def to_result(row) -> SearchResult:
        trip, pickup_m, end_gap_m, detour_m = row
        same = float(end_gap_m) <= DEST_RADIUS_M
        return SearchResult(
            **TripOut.model_validate(trip).model_dump(),
            match="same_destination" if same else "on_the_way",
            pickup_distance_m=round(float(pickup_m)),
            detour_km=None if same else round(max(float(detour_m), 0.0) / 1000, 1),
        )

    return make_page(rows, limit, lambda row: (row[0].depart_at, row[0].id), to_result)


async def search_trips(
    db: AsyncSession,
    user: User,
    origin: tuple[float, float],
    destination: tuple[float, float],
    at: datetime,
    window_minutes: int,
    cursor: str | None = None,
    limit: int = DEFAULT_LIMIT,
) -> Page[SearchResult]:
    """Cache-aside: read the cache, on a miss query MySQL and fill the cache.

    When a full train arrives, hundreds of people run the same search within a minute;
    only the first one reaches MySQL.
    """
    # Snap positions to a ~100 m grid (3 decimal places) and times to the minute, so
    # people standing near each other share one cache entry.
    origin = (round(origin[0], 3), round(origin[1], 3))
    destination = (round(destination[0], 3), round(destination[1], 3))
    at = at.replace(second=0, microsecond=0)
    version = await kv.get("search-ver") or "0"
    key = (
        f"search:v{version}:{origin[0]},{origin[1]}:{destination[0]},{destination[1]}"
        f":{at.isoformat()}:{window_minutes}:{limit}:{cursor or ''}"
    )
    if (cached := await kv.get(key)) is not None:
        page = Page[SearchResult].model_validate_json(cached)
    else:
        page = await _search_page(db, origin, destination, at, window_minutes, cursor, limit)
        await kv.set(key, page.model_dump_json(), SEARCH_CACHE_SECONDS)
    # Per-user filtering after the cache, so one cached page serves every rider:
    # not your own rides, and nobody you blocked or who blocked you.
    hidden = await safety_service.hidden_user_ids(db, user.id) | {user.id}
    page.items = [trip for trip in page.items if trip.host.id not in hidden]
    return page


async def place_point(db: AsyncSession, place_id: int) -> tuple[float, float]:
    place = await db.get(Place, place_id)
    if place is None:
        raise NotFoundError(f"Place {place_id} not found")
    return float(place.lat), float(place.lng)


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
    await invalidate_search()
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
    await invalidate_search()
    await broker.publish(
        riders,
        {
            "type": "trip.cancelled",
            "trip_id": trip.id,
            "message": f"{user.display_name} cancelled the ride to {trip.to_label}",
        },
    )
    return await get_trip(db, trip.id)


async def member_ids(db: AsyncSession, trip: Trip) -> set[int]:
    """The host plus everyone whose request was accepted: the people who share the ride."""
    riders = await db.scalars(
        select(JoinRequest.requester_id).where(
            JoinRequest.trip_id == trip.id, JoinRequest.status == RequestStatus.ACCEPTED
        )
    )
    return {trip.host_id, *riders}


async def complete_trip(db: AsyncSession, user: User, trip_id: int) -> Trip:
    """Host marks the ride done; this is what unlocks ratings."""
    trip = await _get_own_trip(db, user, trip_id)
    if trip.depart_at > utc_now() + timedelta(minutes=30):
        raise ConflictError("You can mark a ride completed once it has started")
    riders = (await member_ids(db, trip)) - {user.id}
    trip.status = TripStatus.COMPLETED
    await db.execute(
        update(JoinRequest)
        .where(JoinRequest.trip_id == trip.id, JoinRequest.status == RequestStatus.PENDING)
        .values(status=RequestStatus.DECLINED)
    )
    await db.commit()
    await invalidate_search()
    await broker.publish(
        list(riders),
        {
            "type": "trip.completed",
            "trip_id": trip.id,
            "message": "Ride completed. Rate your co-travellers to help others.",
        },
    )
    return await get_trip(db, trip.id)
