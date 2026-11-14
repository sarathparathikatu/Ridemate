from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password, verify_password
from app.models import User
from app.schemas.user import UserCreate


class EmailAlreadyRegisteredError(Exception):
    pass


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    return await db.scalar(select(User).where(User.email == email))


async def create_user(db: AsyncSession, data: UserCreate) -> User:
    # bcrypt is slow CPU work; running it directly would freeze the event loop for every
    # other request. run_in_threadpool moves it to a worker thread and awaits the result.
    hashed = await run_in_threadpool(hash_password, data.password)
    user = User(
        email=data.email,
        hashed_password=hashed,
        display_name=data.display_name,
        phone=data.phone,
    )
    db.add(user)
    try:
        await db.commit()
    except IntegrityError:
        # The UNIQUE index on users.email is the real guard against duplicates,
        # even if two sign-ups for the same email arrive at the same instant.
        await db.rollback()
        raise EmailAlreadyRegisteredError(data.email) from None
    # created_at was filled in by MySQL; fetch it explicitly (async can't lazy-load it later).
    await db.refresh(user)
    return user


async def authenticate_user(db: AsyncSession, email: str, password: str) -> User | None:
    user = await get_user_by_email(db, email.lower())
    if user is None:
        return None
    if not await run_in_threadpool(verify_password, password, user.hashed_password):
        return None
    return user
