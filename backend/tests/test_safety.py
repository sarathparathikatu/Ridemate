import pytest

from tests.conftest import make_user, place_ids
from tests.test_rides import KULATHOOR, STATION, post_trip

pytestmark = pytest.mark.anyio


async def verify_phone(client, headers, phone="9876543210") -> dict:
    sent = (await client.post("/users/me/phone/send-code", json={"phone": phone}, headers=headers)).json()
    r = await client.post("/users/me/phone/verify", json={"code": sent["dev_code"]}, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


async def shared_ride(client) -> tuple[dict, dict, dict, dict]:
    """A ride with a host and one accepted rider."""
    places = await place_ids(client)
    host = await make_user(client, "SafeHost", phone="9000000001")
    rider = await make_user(client, "SafeRider", phone="9000000002")
    trip = await post_trip(client, host, places)
    req = await client.post(f"/trips/{trip['id']}/requests", json={"seats": 1}, headers=rider)
    await client.post(f"/requests/{req.json()['id']}/accept", headers=host)
    return places, host, rider, trip


async def test_phone_verification_flow(client):
    user = await make_user(client, "OtpUser")
    sent = (await client.post("/users/me/phone/send-code", json={"phone": "9123412345"}, headers=user)).json()
    assert len(sent["dev_code"]) == 6 and sent["expires_in_seconds"] == 300

    wrong = "000000" if sent["dev_code"] != "000000" else "111111"
    assert (await client.post("/users/me/phone/verify", json={"code": wrong}, headers=user)).status_code == 400

    ok = await client.post("/users/me/phone/verify", json={"code": sent["dev_code"]}, headers=user)
    assert ok.json()["phone_verified"] is True and ok.json()["phone"] == "9123412345"

    reused = await client.post("/users/me/phone/verify", json={"code": sent["dev_code"]}, headers=user)
    assert reused.json()["detail"].startswith("Code expired")  # one use only


async def test_code_is_destroyed_after_five_wrong_guesses(client):
    user = await make_user(client, "Guesser")
    sent = (await client.post("/users/me/phone/send-code", json={"phone": "9123400000"}, headers=user)).json()
    wrong = "000000" if sent["dev_code"] != "000000" else "111111"
    for _ in range(5):
        r = await client.post("/users/me/phone/verify", json={"code": wrong}, headers=user)
    assert r.json()["detail"].startswith("Too many wrong codes")
    late = await client.post("/users/me/phone/verify", json={"code": sent["dev_code"]}, headers=user)
    assert late.status_code == 400  # even the right code is useless now


async def test_unverified_users_cannot_post_when_required(client, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "require_verified_phone", True)
    places = await place_ids(client)
    host = await make_user(client, "Unverified")
    body = {"from_place_id": places[STATION], "to_place_id": places[KULATHOOR], "depart_at": "2099-01-01T06:15:00Z", "seats_total": 1}
    assert (await client.post("/trips", json=body, headers=host)).status_code == 403
    await verify_phone(client, host, "9876500000")
    await post_trip(client, host, places)  # now allowed


async def test_complete_then_rate(client):
    _, host, rider, trip = await shared_ride(client)
    host_id = trip["host"]["id"]

    early = await client.post(f"/trips/{trip['id']}/ratings", json={"rated_user_id": host_id, "stars": 5}, headers=rider)
    assert early.status_code == 409  # not completed yet

    assert (await client.post(f"/trips/{trip['id']}/complete", headers=rider)).status_code == 403
    assert (await client.post(f"/trips/{trip['id']}/complete", headers=host)).json()["status"] == "completed"

    body = {"rated_user_id": host_id, "stars": 5, "tags": ["on_time", "felt_safe"]}
    assert (await client.post(f"/trips/{trip['id']}/ratings", json=body, headers=rider)).status_code == 201
    assert (await client.post(f"/trips/{trip['id']}/ratings", json=body, headers=rider)).status_code == 409

    me = (await client.get("/users/me", headers=host)).json()
    assert me["rating_avg"] == 5.0 and me["rating_count"] == 1

    outsider = await make_user(client, "Outsider")
    r = await client.post(f"/trips/{trip['id']}/ratings", json={"rated_user_id": host_id, "stars": 1}, headers=outsider)
    assert r.status_code == 403


async def test_block_hides_rides_and_stops_requests(client):
    places = await place_ids(client)
    host = await make_user(client, "BlockHost")
    rider = await make_user(client, "BlockRider")
    trip = await post_trip(client, host, places)
    params = {"from_place_id": places[STATION], "to_place_id": places[KULATHOOR]}

    async def visible() -> bool:
        items = (await client.get("/trips/search", params=params, headers=rider)).json()["items"]
        return trip["id"] in [t["id"] for t in items]

    assert await visible()
    assert (await client.post(f"/users/{trip['host']['id']}/block", headers=rider)).status_code == 204
    assert not await visible()
    r = await client.post(f"/trips/{trip['id']}/requests", json={"seats": 1}, headers=rider)
    assert r.status_code == 403
    blocks = (await client.get("/users/me/blocks", headers=rider)).json()
    assert [b["display_name"] for b in blocks] == ["BlockHost"]

    await client.delete(f"/users/{trip['host']['id']}/block", headers=rider)
    assert await visible()


async def test_share_link_shows_the_ride_without_contacts(client):
    _, host, rider, trip = await shared_ride(client)
    link = (await client.post(f"/trips/{trip['id']}/share", headers=rider)).json()

    view = await client.get(f"/share/{link['token']}")  # no Authorization header: public
    assert view.status_code == 200
    body = view.json()
    assert body["shared_by"] == "SafeRider" and body["riders"] == 2
    assert body["end"]["label"] == KULATHOOR
    assert "9000000001" not in view.text and "email" not in view.text

    outsider = await make_user(client, "Nosy")
    assert (await client.post(f"/trips/{trip['id']}/share", headers=outsider)).status_code == 403
    assert (await client.get("/share/not-a-real-token")).status_code == 404


async def test_report_a_user(client):
    _, host, rider, trip = await shared_ride(client)
    r = await client.post(
        f"/users/{trip['host']['id']}/report",
        json={"reason": "no_show", "trip_id": trip["id"], "details": "Never arrived"},
        headers=rider,
    )
    assert r.status_code == 201
