import pytest

from tests.conftest import make_test_redis, make_user, minutes_from_now, place_ids
from tests.test_rides import KULATHOOR, STATION, post_trip

pytestmark = pytest.mark.anyio


async def test_search_pages_with_a_cursor(client):
    places = await place_ids(client)
    rider = await make_user(client, "Pager")
    hosts = [await make_user(client, f"PageHost{i}") for i in range(3)]
    ids = [(await post_trip(client, h, places, depart_at=minutes_from_now(10 + i)))["id"] for i, h in enumerate(hosts)]

    params = {"from_place_id": places[STATION], "to_place_id": places[KULATHOOR], "limit": 2}
    first = (await client.get("/trips/search", params=params, headers=rider)).json()
    assert len(first["items"]) == 2 and first["next_cursor"]

    second = (await client.get("/trips/search", params=params | {"cursor": first["next_cursor"]}, headers=rider)).json()
    seen = [t["id"] for t in first["items"] + second["items"]]
    assert all(i in seen for i in ids)
    assert len(seen) == len(set(seen))  # no trip shown twice

    bad = await client.get("/trips/search", params=params | {"cursor": "garbage"}, headers=rider)
    assert bad.status_code == 400


async def test_cached_search_is_invalidated_when_a_trip_fills_up(client):
    places = await place_ids(client)
    host = await make_user(client, "CacheHost")
    rider = await make_user(client, "CacheRider")
    searcher = await make_user(client, "CacheSearcher")
    trip = await post_trip(client, host, places, seats_total=1)
    params = {"from_place_id": places[STATION], "to_place_id": places[KULATHOOR]}

    found = (await client.get("/trips/search", params=params, headers=searcher)).json()["items"]
    assert trip["id"] in [t["id"] for t in found]  # now cached

    req = await client.post(f"/trips/{trip['id']}/requests", json={"seats": 1}, headers=rider)
    await client.post(f"/requests/{req.json()['id']}/accept", headers=host)  # last seat taken

    found = (await client.get("/trips/search", params=params, headers=searcher)).json()["items"]
    assert trip["id"] not in [t["id"] for t in found]  # stale cache entry was not served


@pytest.mark.parametrize("backend", ["memory", "redis"])
async def test_login_is_rate_limited_per_ip(client, monkeypatch, backend):
    from app.core.config import get_settings
    from app.core.redis import use_redis

    monkeypatch.setattr(get_settings(), "rate_limit_enabled", True)
    # Freeze the limiter's clock mid-window: 11 requests that happened to straddle a
    # minute boundary would land in two windows and never hit the limit (flaky test).
    monkeypatch.setattr("app.dependencies.rate_limit._clock", lambda: 1_800_000_030.0)
    if backend == "redis":
        use_redis(await make_test_redis())
    try:
        wrong = {"username": "nobody@example.com", "password": "wrong-password"}
        codes = [(await client.post("/auth/login", data=wrong)).status_code for _ in range(11)]
        assert codes[:10] == [401] * 10  # ordinary failed logins...
        assert codes[10] == 429  # ...until the 11th attempt in the same minute
        blocked = await client.post("/auth/login", data=wrong)
        assert int(blocked.headers["Retry-After"]) > 0
    finally:
        use_redis(None)
