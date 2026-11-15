from datetime import datetime

from sqlalchemy import String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import MYSQL_TABLE_ARGS, Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = MYSQL_TABLE_ARGS

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    # unique=True -> MySQL builds a unique index, so login lookups by email are fast.
    email: Mapped[str] = mapped_column(String(255), unique=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(50))  # shown to co-travellers
    # Optional, and only revealed to people in the same accepted ride.
    phone: Mapped[str | None] = mapped_column(String(20))
    phone_verified_at: Mapped[datetime | None]
    # Denormalised rating totals: showing "4.8 from 12 rides" next to every search result
    # would otherwise need an AVG() over the ratings table per host. Updated atomically
    # (rating_sum = rating_sum + n) in the same transaction as each new rating.
    rating_sum: Mapped[int] = mapped_column(default=0, server_default=text("0"))
    rating_count: Mapped[int] = mapped_column(default=0, server_default=text("0"))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    @property
    def phone_verified(self) -> bool:
        return self.phone_verified_at is not None

    @property
    def rating_avg(self) -> float | None:
        return round(self.rating_sum / self.rating_count, 1) if self.rating_count else None
