import base64
from collections.abc import Callable
from datetime import datetime

from pydantic import BaseModel

from app.services.errors import DomainError

DEFAULT_LIMIT = 20
MAX_LIMIT = 50


class Page[T](BaseModel):
    """One page of results. Pass next_cursor back as ?cursor= to get the following page."""

    items: list[T]
    next_cursor: str | None = None


def encode_cursor(at: datetime, row_id: int) -> str:
    # Opaque to clients on purpose: they pass it back, never build or parse it.
    return base64.urlsafe_b64encode(f"{at.isoformat()}|{row_id}".encode()).decode()


def decode_cursor(cursor: str) -> tuple[datetime, int]:
    try:
        at, row_id = base64.urlsafe_b64decode(cursor.encode()).decode().split("|")
        return datetime.fromisoformat(at), int(row_id)
    except ValueError:
        raise DomainError("Invalid cursor") from None


def make_page[R, T](
    rows: list[R],
    limit: int,
    cursor_of: Callable[[R], tuple[datetime, int]],
    to_item: Callable[[R], T],
) -> Page[T]:
    """rows holds up to limit + 1 items: the extra one only tells us a next page exists."""
    has_more = len(rows) > limit
    rows = rows[:limit]
    next_cursor = encode_cursor(*cursor_of(rows[-1])) if has_more else None
    return Page(items=[to_item(row) for row in rows], next_cursor=next_cursor)
