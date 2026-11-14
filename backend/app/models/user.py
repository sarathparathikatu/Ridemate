from datetime import datetime

from sqlalchemy import String, func
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
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
