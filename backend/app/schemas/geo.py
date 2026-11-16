from pydantic import BaseModel


class GeoPlace(BaseModel):
    """One address-search result."""

    label: str  # short name, used as the pin's name: "Technopark Phase 3"
    detail: str  # the rest of the address, to tell similar names apart
    lat: float
    lng: float


class RouteOut(BaseModel):
    """A road route between two points."""

    distance_m: int
    duration_s: int  # driving time without traffic: show it as "about"
    points: list[tuple[float, float]]  # (lat, lng) along the road, ready for the map
