"""Learning demo: watch the SQL that SQLAlchemy sends for each Python line.

Needs the tables (run `uv run alembic upgrade head` first).
Run from backend/:  uv run python -m scripts.demo_orm
Cleans up after itself, so it is safe to run repeatedly.
"""

import asyncio
from datetime import timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.models import Place, Trip, User
from app.schemas.common import utc_now


def step(msg: str) -> None:
    print(f"\n===== {msg} =====")


async def main() -> None:
    # echo=True prints every SQL statement; this is the whole point of the demo.
    engine = create_async_engine(get_settings().database_url, echo=True)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    async with Session() as session:
        step("1. Create a Python object (no SQL yet)")
        user = User(email="demo@example.com", hashed_password="not-a-real-hash", display_name="Demo")
        session.add(user)
        print("user.id before commit:", user.id)

        step("2. commit() -> INSERT")
        await session.commit()
        print("user.id after commit:", user.id, "(filled in by AUTO_INCREMENT)")

        step("3. Look up places by name -> SELECT")
        station = await session.scalar(select(Place).where(Place.name == "Kazhakoottam Railway Station"))
        kulathoor = await session.scalar(select(Place).where(Place.name == "Kulathoor"))

        step("4. Post a trip for that user -> INSERT")
        trip = Trip(
            host_id=user.id,
            from_place_id=station.id,
            to_place_id=kulathoor.id,
            depart_at=utc_now() + timedelta(minutes=30),
            seats_total=2,
        )
        session.add(trip)
        await session.commit()

        step("5. Change an attribute -> UPDATE on commit")
        trip.note = "Near the main exit"
        await session.commit()

        step("6. Query -> SELECT, rows come back as Trip objects")
        for t in await session.scalars(select(Trip).where(Trip.host_id == user.id)):
            print(f"Trip object: id={t.id} seats_left={t.seats_left} note={t.note!r}")

        step("7. Clean up: delete the user (ON DELETE CASCADE removes the trip)")
        await session.execute(delete(User).where(User.id == user.id))
        await session.commit()

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
