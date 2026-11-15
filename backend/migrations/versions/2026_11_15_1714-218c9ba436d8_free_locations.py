"""free locations

Rides start and end at any point (GPS, a map pin or a known place) instead of only the
fixed places list, so RideMate works in every city.

Revision ID: 218c9ba436d8
Revises: f1499cc616cb
Create Date: 2026-11-15 17:14:05.649916

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = '218c9ba436d8'
down_revision: Union[str, Sequence[str], None] = 'f1499cc616cb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NEW_COLUMNS = {
    'from_lat': sa.Numeric(precision=9, scale=6),
    'from_lng': sa.Numeric(precision=9, scale=6),
    'from_label': sa.String(length=120),
    'to_lat': sa.Numeric(precision=9, scale=6),
    'to_lng': sa.Numeric(precision=9, scale=6),
    'to_label': sa.String(length=120),
}


def upgrade() -> None:
    """Upgrade schema."""
    # Hand-edited. Trips may already exist, so the usual three steps:
    # 1) add the columns as nullable...
    for name, type_ in NEW_COLUMNS.items():
        op.add_column('trips', sa.Column(name, type_, nullable=True))
    # 2) ...copy every existing trip's coordinates and names from its places...
    op.execute(
        "UPDATE trips t"
        " JOIN places f ON f.id = t.from_place_id"
        " JOIN places d ON d.id = t.to_place_id"
        " SET t.from_lat = f.lat, t.from_lng = f.lng, t.from_label = f.name,"
        "     t.to_lat = d.lat, t.to_lng = d.lng, t.to_label = d.name"
    )
    # 3) ...then make them required.
    for name, type_ in NEW_COLUMNS.items():
        op.alter_column('trips', name, existing_type=type_, nullable=False)

    # A known place is now optional: a ride can start at a GPS point or a map pin.
    for name in ('from_place_id', 'to_place_id'):
        op.alter_column('trips', name, existing_type=mysql.INTEGER(), nullable=True)

    # A POINT that MySQL computes and stores from the coordinates, carrying a SPATIAL
    # index. Plain SQL: Alembic has no built-in type for MySQL's POINT, and a migration
    # must not import app code (the code will change; this file must keep working).
    # For a generated column MySQL wants the SRID attribute after NOT NULL
    # ("POINT SRID 0 GENERATED ..." is a syntax error). The SRID is what lets the
    # optimizer use the SPATIAL index.
    op.execute(
        "ALTER TABLE trips ADD COLUMN from_point POINT"
        " GENERATED ALWAYS AS (point(`from_lng`,`from_lat`)) STORED NOT NULL SRID 0"
    )
    op.create_index('ix_trips_from_point', 'trips', ['from_point'], unique=False, mysql_prefix='SPATIAL')
    op.create_index('ix_trips_open_by_time', 'trips', ['status', 'depart_at'], unique=False)


def downgrade() -> None:
    """Downgrade schema.

    DATA LOSS: rides that start or end at a free location (no known place) can't be
    represented in the old schema, so they are deleted.
    """
    op.drop_index('ix_trips_open_by_time', table_name='trips')
    op.drop_index('ix_trips_from_point', table_name='trips')
    op.drop_column('trips', 'from_point')
    op.execute("DELETE FROM trips WHERE from_place_id IS NULL OR to_place_id IS NULL")
    for name in ('to_place_id', 'from_place_id'):
        op.alter_column('trips', name, existing_type=mysql.INTEGER(), nullable=False)
    for name in reversed(NEW_COLUMNS):
        op.drop_column('trips', name)
