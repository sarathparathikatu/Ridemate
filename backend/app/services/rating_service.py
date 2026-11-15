from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Rating, TripStatus, User
from app.schemas.safety import RatingCreate
from app.services.errors import ConflictError, DomainError, ForbiddenError
from app.services.trip_service import get_trip, member_ids


async def rate(db: AsyncSession, user: User, trip_id: int, data: RatingCreate) -> None:
    trip = await get_trip(db, trip_id)
    if trip.status != TripStatus.COMPLETED:
        raise ConflictError("You can rate co-travellers once the ride is completed")
    if data.rated_user_id == user.id:
        raise DomainError("You can't rate yourself")
    members = await member_ids(db, trip)
    if user.id not in members or data.rated_user_id not in members:
        raise ForbiddenError("Only people who shared this ride can rate each other")

    db.add(
        Rating(
            trip_id=trip.id,
            rater_id=user.id,
            rated_id=data.rated_user_id,
            stars=data.stars,
            tags=",".join(data.tags) or None,
            comment=data.comment,
        )
    )
    try:
        await db.flush()  # the UNIQUE(trip, rater, rated) index stops double ratings
    except IntegrityError:
        await db.rollback()
        raise ConflictError("You already rated this person for this ride") from None
    # The arithmetic runs inside MySQL (SET rating_sum = rating_sum + 5), so two ratings
    # arriving at once can't overwrite each other, as reading then writing in Python could.
    await db.execute(
        update(User)
        .where(User.id == data.rated_user_id)
        .values(rating_sum=User.rating_sum + data.stars, rating_count=User.rating_count + 1)
    )
    await db.commit()
