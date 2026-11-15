# Importing every model here registers it on Base.metadata; Alembic relies on this.
from app.models.join_request import JoinRequest, RequestStatus
from app.models.place import Place, PlaceKind
from app.models.refresh_token import RefreshToken
from app.models.safety import Block, Rating, Report, ReportReason, ReportStatus, TripShare
from app.models.trip import Trip, TripStatus, Vehicle
from app.models.user import User

__all__ = [
    "Block",
    "Rating",
    "Report",
    "ReportReason",
    "ReportStatus",
    "TripShare",
    "JoinRequest",
    "Place",
    "PlaceKind",
    "RefreshToken",
    "RequestStatus",
    "Trip",
    "TripStatus",
    "User",
    "Vehicle",
]
