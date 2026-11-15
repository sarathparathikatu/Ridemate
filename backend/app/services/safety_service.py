from sqlalchemy import delete, or_, select, update
from sqlalchemy.dialects.mysql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Block, JoinRequest, Report, RequestStatus, Trip, User
from app.schemas.safety import BlockedUserOut, ReportCreate
from app.services.errors import DomainError, NotFoundError


async def hidden_user_ids(db: AsyncSession, user_id: int) -> set[int]:
    """Everyone this user blocked, plus everyone who blocked this user (works both ways)."""
    rows = await db.execute(
        select(Block.blocker_id, Block.blocked_id).where(
            or_(Block.blocker_id == user_id, Block.blocked_id == user_id)
        )
    )
    return {blocked if blocker == user_id else blocker for blocker, blocked in rows}


async def is_blocked_between(db: AsyncSession, a: int, b: int) -> bool:
    return b in await hidden_user_ids(db, a)


async def block(db: AsyncSession, user: User, other_id: int) -> None:
    if other_id == user.id:
        raise DomainError("You can't block yourself")
    if await db.get(User, other_id) is None:
        raise NotFoundError("User not found")
    # INSERT IGNORE (MySQL): blocking twice is harmless instead of a duplicate-key error.
    await db.execute(insert(Block).prefix_with("IGNORE").values(blocker_id=user.id, blocked_id=other_id))
    # Close any pending requests between the two, in either direction.
    their_trips = select(Trip.id).where(Trip.host_id == other_id)
    my_trips = select(Trip.id).where(Trip.host_id == user.id)
    await db.execute(
        update(JoinRequest)
        .where(
            JoinRequest.status == RequestStatus.PENDING,
            or_(
                (JoinRequest.requester_id == other_id) & JoinRequest.trip_id.in_(my_trips),
                (JoinRequest.requester_id == user.id) & JoinRequest.trip_id.in_(their_trips),
            ),
        )
        .values(status=RequestStatus.DECLINED)
    )
    await db.commit()


async def unblock(db: AsyncSession, user: User, other_id: int) -> None:
    await db.execute(delete(Block).where(Block.blocker_id == user.id, Block.blocked_id == other_id))
    await db.commit()


async def list_blocked(db: AsyncSession, user: User) -> list[BlockedUserOut]:
    rows = await db.execute(
        select(User.id, User.display_name)
        .join(Block, Block.blocked_id == User.id)
        .where(Block.blocker_id == user.id)
        .order_by(User.display_name)
    )
    return [BlockedUserOut(id=uid, display_name=name) for uid, name in rows]


async def report(db: AsyncSession, user: User, other_id: int, data: ReportCreate) -> None:
    if other_id == user.id:
        raise DomainError("You can't report yourself")
    if await db.get(User, other_id) is None:
        raise NotFoundError("User not found")
    db.add(Report(reporter_id=user.id, reported_id=other_id, **data.model_dump()))
    await db.commit()
