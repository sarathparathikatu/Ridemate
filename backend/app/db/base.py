import enum

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

# Deterministic constraint names, so Alembic can later find and drop/alter them by name.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

# Applied to every table: InnoDB for transactions + real foreign keys,
# utf8mb4 so emoji and all of Unicode fit (MySQL's "utf8" is a 3-byte subset).
MYSQL_TABLE_ARGS = {
    "mysql_engine": "InnoDB",
    "mysql_charset": "utf8mb4",
    "mysql_collate": "utf8mb4_0900_ai_ci",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def enum_values(enum_cls: type[enum.Enum]) -> list[str]:
    # Store an enum's values ("open") in MySQL ENUM columns, not its member names ("OPEN").
    return [member.value for member in enum_cls]
