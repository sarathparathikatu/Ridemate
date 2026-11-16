"""correct place coordinates

The first coordinates were typed in from memory and some were far off (Kazhakoottam
station by 1.3 km). These come from OpenStreetMap, looked up one place at a time and
checked by hand: the result had to be the right kind of thing (a station for a station,
the suburb's own marker for an area) and near where the place was expected.

A data migration: no table changes, only rows. Rides that already exist keep the
coordinates they were posted with (each ride stores its own copy).

Revision ID: 3da2f0041c82
Revises: cd06c06f2232
Create Date: 2026-11-16 15:30:38.477916

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3da2f0041c82'
down_revision: Union[str, Sequence[str], None] = 'cd06c06f2232'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# name: ((old lat, old lng), (new lat, new lng))        what OpenStreetMap calls it, how far it moved
PLACES = {
    'Kazhakoottam Railway Station': ((8.568600, 76.873500), (8.556815, 76.872753)),  # station "Kazhakuttam", 1.3 km
    'Thiruvananthapuram Central': ((8.487500, 76.952000), (8.487017, 76.952641)),    # station, 90 m
    'Kochuveli Railway Station': ((8.500300, 76.901800), (8.510334, 76.897047)),     # station, 1.2 km
    'Kulathoor': ((8.545800, 76.880000), (8.540365, 76.880632)),                     # suburb, 610 m
    'Technopark Phase 1': ((8.558300, 76.881100), (8.557827, 76.880744)),            # campus "Technopark", 70 m
    'Technopark Phase 3': ((8.552000, 76.879000), (8.546082, 76.883640)),            # campus "Technopark Phase III", 830 m
    'Kazhakoottam Junction': ((8.567700, 76.874100), (8.566026, 76.873787)),         # suburb "Kazhakkoottam", 190 m
    'Sreekaryam': ((8.548700, 76.917500), (8.548949, 76.917187)),                    # suburb, 40 m
    'Ulloor': ((8.530000, 76.933000), (8.530005, 76.928621)),                        # suburb, 480 m
    'Medical College': ((8.523500, 76.928500), (8.523793, 76.927448)),               # the hospital building, 120 m
    'Pattom': ((8.518000, 76.942000), (8.518606, 76.942383)),                        # suburb, 80 m
    'Kesavadasapuram': ((8.529000, 76.937500), (8.529709, 76.938403)),               # suburb, 130 m
    'Thampanoor': ((8.488200, 76.953000), (8.487667, 76.952434)),                    # suburb, 90 m
    'East Fort': ((8.483000, 76.947000), (8.483568, 76.947448)),                     # the East Fort bus shelter, 80 m
}

# Kochuveli station was officially renamed in 2024; people use both names.
OLD_NAME = 'Kochuveli Railway Station'
NEW_NAME = 'Thiruvananthapuram North (Kochuveli)'

places = sa.table('places', sa.column('name', sa.String), sa.column('lat'), sa.column('lng'))


def upgrade() -> None:
    """Upgrade data."""
    for name, (_, (lat, lng)) in PLACES.items():
        op.execute(places.update().where(places.c.name == name).values(lat=lat, lng=lng))
    op.execute(places.update().where(places.c.name == OLD_NAME).values(name=NEW_NAME))


def downgrade() -> None:
    """Downgrade data: back to the approximate coordinates and the old station name."""
    op.execute(places.update().where(places.c.name == NEW_NAME).values(name=OLD_NAME))
    for name, ((lat, lng), _) in PLACES.items():
        op.execute(places.update().where(places.c.name == name).values(lat=lat, lng=lng))
