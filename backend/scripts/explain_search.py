"""Learning demo: how MySQL answers "open rides starting near me, around now".

Seeds 30,000 fake rides with start points scattered over ~100 km, then runs the real
search condition three ways and prints MySQL's plan and timing for each:
  1. no index at all     -> scans every row
  2. time index only     -> (status, depart_at) narrows to the time window
  3. SPATIAL index       -> the R-tree finds rides starting inside a 2 km box
Deletes everything it created at the end.
Run from backend/:  uv run python -m scripts.explain_search
"""

import asyncio
import random
from datetime import timedelta

from sqlalchemy import text

from app.core.geo import bounding_box_wkt
from app.db.session import engine
from app.schemas.common import utc_now

N_TRIPS = 30_000
DEMO_EMAIL = "explain-demo@example.com"
CENTER = (8.5241, 76.9366)  # Thiruvananthapuram
SPREAD_DEG = 0.45  # ~50 km in each direction

# Raw SQL on purpose: this is about what MySQL itself does with the query.
SEARCH = """
SELECT id, depart_at FROM trips {hint}
WHERE MBRContains(ST_GeomFromText(:box, 0), from_point)
  AND ST_Distance_Sphere(POINT(from_lng, from_lat), POINT(:lng, :lat)) <= 1000
  AND status = 'open'
  AND depart_at BETWEEN :earliest AND :latest
ORDER BY depart_at, id
LIMIT 21
"""

PLANS = [
    ("1. No index at all", "IGNORE INDEX (ix_trips_from_point, ix_trips_open_by_time, ix_trips_search)"),
    ("2. Time index only", "IGNORE INDEX (ix_trips_from_point)"),
    ("3. MySQL's own choice (SPATIAL index available)", ""),
]


async def seed(conn) -> None:
    await conn.execute(
        text("INSERT INTO users (email, hashed_password, display_name) VALUES (:e, 'x', 'Explain demo')"),
        {"e": DEMO_EMAIL},
    )
    host_id = (await conn.execute(text("SELECT id FROM users WHERE email = :e"), {"e": DEMO_EMAIL})).scalar_one()
    now = utc_now()
    rows = []
    for _ in range(N_TRIPS):
        lat = CENTER[0] + random.uniform(-SPREAD_DEG, SPREAD_DEG)
        lng = CENTER[1] + random.uniform(-SPREAD_DEG, SPREAD_DEG)
        rows.append(
            {
                "host": host_id,
                "flat": lat, "flng": lng, "tlat": lat + 0.02, "tlng": lng + 0.02,
                "at": now + timedelta(minutes=random.randint(-3 * 24 * 60, 3 * 24 * 60)),
                "status": random.choices(["open", "full", "cancelled", "completed"], [6, 1, 1, 2])[0],
            }
        )
    await conn.execute(
        text(
            "INSERT INTO trips (host_id, from_lat, from_lng, from_label, to_lat, to_lng, to_label,"
            " depart_at, seats_total, status)"
            " VALUES (:host, :flat, :flng, 'demo', :tlat, :tlng, 'demo', :at, 2, :status)"
        ),
        rows,
    )
    await conn.execute(text("ANALYZE TABLE trips"))  # refresh the optimizer's statistics


async def show_plan(conn, label: str, hint: str, params: dict) -> None:
    sql = SEARCH.format(hint=hint)
    row = (await conn.execute(text("EXPLAIN " + sql), params)).mappings().one()
    analyze = (await conn.execute(text("EXPLAIN ANALYZE " + sql), params)).scalar_one()
    first_line = analyze.strip().splitlines()[0]
    print(f"\n===== {label} =====")
    print(f"type={row['type']}  key={row['key']}  rows examined (estimate)={row['rows']}")
    print(f"Extra: {row['Extra']}")
    print(f"Real execution: {first_line.strip()}")


async def main() -> None:
    async with engine.connect() as conn:
        print(f"Seeding {N_TRIPS:,} rides scattered over ~100 km...")
        try:
            await seed(conn)
            await conn.commit()
            now = utc_now()
            lat, lng = CENTER
            params = {
                "box": bounding_box_wkt(lat, lng, 1000),
                "lat": lat,
                "lng": lng,
                "earliest": now - timedelta(minutes=45),
                "latest": now + timedelta(minutes=45),
            }
            for label, hint in PLANS:
                await show_plan(conn, label, hint, params)
        finally:
            await conn.execute(text("DELETE FROM users WHERE email = :e"), {"e": DEMO_EMAIL})  # cascades
            await conn.commit()
            print("\nCleaned up the demo data.")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
