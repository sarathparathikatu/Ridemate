from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models import JoinRequest, RequestStatus, Trip, TripStatus, User
from app.schemas.common import utc_now
from app.services.errors import ConflictError, DomainError, ForbiddenError, NotFoundError
from app.services.trip_service import WITH_DETAILS, get_trip

WITH_TRIP = joinedload(JoinRequest.trip).options(*WITH_DETAILS)


async def _get_request(
    db: AsyncSession, request_id: int, *options, lock: bool = False
) -> JoinRequest:
    stmt = (
        select(JoinRequest)
        .options(*options)
        .where(JoinRequest.id == request_id)
        .execution_options(populate_existing=True)
    )
    if lock:
        stmt = stmt.with_for_update(of=JoinRequest)
    req = await db.scalar(stmt)
    if req is None:
        raise NotFoundError("Request not found")
    return req


async def create_request(db: AsyncSession, user: User, trip_id: int, seats: int) -> JoinRequest:
    trip = await get_trip(db, trip_id)
    if trip.host_id == user.id:
        raise DomainError("You can't join your own trip")
    if trip.status != TripStatus.OPEN:
        raise ConflictError("This trip is no longer open")
    if trip.depart_at < utc_now() - timedelta(minutes=10):
        raise ConflictError("This trip has already left")
    # Only a friendly early check: seats are really reserved at accept time, under a lock.
    if seats > trip.seats_left:
        raise ConflictError(f"Only {trip.seats_left} seat(s) left")

    existing = await db.scalar(
        select(JoinRequest).where(
            JoinRequest.trip_id == trip.id, JoinRequest.requester_id == user.id
        )
    )
    if existing is not None:
        if existing.status != RequestStatus.CANCELLED:
            raise ConflictError(f"You already have a {existing.status} request for this trip")
        existing.status, existing.seats = RequestStatus.PENDING, seats  # re-request
        req = existing
    else:
        req = JoinRequest(trip_id=trip.id, requester_id=user.id, seats=seats)
        db.add(req)
    try:
        await db.commit()
    except IntegrityError:
        # Two simultaneous requests from the same user: the UNIQUE(trip_id, requester_id)
        # index lets exactly one through.
        await db.rollback()
        raise ConflictError("You already requested this trip") from None
    return await _get_request(db, req.id, WITH_TRIP)


async def list_my_requests(db: AsyncSession, user: User) -> list[JoinRequest]:
    stmt = (
        select(JoinRequest)
        .options(WITH_TRIP)
        .where(JoinRequest.requester_id == user.id)
        .order_by(JoinRequest.created_at.desc())
        .limit(50)
    )
    return list(await db.scalars(stmt))


async def list_trip_requests(db: AsyncSession, user: User, trip_id: int) -> list[JoinRequest]:
    trip = await get_trip(db, trip_id)
    if trip.host_id != user.id:
        raise ForbiddenError("Only the host can see requests for this trip")
    stmt = (
        select(JoinRequest)
        .options(joinedload(JoinRequest.requester))
        .where(JoinRequest.trip_id == trip_id)
        .order_by(JoinRequest.created_at)
    )
    return list(await db.scalars(stmt))


async def accept_request(db: AsyncSession, user: User, request_id: int) -> JoinRequest:
    """The race-sensitive operation: two accepts for the last seat must not both win.

    Locks are always taken in the same order (trip row first, then request row) by every
    function here, so two transactions can never wait on each other in a circle (deadlock).
    """
    req = await _get_request(db, request_id)  # unlocked read, just to learn trip_id
    # SELECT ... FOR UPDATE: any other transaction trying to lock this trip row now WAITS
    # until we commit, so "check seats left, then take them" happens as one step.
    trip = await get_trip(db, req.trip_id, lock=True)
    if trip.host_id != user.id:
        raise ForbiddenError("Only the host can accept requests")
    req = await _get_request(db, request_id, lock=True)  # re-read now that we hold the lock
    if req.status != RequestStatus.PENDING:
        raise ConflictError(f"Request is already {req.status}")
    if trip.status != TripStatus.OPEN:
        raise ConflictError("This trip is no longer open")
    if req.seats > trip.seats_left:
        raise ConflictError(f"Not enough seats left ({trip.seats_left})")

    trip.seats_taken += req.seats
    if trip.seats_left == 0:
        trip.status = TripStatus.FULL
    req.status = RequestStatus.ACCEPTED
    await db.commit()  # releases the locks; a waiting transaction now sees the new seats
    return await _get_request(db, request_id, joinedload(JoinRequest.requester))


async def decline_request(db: AsyncSession, user: User, request_id: int) -> JoinRequest:
    req = await _get_request(db, request_id)
    trip = await get_trip(db, req.trip_id, lock=True)
    if trip.host_id != user.id:
        raise ForbiddenError("Only the host can decline requests")
    req = await _get_request(db, request_id, lock=True)
    if req.status != RequestStatus.PENDING:
        raise ConflictError(f"Request is already {req.status}")
    req.status = RequestStatus.DECLINED
    await db.commit()
    return await _get_request(db, request_id, joinedload(JoinRequest.requester))


async def cancel_request(db: AsyncSession, user: User, request_id: int) -> JoinRequest:
    req = await _get_request(db, request_id)
    if req.requester_id != user.id:
        raise ForbiddenError("You can only cancel your own requests")
    trip = await get_trip(db, req.trip_id, lock=True)
    req = await _get_request(db, request_id, lock=True)
    if req.status not in (RequestStatus.PENDING, RequestStatus.ACCEPTED):
        raise ConflictError(f"Request is already {req.status}")
    if req.status == RequestStatus.ACCEPTED:
        # Give the seat back, and reopen the trip if that makes room again.
        trip.seats_taken -= req.seats
        if trip.status == TripStatus.FULL:
            trip.status = TripStatus.OPEN
    req.status = RequestStatus.CANCELLED
    await db.commit()
    return await _get_request(db, request_id, WITH_TRIP)
