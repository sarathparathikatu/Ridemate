import enum

from sqlalchemy import Enum, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import MYSQL_TABLE_ARGS, Base, enum_values


class PlaceKind(enum.StrEnum):
    STATION = "station"
    AREA = "area"


class Place(Base):
    """A fixed pickup/drop point. Seeded by migration; users pick from this list."""

    __tablename__ = "places"
    __table_args__ = MYSQL_TABLE_ARGS

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    kind: Mapped[PlaceKind] = mapped_column(Enum(PlaceKind, values_callable=enum_values))
