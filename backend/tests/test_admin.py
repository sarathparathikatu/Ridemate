import pytest

from app.db.session import SessionLocal
from app.services import admin_service
from tests.conftest import make_user, place_ids
from tests.test_rides import post_trip

pytestmark = pytest.mark.anyio


async def me(client, headers) -> dict:
    return (await client.get("/users/me", headers=headers)).json()


async def make_admin(client, name="Moderator") -> dict:
    headers = await make_user(client, name)
    email = (await me(client, headers))["email"]
    async with SessionLocal() as db:
        await admin_service.set_admin(db, email, True)  # the function the command line uses
    return headers


async def report(client, reporter, reported_id, **extra) -> None:
    body = {"reason": "unsafe", "details": "Drove off without me"} | extra
    r = await client.post(f"/users/{reported_id}/report", json=body, headers=reporter)
    assert r.status_code == 201, r.text


async def open_reports(client, admin) -> list[dict]:
    r = await client.get("/admin/reports", headers=admin)
    assert r.status_code == 200, r.text
    return r.json()["items"]


async def test_only_admins_reach_the_admin_api(client):
    user = await make_user(client, "Ordinary")
    assert (await me(client, user))["is_admin"] is False
    assert (await client.get("/admin/reports")).status_code == 401  # not logged in
    assert (await client.get("/admin/reports", headers=user)).status_code == 403  # not allowed
    assert (await client.get("/admin/summary", headers=user)).status_code == 403
    r = await client.post("/admin/reports/1/resolve", json={"action": "suspend"}, headers=user)
    assert r.status_code == 403

    admin = await make_admin(client)
    assert (await me(client, admin))["is_admin"] is True
    assert (await client.get("/admin/reports", headers=admin)).status_code == 200


async def test_dismissing_a_report_leaves_the_account_alone(client):
    admin = await make_admin(client)
    reporter = await make_user(client, "Complainer")
    accused = await make_user(client, "Accused")
    accused_id = (await me(client, accused))["id"]
    await report(client, reporter, accused_id)

    mine = [r for r in await open_reports(client, admin) if r["reported"]["id"] == accused_id]
    assert len(mine) == 1
    item = mine[0]
    assert item["reporter"]["display_name"] == "Complainer"
    assert item["reported"]["reports_received"] == 1 and item["details"] == "Drove off without me"
    assert "phone" not in item["reported"]  # an admin doesn't need phone numbers

    r = await client.post(
        f"/admin/reports/{item['id']}/resolve",
        json={"action": "dismiss", "note": "  Misunderstanding  "},
        headers=admin,
    )
    assert r.status_code == 200, r.text
    done = r.json()
    assert done["status"] == "reviewed" and done["resolution"] == "dismissed"
    assert done["admin_note"] == "Misunderstanding" and done["reviewed_by_name"] == "Moderator"

    again = await client.post(f"/admin/reports/{item['id']}/resolve", json={"action": "dismiss"}, headers=admin)
    assert again.status_code == 409  # a report is decided once
    assert (await me(client, accused))["display_name"] == "Accused"  # still works normally
    assert item["id"] not in [r["id"] for r in await open_reports(client, admin)]
    reviewed = (await client.get("/admin/reports", params={"status": "reviewed"}, headers=admin)).json()
    assert item["id"] in [r["id"] for r in reviewed["items"]]


async def test_suspending_logs_the_person_out_and_takes_them_out_of_every_ride(client):
    places = await place_ids(client)
    admin = await make_admin(client)
    victim = await make_user(client, "Victim")
    other = await make_user(client, "Bystander")
    bad = await make_user(client, "BadActor")
    bad_me = await me(client, bad)
    bad_login = {"username": bad_me["email"], "password": "supersecret1"}
    tokens = (await client.post("/auth/login", data=bad_login)).json()

    # BadActor hosts one ride (Bystander asked to join it) and has a seat in Victim's ride.
    bad_trip = await post_trip(client, bad, places)
    await client.post(f"/trips/{bad_trip['id']}/requests", json={"seats": 1}, headers=other)
    victim_trip = await post_trip(client, victim, places, seats_total=1)
    req = await client.post(f"/trips/{victim_trip['id']}/requests", json={"seats": 1}, headers=bad)
    await client.post(f"/requests/{req.json()['id']}/accept", headers=victim)
    assert (await client.get(f"/trips/{victim_trip['id']}", headers=victim)).json()["status"] == "full"

    # Two people report BadActor; the admin suspends through one of the reports.
    await report(client, victim, bad_me["id"], trip_id=victim_trip["id"])
    await report(client, other, bad_me["id"], reason="harassment")
    about_bad = [r for r in await open_reports(client, admin) if r["reported"]["id"] == bad_me["id"]]
    assert len(about_bad) == 2 and about_bad[0]["reported"]["reports_received"] == 2
    with_trip = next(r for r in about_bad if r["trip"])
    assert with_trip["trip"]["end_label"] == "Kulathoor"

    r = await client.post(
        f"/admin/reports/{with_trip['id']}/resolve", json={"action": "suspend", "note": "Two reports"}, headers=admin
    )
    assert r.status_code == 200, r.text
    assert r.json()["resolution"] == "suspended" and r.json()["reported"]["is_suspended"] is True
    # The other open report about the same person was closed by the same decision.
    assert not [r for r in await open_reports(client, admin) if r["reported"]["id"] == bad_me["id"]]

    # Logged out everywhere: the access token, the refresh token and a new login all fail.
    assert (await client.get("/users/me", headers=bad)).status_code == 401
    refresh = await client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert refresh.status_code == 401
    login = await client.post("/auth/login", data=bad_login)
    assert login.status_code == 403 and "suspended" in login.json()["detail"]

    # Their own ride is cancelled, and their seat in Victim's ride is free again.
    assert (await client.get(f"/trips/{bad_trip['id']}", headers=other)).json()["status"] == "cancelled"
    freed = (await client.get(f"/trips/{victim_trip['id']}", headers=victim)).json()
    assert freed["status"] == "open" and freed["seats_taken"] == 0

    summary = (await client.get("/admin/summary", headers=admin)).json()
    assert summary["suspended_users"] >= 1
    suspended = (await client.get("/admin/suspended", headers=admin)).json()
    assert bad_me["id"] in [u["id"] for u in suspended]

    # Lifting the suspension lets them log in again (their old rides stay cancelled).
    lifted = await client.post(f"/admin/users/{bad_me['id']}/unsuspend", headers=admin)
    assert lifted.status_code == 200 and lifted.json()["is_suspended"] is False
    assert (await client.post("/auth/login", data=bad_login)).status_code == 200
    assert (await client.post(f"/admin/users/{bad_me['id']}/unsuspend", headers=admin)).status_code == 409


async def test_admins_cannot_be_suspended_through_a_report(client):
    admin = await make_admin(client)
    second_admin = await make_admin(client, "SecondMod")
    reporter = await make_user(client, "Troll")
    target_id = (await me(client, second_admin))["id"]
    await report(client, reporter, target_id)
    item = next(r for r in await open_reports(client, admin) if r["reported"]["id"] == target_id)

    r = await client.post(f"/admin/reports/{item['id']}/resolve", json={"action": "suspend"}, headers=admin)
    assert r.status_code == 400 and "Admins can't be suspended" in r.json()["detail"]
    assert (await me(client, second_admin))["is_admin"] is True  # untouched, report still open
    assert item["id"] in [r["id"] for r in await open_reports(client, admin)]

    async with SessionLocal() as db:  # revoking works the same way granting did
        await admin_service.set_admin(db, (await me(client, second_admin))["email"], False)
    assert (await client.get("/admin/reports", headers=second_admin)).status_code == 403
