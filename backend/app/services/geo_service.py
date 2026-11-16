"""Address search and road routes, fetched from outside map services.

The browser never talks to those services itself: it asks our API, and the API asks them.
That one extra hop buys four things:

- privacy: the outside service sees our server, not each user's IP address;
- caching: a popular search or route is fetched once and reused;
- manners: we control how fast we call a free community server;
- freedom: the provider is a setting (GEOCODER_URL, ROUTING_URL), not code in every phone.

Both features are optional extras. If a service is down, blocked or switched off, the app
still works: people tap the map, and the route is drawn as a simple curve.
"""

import asyncio
import json
import logging
import ssl
import time
from functools import lru_cache

import certifi
import httpx

from app.core import kv
from app.core.config import get_settings
from app.schemas.geo import GeoPlace, RouteOut
from app.services.errors import DomainError

log = logging.getLogger(__name__)

TIMEOUT_SECONDS = 6
CACHE_SECONDS = 24 * 3600  # streets and addresses don't change by the hour
MIN_SECONDS_BETWEEN_SEARCHES = 1.0  # the public geocoder asks for at most one request a second
MAX_ROUTE_POINTS = 1500

_next_search_at = 0.0


class GeoUnavailableError(DomainError):
    status_code = 503


@lru_cache
def _tls_context() -> ssl.SSLContext:
    """Verify servers against the operating system's certificate store, like a browser does.

    (The default bundle that ships with the HTTP library doesn't know about certificates an
    organisation installs on its own machines, e.g. on a company network.)
    """
    context = ssl.create_default_context()
    if not context.cert_store_stats()["x509_ca"]:
        context.load_verify_locations(certifi.where())  # a bare system: use the bundled list
    return context


async def _get_json(url: str, params: dict[str, str | int]) -> object:
    """One GET to an outside service. Tests replace this function, so they never go online."""
    headers = {"User-Agent": get_settings().outbound_user_agent, "Accept-Language": "en"}
    try:
        async with httpx.AsyncClient(
            timeout=TIMEOUT_SECONDS, verify=_tls_context(), headers=headers
        ) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            return response.json()
    except (httpx.HTTPError, ValueError) as exc:
        # Log what kind of failure it was, never the request: addresses are personal.
        log.warning("map service call failed: %s", type(exc).__name__)
        raise GeoUnavailableError("The map service can't be reached right now.") from None


async def _wait_for_search_slot() -> None:
    """Space our address searches out. The next slot is reserved before sleeping, so
    several requests arriving together queue up instead of all going at once.
    (Per server process: several processes would share the counter through Redis.)"""
    global _next_search_at
    now = time.monotonic()
    wait = max(0.0, _next_search_at - now)
    _next_search_at = max(now, _next_search_at) + MIN_SECONDS_BETWEEN_SEARCHES
    if wait:
        await asyncio.sleep(wait)


def _to_place(row: dict) -> GeoPlace | None:
    try:
        parts = [part.strip() for part in str(row["display_name"]).split(",")]
        label = str(row.get("name") or parts[0])[:120]
        rest = [part for part in parts if part != label]
        return GeoPlace(
            label=label,
            detail=", ".join(rest[:3]),
            lat=float(row["lat"]),
            lng=float(row["lon"]),
        )
    except (KeyError, TypeError, ValueError):
        return None  # a malformed row from outside must not break the whole answer


async def search_places(query: str, near: tuple[float, float] | None = None) -> list[GeoPlace]:
    settings = get_settings()
    if not settings.geocoder_url:
        raise GeoUnavailableError("Address search isn't set up on this server.")

    query = " ".join(query.split())
    # "Prefer results around here": rounded to ~10 km, which is plenty for a preference and
    # lets everyone in the same town share cache entries.
    area = (round(near[0], 1), round(near[1], 1)) if near else None
    key = f"geo:search:{settings.geocoder_country_codes or ''}:{area or ''}:{query.lower()}"
    if (cached := await kv.get(key)) is not None:
        return [GeoPlace(**place) for place in json.loads(cached)]

    params: dict[str, str | int] = {"q": query, "format": "jsonv2", "limit": 6}
    if settings.geocoder_country_codes:
        params["countrycodes"] = settings.geocoder_country_codes
    if area:
        lat, lng = area
        # left, top, right, bottom. A preference, not a fence: far-away matches still come
        # back, just lower down.
        params["viewbox"] = f"{lng - 0.5:.1f},{lat + 0.5:.1f},{lng + 0.5:.1f},{lat - 0.5:.1f}"

    await _wait_for_search_slot()
    rows = await _get_json(f"{settings.geocoder_url.rstrip('/')}/search", params)
    places = [place for row in rows if (place := _to_place(row))] if isinstance(rows, list) else []
    await kv.set(key, json.dumps([place.model_dump() for place in places]), CACHE_SECONDS)
    return places


async def road_route(start: tuple[float, float], end: tuple[float, float]) -> RouteOut:
    settings = get_settings()
    if not settings.routing_url:
        raise GeoUnavailableError("Road routes aren't set up on this server.")

    # Rounded to ~11 m: the same route for people at the same gate, and nobody's exact
    # position leaves our server.
    (a_lat, a_lng), (b_lat, b_lng) = [(round(lat, 4), round(lng, 4)) for lat, lng in (start, end)]
    key = f"geo:route:{a_lat},{a_lng}:{b_lat},{b_lng}"
    if (cached := await kv.get(key)) is not None:
        return RouteOut.model_validate_json(cached)

    # OSRM puts longitude first.
    url = f"{settings.routing_url.rstrip('/')}/route/v1/driving/{a_lng},{a_lat};{b_lng},{b_lat}"
    data = await _get_json(url, {"overview": "full", "geometries": "geojson", "steps": "false"})
    try:
        if data["code"] != "Ok":
            raise KeyError("code")
        best = data["routes"][0]
        line = best["geometry"]["coordinates"]
        step = max(1, len(line) // MAX_ROUTE_POINTS)  # thin out very long routes
        points = [(float(lat), float(lng)) for lng, lat in line[::step]]
        if line and step > 1:
            points.append((float(line[-1][1]), float(line[-1][0])))  # always end at the end
        route = RouteOut(
            distance_m=round(best["distance"]), duration_s=round(best["duration"]), points=points
        )
    except (KeyError, IndexError, TypeError, ValueError):
        raise GeoUnavailableError("No road route was found between these two points.") from None

    await kv.set(key, route.model_dump_json(), CACHE_SECONDS)
    return route
