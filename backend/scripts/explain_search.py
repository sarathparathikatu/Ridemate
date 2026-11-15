"""Learning demo: what the ix_trips_search index changes, proven with MySQL's EXPLAIN.

Seeds 30,000 fake trips, runs the search query with the index ignored and with it used,
prints both plans and timings, then deletes everything it created.
Run from backend/:  uv run python -m scripts.explain_search
"""

import asyncio
import random
from datetime import timedelta

from sqlalchemy import text

from app.db.session import engine
from app.schemas.common import utc_now

N_TRIPS = 30_000
DEMO_EMAIL = "explain-demo@example.com"

# Raw SQL on purpose: this is about what MySQL itself does with the query.
SEARCH = """
SELECT id, depart_at FROM trips {hint}
WHERE from_place_id = :station AND status = 'open'
  AND depart_at BETWEEN :earliest AND :latest
ORDER BY depart_at, id
LIMIT 21
"""


async def seed(conn) -> tuple[int, int]:
    await conn.execute(
        text("INSERT INTO users (email, hashed_password, display_name) VALUES (:e, 'x', 'Explain demo')"),
        {"e": DEMO_EMAIL},
    )
    host_id = (await conn.execute(text("SELECT id FROM users WHERE email = :e"), {"e": DEMO_EMAIL})).scalar_one()
    stations = [r[0] for r in await conn.execute(text("SELECT id FROM places WHERE kind = 'station'"))]
    areas = [r[0] for r in await conn.execute(text("SELECT id FROM places WHERE kind = 'area'"))]
    now = utc_now()
    rows = [
        {
            "host": host_id,
            "src": random.choice(stations),
            "dst": random.choice(areas),
            "at": now + timedelta(minutes=random.randint(-3 * 24 * 60, 3 * 24 * 60)),
            "status": random.choices(["open", "full", "cancelled", "completed"], [6, 1, 1, 2])[0],
        }
        for _ in range(N_TRIPS)
    ]
    await conn.execute(
        text(
            "INSERT INTO trips (host_id, from_place_id, to_place_id, depart_at, seats_total, status)"
            " VALUES (:host, :src, :dst, :at, 2, :status)"
        ),
        rows,
    )
    await conn.execute(text("ANALYZE TABLE trips"))  # refresh the optimizer's statistics
    return host_id, stations[0]


async def show_plan(conn, label: str, hint: str, params: dict) -> None:
    sql = SEARCH.format(hint=hint)
    row = (await conn.execute(text("EXPLAIN " + sql), params)).mappings().one()
    analyze = (await conn.execute(text("EXPLAIN ANALYZE " + sql), params)).scalar_one()
    print(f"\n===== {label} =====")
    print(f"type={row['type']}  key={row['key']}  rows examined (estimate)={row['rows']}")
    print(f"Extra: {row['Extra']}")
    print("EXPLAIN ANALYZE (real execution):")
    print(analyze)


async def main() -> None:
    async with engine.connect() as conn:
        print(f"Seeding {N_TRIPS:,} trips...")
        try:
            host_id, station = await seed(conn)
            await conn.commit()
            now = utc_now()
            params = {"station": station, "earliest": now - timedelta(minutes=30), "latest": now + timedelta(minutes=30)}
            await show_plan(conn, "BEFORE: index ignored", "IGNORE INDEX (ix_trips_search)", params)
            await show_plan(conn, "AFTER: using ix_trips_search", "", params)
        finally:
            await conn.execute(text("DELETE FROM users WHERE email = :e"), {"e": DEMO_EMAIL})  # cascades
            await conn.commit()
            print("\nCleaned up the demo data.")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
