"""RideMate MCP server: lets Claude find, post and join RideMate rides with your account.

It speaks MCP over stdio: the client (Claude Desktop, MCP Inspector...) starts this script
and exchanges messages through its stdin/stdout. So never print() to stdout here; it would
corrupt the protocol stream (logs go to stderr).

Configuration (environment variables):
    RIDEMATE_API_URL   default http://localhost:8000
    RIDEMATE_EMAIL     your RideMate login
    RIDEMATE_PASSWORD
"""

import json
import os
from datetime import UTC, datetime, timedelta, timezone
from typing import Annotated, Any, Literal

import httpx
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import Field

API_URL = os.environ.get("RIDEMATE_API_URL", "http://localhost:8000")
DEFAULT_PICKUP = "Kazhakoottam Railway Station"
IST = timezone(timedelta(hours=5, minutes=30), "IST")  # India has no daylight saving


class RideMateAPI:
    """The RideMate REST API, used as one logged-in user. Handles tokens by itself."""

    def __init__(self, base_url: str, email: str, password: str) -> None:
        self._http = httpx.AsyncClient(base_url=base_url, timeout=20)
        self._email, self._password = email, password
        self._access: str | None = None
        self._refresh: str | None = None
        self._places: list[dict] | None = None

    async def _login(self) -> None:
        r = await self._http.post("/auth/login", data={"username": self._email, "password": self._password})
        if r.status_code != 200:
            raise ToolError("RideMate login failed: check RIDEMATE_EMAIL and RIDEMATE_PASSWORD")
        self._store(r.json())

    def _store(self, tokens: dict) -> None:
        self._access, self._refresh = tokens["access_token"], tokens["refresh_token"]

    async def _renew(self) -> None:
        # Same rule as the web app: try the refresh token first, log in again if that fails.
        if self._refresh:
            r = await self._http.post("/auth/refresh", json={"refresh_token": self._refresh})
            if r.status_code == 200:
                self._store(r.json())
                return
        await self._login()

    async def call(self, method: str, path: str, **kwargs: Any) -> Any:
        if self._access is None:
            await self._login()
        for attempt in (1, 2):
            r = await self._http.request(
                method, path, headers={"Authorization": f"Bearer {self._access}"}, **kwargs
            )
            if r.status_code == 401 and attempt == 1:
                await self._renew()  # access token expired mid-conversation
                continue
            break
        if r.is_error:
            detail = r.json().get("detail") if "json" in r.headers.get("content-type", "") else r.text
            if isinstance(detail, list):  # FastAPI validation errors
                detail = "; ".join(d.get("msg", "") for d in detail)
            # ToolError messages reach the model, which can explain them to the user. Any
            # other exception is reported only as "unexpected error" (no internals leak).
            raise ToolError(f"RideMate said: {detail}")
        return r.json() if r.content else None

    async def place_id(self, name: str) -> int:
        """Resolve a place name the way a person would type it ("kulathoor", "technopark 1")."""
        if self._places is None:
            self._places = await self.call("GET", "/places")
        wanted = name.strip().lower()
        exact = [p for p in self._places if p["name"].lower() == wanted]
        if exact:
            return exact[0]["id"]
        partial = [p for p in self._places if all(word in p["name"].lower() for word in wanted.split())]
        if len(partial) == 1:
            return partial[0]["id"]
        options = ", ".join(p["name"] for p in (partial or self._places))
        raise ToolError(f"Which place did you mean by {name!r}? Options: {options}")


_api: RideMateAPI | None = None


def api() -> RideMateAPI:
    # Created on first use, so the server still starts (and lists its tools) without
    # credentials; the first tool call then explains what's missing.
    global _api
    if _api is None:
        email, password = os.environ.get("RIDEMATE_EMAIL"), os.environ.get("RIDEMATE_PASSWORD")
        if not email or not password:
            raise ToolError("Set RIDEMATE_EMAIL and RIDEMATE_PASSWORD in the MCP server config")
        _api = RideMateAPI(API_URL, email, password)
    return _api


def ist(iso: str) -> str:
    return datetime.fromisoformat(iso).astimezone(IST).strftime("%a %d %b, %I:%M %p IST")


def ride_summary(trip: dict) -> dict:
    share = None
    if trip.get("fare_estimate"):
        share = -(-trip["fare_estimate"] // (2 + trip["seats_taken"]))  # host + riders + you, rounded up
    return {
        "trip_id": trip["id"],
        "departs": ist(trip["depart_at"]),
        "route": f'{trip["start"]["label"]} -> {trip["end"]["label"]}',
        "match": (trip.get("match") or "").replace("_", " ") or None,
        "starts_from_you_m": trip.get("pickup_distance_m"),
        "host": trip["host"]["display_name"],
        "host_verified": trip["host"]["phone_verified"],
        "host_rating": trip["host"]["rating_avg"],
        "seats_left": trip["seats_left"],
        "vehicle": trip["vehicle"],
        "fare_total_inr": trip.get("fare_estimate"),
        "your_share_estimate_inr": share,
        "note": trip.get("note"),
        "status": trip["status"],
    }


mcp = MCPServer(
    "RideMate",
    instructions=(
        "RideMate helps people arriving at the same railway station share one auto or cab. "
        "Use find_co_travellers to look for rides, post_trip to offer one, request_to_join to "
        "ask for a seat. Times must include a timezone; the user is in India (UTC+05:30). "
        "Confirm with the user before posting a ride or requesting to join one."
    ),
)

Place = Annotated[str, Field(description='A place name, e.g. "Kulathoor" (see list_places)')]


@mcp.tool(annotations=ToolAnnotations(read_only_hint=True))
async def list_places() -> list[dict]:
    """List the pickup and drop points RideMate knows (stations and areas in Thiruvananthapuram)."""
    places = await api().call("GET", "/places")
    return [{"name": p["name"], "kind": p["kind"]} for p in places]


Lat = Annotated[float | None, Field(ge=-90, le=90)]
Lng = Annotated[float | None, Field(ge=-180, le=180)]


@mcp.tool(annotations=ToolAnnotations(read_only_hint=True))
async def find_co_travellers(
    destination: Annotated[
        str | None, Field(description='A place name, e.g. "Kulathoor". Or give destination_lat/lng')
    ] = None,
    pickup: Annotated[
        str | None, Field(description="A place name. Or give pickup_lat/lng. Default: Kazhakoottam Railway Station")
    ] = None,
    destination_lat: Lat = None,
    destination_lng: Lng = None,
    pickup_lat: Lat = None,
    pickup_lng: Lng = None,
    around: Annotated[
        str | None,
        Field(description='ISO 8601 time WITH timezone, e.g. "2026-11-16T06:15:00+05:30". Default: now'),
    ] = None,
    window_minutes: Annotated[int, Field(ge=5, le=180, description="Look this many minutes before/after")] = 45,
) -> list[dict]:
    """Find open rides by other people starting within 1 km of the pickup around a time, going
    to the destination or passing it on the way. Places can be names (known places) or
    coordinates (works in any city). Returns host, rating, seats left, fare share."""
    params: dict[str, Any] = {"window_minutes": window_minutes}
    if pickup_lat is not None and pickup_lng is not None:
        params |= {"from_lat": pickup_lat, "from_lng": pickup_lng}
    else:
        params["from_place_id"] = await api().place_id(pickup or DEFAULT_PICKUP)
    if destination_lat is not None and destination_lng is not None:
        params |= {"to_lat": destination_lat, "to_lng": destination_lng}
    elif destination:
        params["to_place_id"] = await api().place_id(destination)
    else:
        raise ToolError("Say where the user is going: a place name or destination_lat/lng")
    if around:
        params["at"] = around
    page = await api().call("GET", "/trips/search", params=params)
    return [ride_summary(t) for t in page["items"]]


@mcp.tool(annotations=ToolAnnotations(read_only_hint=False, destructive_hint=False))
async def post_trip(
    destination: Place,
    depart_at: Annotated[str, Field(description='ISO 8601 WITH timezone, e.g. "2026-11-16T06:15:00+05:30"')],
    pickup: Place = DEFAULT_PICKUP,
    seats: Annotated[int, Field(ge=1, le=3, description="Seats offered to others")] = 2,
    vehicle: Literal["auto", "cab", "any"] = "auto",
    fare_estimate_inr: Annotated[int | None, Field(ge=0, le=5000)] = None,
    note: Annotated[str | None, Field(max_length=200, description="e.g. where to meet")] = None,
) -> dict:
    """Offer a ride as host: you book the auto/cab and others from your train join you."""
    body = {
        "from_place_id": await api().place_id(pickup),
        "to_place_id": await api().place_id(destination),
        "depart_at": depart_at,
        "seats_total": seats,
        "vehicle": vehicle,
        "fare_estimate": fare_estimate_inr,
        "note": note,
    }
    return ride_summary(await api().call("POST", "/trips", json=body))


@mcp.tool(annotations=ToolAnnotations(read_only_hint=False, destructive_hint=False))
async def request_to_join(
    trip_id: Annotated[int, Field(description="trip_id from find_co_travellers")],
    seats: Annotated[int, Field(ge=1, le=3)] = 1,
) -> dict:
    """Ask the host of a ride for a seat. The host accepts or declines in the app."""
    req = await api().call("POST", f"/trips/{trip_id}/requests", json={"seats": seats})
    return {"request_id": req["id"], "status": req["status"], "ride": ride_summary(req["trip"])}


async def upcoming() -> dict:
    now = datetime.now(UTC) - timedelta(hours=1)
    hosted = (await api().call("GET", "/trips/mine"))["items"]
    requests = (await api().call("GET", "/requests/mine"))["items"]
    soon = lambda trip: datetime.fromisoformat(trip["depart_at"]) >= now  # noqa: E731
    return {
        "hosting": [ride_summary(t) for t in hosted if soon(t) and t["status"] in ("open", "full")],
        "joining": [
            {
                "request_id": r["id"],
                "request_status": r["status"],
                "ride": ride_summary(r["trip"]),
                "host_contact": r.get("host_contact"),  # only present once accepted
            }
            for r in requests
            if soon(r["trip"]) and r["status"] in ("pending", "accepted")
        ],
    }


@mcp.tool(annotations=ToolAnnotations(read_only_hint=True))
async def my_upcoming_rides() -> dict:
    """Rides you are hosting and rides you asked to join that haven't happened yet."""
    return await upcoming()


# The same information as a resource: clients can attach it to a conversation as context.
@mcp.resource(
    "ridemate://trips/upcoming",
    name="upcoming_rides",
    description="Rides you host and rides you asked to join that haven't happened yet",
    mime_type="application/json",
)
async def upcoming_rides_resource() -> str:
    return json.dumps(await upcoming(), indent=2)


def main() -> None:
    mcp.run()  # stdio transport by default


if __name__ == "__main__":
    main()
