from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.dependencies.auth import CurrentUser
from app.dependencies.rate_limit import per_user
from app.schemas.geo import GeoPlace, RouteOut
from app.services import geo_service

router = APIRouter(prefix="/geo", tags=["maps"])

Lat = Annotated[float, Query(ge=-90, le=90)]
Lng = Annotated[float, Query(ge=-180, le=180)]


# Logged-in users only, and rate limited: otherwise anyone on the internet could use our
# server as a free relay to someone else's map service.
@router.get(
    "/search",
    response_model=list[GeoPlace],
    dependencies=[Depends(per_user("geo-search", limit=20, window_seconds=60))],
)
async def search_places(
    current_user: CurrentUser,
    q: Annotated[str, Query(min_length=3, max_length=100)],
    near_lat: Annotated[float | None, Query(ge=-90, le=90)] = None,
    near_lng: Annotated[float | None, Query(ge=-180, le=180)] = None,
) -> list[GeoPlace]:
    """Find places by name or address. `near_*` makes nearby matches come first."""
    near = (near_lat, near_lng) if near_lat is not None and near_lng is not None else None
    return await geo_service.search_places(q, near)


@router.get(
    "/route",
    response_model=RouteOut,
    dependencies=[Depends(per_user("geo-route", limit=40, window_seconds=60))],
)
async def road_route(
    current_user: CurrentUser, from_lat: Lat, from_lng: Lng, to_lat: Lat, to_lng: Lng
) -> RouteOut:
    """The road route between two points, with its distance and driving time."""
    return await geo_service.road_route((from_lat, from_lng), (to_lat, to_lng))
