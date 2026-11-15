import asyncio

import pytest

from tests.conftest import make_user, minutes_from_now, place_ids

pytestmark = pytest.mark.anyio

STATION = "Kazhakoottam Railway Station"
KULATHOOR = "Kulathoor"


async def post_trip(client, headers, places, **overrides) -> dict:
    body = {
        "from_place_id": places[STATION],
        "to_place_id": places[KULATHOOR],
        "depart_at": minutes_from_now(20),
        "seats_total": 2,
        "vehicle": "auto",
        "fare_estimate": 200,
    } | overrides
    r = await client.post("/trips", json=body, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


async def test_full_ride_flow(client):
    places = await place_ids(client)
    host = await make_user(client, "Host", phone="9876543210")
    rider = await make_user(client, "Rider", phone="9123456780")

    # Host posts a trip. The public view shows a name, never contact details.
    trip = await post_trip(client, host, places)
    assert trip["seats_left"] == 2 and trip["status"] == "open"
    assert trip["host"]["display_name"] == "Host"
    assert "email" not in trip["host"] and "phone" not in trip["host"]  # contacts stay private

    # Rider finds it; the host doesn't see their own trip in search.
    params = {"from_place_id": places[STATION], "to_place_id": places[KULATHOOR]}
    found = (await client.get("/trips/search", params=params, headers=rider)).json()["items"]
    assert trip["id"] in [t["id"] for t in found]
    own = (await client.get("/trips/search", params=params, headers=host)).json()["items"]
    assert trip["id"] not in [t["id"] for t in own]

    # Before acceptance: no contact for the rider.
    detail = (await client.get(f"/trips/{trip['id']}", headers=rider)).json()
    assert detail["host_contact"] is None and detail["riders"] == []

    # Rider requests; asking twice, or the host joining their own trip, is refused.
    r = await client.post(f"/trips/{trip['id']}/requests", json={"seats": 1}, headers=rider)
    assert r.status_code == 201
    req_id = r.json()["id"]
    dup = await client.post(f"/trips/{trip['id']}/requests", json={"seats": 1}, headers=rider)
    assert dup.status_code == 409
    self_join = await client.post(f"/trips/{trip['id']}/requests", json={}, headers=host)
    assert self_join.status_code == 400

    # Only the host may accept, and the host sees no rider contact before accepting.
    assert (await client.post(f"/requests/{req_id}/accept", headers=rider)).status_code == 403
    incoming = (await client.get(f"/trips/{trip['id']}/requests", headers=host)).json()
    assert incoming[0]["requester_contact"] is None

    accepted = await client.post(f"/requests/{req_id}/accept", headers=host)
    assert accepted.status_code == 200
    assert accepted.json()["requester_contact"]["phone"] == "9123456780"

    # After acceptance: both sides see each other's contact.
    detail = (await client.get(f"/trips/{trip['id']}", headers=rider)).json()
    assert detail["host_contact"]["phone"] == "9876543210"
    assert detail["seats_left"] == 1
    mine = (await client.get("/requests/mine", headers=rider)).json()["items"]
    assert mine[0]["status"] == "accepted" and mine[0]["host_contact"] is not None

    # The rider can't edit or cancel the host's trip.
    assert (await client.patch(f"/trips/{trip['id']}", json={"note": "x"}, headers=rider)).status_code == 403
    assert (await client.post(f"/trips/{trip['id']}/cancel", headers=rider)).status_code == 403

    # Rider backs out: the seat goes back.
    assert (await client.post(f"/requests/{req_id}/cancel", headers=rider)).json()["status"] == "cancelled"
    assert (await client.get(f"/trips/{trip['id']}", headers=host)).json()["seats_left"] == 2

    # Host cancels: the trip disappears from search.
    assert (await client.post(f"/trips/{trip['id']}/cancel", headers=host)).json()["status"] == "cancelled"
    found = (await client.get("/trips/search", params=params, headers=rider)).json()["items"]
    assert trip["id"] not in [t["id"] for t in found]


async def test_validation_and_auth(client):
    places = await place_ids(client)
    host = await make_user(client, "Validator")
    base = {"from_place_id": places[STATION], "to_place_id": places[KULATHOOR], "seats_total": 1}

    cases = {
        "past departure": base | {"depart_at": minutes_from_now(-60)},
        "no timezone": base | {"depart_at": "2030-01-01T06:15:00"},
        "3 seats in an auto": base | {"depart_at": minutes_from_now(20), "seats_total": 3, "vehicle": "auto"},
        "same pickup and drop": base | {"depart_at": minutes_from_now(20), "to_place_id": places[STATION]},
    }
    for name, body in cases.items():
        r = await client.post("/trips", json=body, headers=host)
        assert r.status_code == 422, f"{name}: {r.status_code} {r.text}"

    assert (await client.get("/trips/mine")).status_code == 401  # no token


async def test_last_seat_cannot_be_double_booked(client):
    """Two accepts race for one seat. SELECT ... FOR UPDATE must let exactly one win."""
    places = await place_ids(client)
    host = await make_user(client, "RaceHost")
    trip = await post_trip(client, host, places, seats_total=1)

    request_ids = []
    for name in ("RiderA", "RiderB"):
        rider = await make_user(client, name)
        r = await client.post(f"/trips/{trip['id']}/requests", json={"seats": 1}, headers=rider)
        request_ids.append(r.json()["id"])

    # Fire both accepts at the same moment (separate DB connections, truly concurrent).
    results = await asyncio.gather(
        *(client.post(f"/requests/{rid}/accept", headers=host) for rid in request_ids)
    )
    assert sorted(r.status_code for r in results) == [200, 409]

    final = (await client.get(f"/trips/{trip['id']}", headers=host)).json()
    assert final["seats_taken"] == 1 and final["status"] == "full"
