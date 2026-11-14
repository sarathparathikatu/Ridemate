"""Stage 1 sanity check: print the DDL our models generate, then ping MySQL.

Run from backend/:  python -m scripts.check_db [--ddl-only]
"""

import asyncio
import sys

from sqlalchemy import text
from sqlalchemy.dialects import mysql
from sqlalchemy.schema import CreateTable

import app.models  # noqa: F401  registers User and Task on Base.metadata
from app.db.base import Base


def print_ddl() -> None:
    # sorted_tables is FK-dependency order: users must exist before tasks can reference it.
    for table in Base.metadata.sorted_tables:
        print(str(CreateTable(table).compile(dialect=mysql.dialect())).strip() + ";\n")


async def ping() -> None:
    from app.db.session import engine  # imported here so --ddl-only works without a .env

    async with engine.connect() as conn:
        row = (
            await conn.execute(
                text(
                    "SELECT VERSION(), DATABASE(), @@character_set_database,"
                    " @@collation_database, @@default_storage_engine, @@session.time_zone"
                )
            )
        ).one()
    await engine.dispose()

    labels = ["version", "database", "charset", "collation", "engine", "time_zone"]
    for label, value in zip(labels, row):
        print(f"{label:>10}: {value}")


if __name__ == "__main__":
    print_ddl()
    if "--ddl-only" not in sys.argv:
        asyncio.run(ping())
