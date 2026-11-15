"""Rides at any point on the map (here: Kozhikode, which has no entries in `places`)."""

import pytest

from app.core.geo import distance_m
from tests.conftest import make_user, minutes_from_now

pytestmark = pytest.mark.anyio

# A station and two points due east of it on a straight road (synthetic, for clear maths).
STATION = {"lat": 11.2479, "lng": 75.7804, "label": "Kozhikode Railway Station"}
HALFWAY = {"lat": 11.2479, "lng": 75.7942, "label": "Halfway stop"}  # ~1.5 km east
FAR_END = {"lat": 11.2479, "lng": 75.8079, "label": "Medical College side"}  # ~3 km east


async def post_free_trip(client, headers, start=STATION, end=FAR_END) -> dict:
    body = {"start": start, "end": end, "depart_at": minutes_from_now(20), "seats_total": 2, "vehicle": "auto"}
    r = await client.post("/trips", json=body, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


async def search(client, headers, origin: dict, destination: dict) -> list[dict]:
    params = {
        "from_lat": origin["lat"], "from_lng": origin["lng"],
        "to_lat": destination["lat"], "to_lng": destination["lng"],
    }
    r = await client.get("/trips/search", params=params, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()["items"]


async def test_ride_in_a_city_with_no_known_places(client):
    host = await make_user(client, "KozhikodeHost")
    rider = await make_user(client, "KozhikodeRider")
    trip = await post_free_trip(client, host)
    assert trip["start"]["label"] == "Kozhikode Railway Station"
    assert trip["end"] == FAR_END

    # The rider stands ~300 m from the host's start and wants the same destination.
    nearby = {"lat": 11.2500, "lng": 75.7824, "label": "Me"}
    found = [t for t in await search(client, rider, nearby, FAR_END) if t["id"] == trip["id"]]
    assert found and found[0]["match"] == "same_destination"
    assert 200 < found[0]["pickup_distance_m"] < 400  # how far they walk to meet the host


async def test_on_the_way_with_coordinates(client):
    host = await make_user(client, "WayHostK")
    rider = await make_user(client, "WayRiderK")
    trip = await post_free_trip(client, host)
    found = [t for t in await search(client, rider, STATION, HALFWAY) if t["id"] == trip["id"]]
    assert found and found[0]["match"] == "on_the_way" and found[0]["detour_km"] == 0.0


async def test_rides_starting_too_far_away_are_not_shown(client):
    host = await make_user(client, "FarHost")
    rider = await make_user(client, "FarRider")
    trip = await post_free_trip(client, host)
    two_km_north = {"lat": 11.2659, "lng": 75.7804, "label": "Elsewhere"}
    assert distance_m(STATION["lat"], STATION["lng"], two_km_north["lat"], two_km_north["lng"]) > 1900
    assert trip["id"] not in [t["id"] for t in await search(client, rider, two_km_north, FAR_END)]


async def test_location_validation(client):
    host = await make_user(client, "Validator2")
    base = {"depart_at": minutes_from_now(20), "seats_total": 1}
    neither = await client.post("/trips", json=base | {"end": FAR_END}, headers=host)
    assert neither.status_code == 422  # no pickup at all
    tiny = await client.post(
        "/trips", json=base | {"start": STATION, "end": STATION | {"lat": 11.2480}}, headers=host
    )
    assert tiny.status_code == 400 and "too close" in tiny.json()["detail"]
    missing = await client.get("/trips/search", params={"to_lat": 11.25, "to_lng": 75.78}, headers=host)
    assert missing.status_code == 400  # no origin given
