from pydantic import BaseModel, Field

from app.models import JoinRequest, RequestStatus
from app.schemas.common import UTCOutput
from app.schemas.trip import TripOut
from app.schemas.user import ContactOut, PersonOut


class JoinRequestCreate(BaseModel):
    seats: int = Field(default=1, ge=1, le=3)


class IncomingRequestOut(BaseModel):
    """What the host sees: who is asking. Contact only once the host has accepted."""

    id: int
    seats: int
    status: RequestStatus
    created_at: UTCOutput
    requester: PersonOut
    requester_contact: ContactOut | None = None

    @classmethod
    def build(cls, req: JoinRequest) -> "IncomingRequestOut":
        accepted = req.status == RequestStatus.ACCEPTED
        return cls(
            id=req.id,
            seats=req.seats,
            status=req.status,
            created_at=req.created_at,
            requester=PersonOut.model_validate(req.requester),
            requester_contact=ContactOut.model_validate(req.requester) if accepted else None,
        )


class MyRequestOut(BaseModel):
    """What the rider sees: the trip they asked to join. Host contact once accepted."""

    id: int
    seats: int
    status: RequestStatus
    created_at: UTCOutput
    trip: TripOut
    host_contact: ContactOut | None = None

    @classmethod
    def build(cls, req: JoinRequest) -> "MyRequestOut":
        accepted = req.status == RequestStatus.ACCEPTED
        return cls(
            id=req.id,
            seats=req.seats,
            status=req.status,
            created_at=req.created_at,
            trip=TripOut.model_validate(req.trip),
            host_contact=ContactOut.model_validate(req.trip.host) if accepted else None,
        )
