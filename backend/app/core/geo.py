"""Small geography helpers. Coordinates are WGS84 degrees (what GPS and maps use)."""

import math

EARTH_RADIUS_M = 6_371_000
METERS_PER_DEGREE_LAT = 111_320  # one degree of latitude is ~111 km everywhere


def distance_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle ("as the crow flies") distance in metres: the haversine formula, the
    same calculation MySQL's ST_Distance_Sphere does."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


def bounding_box_wkt(lat: float, lng: float, radius_m: float) -> str:
    """A square around a point, as WKT for MySQL. Used to let the SPATIAL index find
    candidates fast; the exact circular distance is checked afterwards.

    Coordinates are written x=longitude, y=latitude, matching POINT(lng, lat) columns.
    """
    dlat = radius_m / METERS_PER_DEGREE_LAT
    # Lines of longitude get closer together away from the equator, so a metre is more
    # degrees of longitude than of latitude.
    dlng = radius_m / (METERS_PER_DEGREE_LAT * math.cos(math.radians(lat)))
    w, e, s, n = lng - dlng, lng + dlng, lat - dlat, lat + dlat
    return f"POLYGON(({w} {s}, {e} {s}, {e} {n}, {w} {n}, {w} {s}))"
