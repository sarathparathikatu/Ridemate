from datetime import UTC, datetime
from typing import Annotated

from pydantic import AfterValidator, AwareDatetime


def to_utc_naive(value: datetime) -> datetime:
    return value.astimezone(UTC).replace(tzinfo=None)


def label_as_utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


# Incoming times must carry a timezone ("...+05:30" or "...Z"); we convert to UTC for MySQL.
# Rejecting naive times avoids the classic bug of guessing whose "6:15" it was.
UTCInput = Annotated[AwareDatetime, AfterValidator(to_utc_naive)]

# MySQL returns naive UTC values; label them UTC so clients (the browser) convert to IST.
UTCOutput = Annotated[datetime, AfterValidator(label_as_utc)]


def utc_now() -> datetime:
    """Current time as naive UTC, the same form MySQL stores."""
    return datetime.now(UTC).replace(tzinfo=None)
