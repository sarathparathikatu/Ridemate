import pytest

from tests.conftest import make_user, place_ids
from tests.test_rides import KULATHOOR, STATION, post_trip

pytestmark = pytest.mark.anyio


async def search(client, headers, places, destination) -> list[dict]:
    params = {"from_place_id": places[STATION], "to_place_id": places[destination]}
    return (await client.get("/trips/search", params=params, headers=headers)).json()["items"]


async def test_on_the_way_matching(client):
    places = await place_ids(client)
    host = await make_user(client, "WayHost")
    rider = await make_user(client, "WayRider")
    trip = await post_trip(client, host, places)  # station -> Kulathoor

    same = [t for t in await search(client, rider, places, KULATHOOR) if t["id"] == trip["id"]]
    assert same and same[0]["match"] == "same_destination" and same[0]["detour_km"] is None

    # Technopark Phase 1 lies between the station and Kulathoor: a ride passes it.
    on_way = [t for t in await search(client, rider, places, "Technopark Phase 1") if t["id"] == trip["id"]]
    assert on_way and on_way[0]["match"] == "on_the_way"
    assert 0 <= on_way[0]["detour_km"] <= 1.5

    # Pattom is in the city centre, nowhere near this route.
    far = [t for t in await search(client, rider, places, "Pattom") if t["id"] == trip["id"]]
    assert far == []


async def test_places_include_coordinates(client):
    places = (await client.get("/places")).json()
    assert all(isinstance(p["lat"], float) and isinstance(p["lng"], float) for p in places)
