from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_token, new_opaque_token
from app.models import TripShare, User
from app.schemas.common import utc_now
from app.schemas.place import PlaceOut
from app.schemas.safety import ShareLinkOut, ShareView
from app.services.errors import ForbiddenError, NotFoundError
from app.services.trip_service import get_trip, member_ids

LINK_VALID_AFTER_DEPARTURE = timedelta(hours=6)


async def create_link(db: AsyncSession, user: User, trip_id: int) -> ShareLinkOut:
    trip = await get_trip(db, trip_id)
    if user.id not in await member_ids(db, trip):
        raise ForbiddenError("Only people in this ride can share it")
    token = new_opaque_token()  # 256 random bits: unguessable, so the link itself is the key
    expires_at = max(trip.depart_at, utc_now()) + LINK_VALID_AFTER_DEPARTURE
    db.add(TripShare(trip_id=trip.id, created_by=user.id, token_hash=hash_token(token), expires_at=expires_at))
    await db.commit()
    return ShareLinkOut(token=token, expires_at=expires_at)


async def view(db: AsyncSession, token: str) -> ShareView:
    share = await db.scalar(select(TripShare).where(TripShare.token_hash == hash_token(token)))
    if share is None or share.expires_at <= utc_now():
        raise NotFoundError("This link has expired or doesn't exist")
    trip = await get_trip(db, share.trip_id)
    sharer = await db.get(User, share.created_by)
    return ShareView(
        shared_by=sharer.display_name,
        host_name=trip.host.display_name,
        from_place=PlaceOut.model_validate(trip.from_place),
        to_place=PlaceOut.model_validate(trip.to_place),
        depart_at=trip.depart_at,
        vehicle=trip.vehicle,
        status=trip.status,
        riders=len(await member_ids(db, trip)),
    )
