from typing import Literal

from pydantic import BaseModel, Field

from app.models import ReportReason, TripStatus, Vehicle
from app.schemas.common import UTCOutput
from app.schemas.trip import LocationOut

RatingTag = Literal["on_time", "friendly", "easy_to_find", "felt_safe"]


class PhoneOtpRequest(BaseModel):
    phone: str = Field(pattern=r"^\+?[0-9]{10,15}$")


class OtpSent(BaseModel):
    expires_in_seconds: int
    # Only in development (OTP_DEV_ECHO=true), so you can test without an SMS provider.
    dev_code: str | None = None


class PhoneVerifyRequest(BaseModel):
    code: str = Field(pattern=r"^[0-9]{6}$")


class RatingCreate(BaseModel):
    rated_user_id: int
    stars: int = Field(ge=1, le=5)
    tags: list[RatingTag] = []
    comment: str | None = Field(default=None, max_length=500)


class ReportCreate(BaseModel):
    reason: ReportReason
    trip_id: int | None = None
    details: str | None = Field(default=None, max_length=1000)


class BlockedUserOut(BaseModel):
    id: int
    display_name: str


class ShareLinkOut(BaseModel):
    token: str  # the frontend turns it into <app>/share/<token>
    expires_at: UTCOutput


class ShareView(BaseModel):
    """What family sees through a share link: enough to follow the ride, no contacts."""

    shared_by: str
    host_name: str
    start: LocationOut
    end: LocationOut
    depart_at: UTCOutput
    vehicle: Vehicle
    status: TripStatus
    riders: int  # how many people share the ride, host included
