from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models import ReportReason, ReportResolution, ReportStatus, TripStatus
from app.schemas.common import UTCOutput


class AdminPersonOut(BaseModel):
    """What an admin sees about an account: enough to judge a report and to get in touch.
    No phone number: reviewing a report doesn't need it."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    display_name: str
    email: EmailStr
    phone_verified: bool
    rating_avg: float | None
    rating_count: int
    created_at: UTCOutput
    is_admin: bool
    is_suspended: bool
    suspended_at: UTCOutput | None
    reports_received: int = 0  # how many reports name this person; filled in by the service


class ReportTripOut(BaseModel):
    id: int
    start_label: str
    end_label: str
    depart_at: UTCOutput
    status: TripStatus


class ReportOut(BaseModel):
    id: int
    reason: ReportReason
    details: str | None
    status: ReportStatus
    created_at: UTCOutput
    reporter: AdminPersonOut
    reported: AdminPersonOut
    trip: ReportTripOut | None
    # Filled in once an admin has decided.
    resolution: ReportResolution | None
    admin_note: str | None
    reviewed_at: UTCOutput | None
    reviewed_by_name: str | None


class ReportResolve(BaseModel):
    action: Literal["dismiss", "suspend"]
    note: str | None = Field(default=None, max_length=500)


class AdminSummary(BaseModel):
    open_reports: int
    suspended_users: int
