# Importing every model here registers it on Base.metadata; Alembic relies on this.
from app.models.join_request import JoinRequest, RequestStatus
from app.models.place import Place, PlaceKind
from app.models.trip import Trip, TripStatus, Vehicle
from app.models.user import User

__all__ = [
    "JoinRequest",
    "Place",
    "PlaceKind",
    "RequestStatus",
    "Trip",
    "TripStatus",
    "User",
    "Vehicle",
]
