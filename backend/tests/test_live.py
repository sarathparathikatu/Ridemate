import asyncio

import anyio
import pytest
from httpx import AsyncClient
from httpx_ws import WebSocketDisconnect, aconnect_ws
from httpx_ws.transport import ASGIWebSocketTransport

from app.core.redis import use_redis
from app.main import app
from app.realtime.broker import relay_forever
from tests.conftest import make_test_redis, make_user, place_ids
from tests.test_rides import post_trip

pytestmark = pytest.mark.anyio


@pytest.fixture
async def ws_client(client):  # `client` (from conftest) handles cleanup of test users
    async with AsyncClient(transport=ASGIWebSocketTransport(app), base_url="http://test") as c:
        yield c


async def next_event(ws) -> dict:
    with anyio.fail_after(5):
        return await ws.receive_json()


async def open_live(ws, headers: dict) -> None:
    await ws.send_json({"type": "auth", "token": headers["Authorization"].removeprefix("Bearer ")})
    assert (await next_event(ws))["type"] == "ready"


async def test_socket_rejects_a_bad_token(ws_client):
    async with aconnect_ws("http://test/ws", ws_client) as ws:
        await ws.send_json({"type": "auth", "token": "not-a-jwt"})
        with pytest.raises(WebSocketDisconnect) as closed:
            await next_event(ws)
        assert closed.value.code == 4401


async def test_host_and_rider_get_live_events(ws_client):
    places = await place_ids(ws_client)
    host = await make_user(ws_client, "LiveHost")
    rider = await make_user(ws_client, "LiveRider")
    trip = await post_trip(ws_client, host, places)

    async with aconnect_ws("http://test/ws", ws_client) as host_ws, aconnect_ws(
        "http://test/ws", ws_client
    ) as rider_ws:
        await open_live(host_ws, host)
        await open_live(rider_ws, rider)

        r = await ws_client.post(f"/trips/{trip['id']}/requests", json={"seats": 1}, headers=rider)
        event = await next_event(host_ws)
        assert event["type"] == "request.created"
        assert event["message"] == "LiveRider wants to join your ride"

        await ws_client.post(f"/requests/{r.json()['id']}/accept", headers=host)
        event = await next_event(rider_ws)
        assert event["type"] == "request.accepted" and event["trip_id"] == trip["id"]


async def test_events_travel_through_redis(ws_client):
    """With Redis, the publisher and the socket could be on different server processes."""
    use_redis(await make_test_redis())
    relay = asyncio.create_task(relay_forever())
    try:
        await asyncio.sleep(0.1)  # let the relay subscribe
        places = await place_ids(ws_client)
        host = await make_user(ws_client, "RedisHost")
        rider = await make_user(ws_client, "RedisRider")
        trip = await post_trip(ws_client, host, places)
        async with aconnect_ws("http://test/ws", ws_client) as host_ws:
            await open_live(host_ws, host)
            await ws_client.post(f"/trips/{trip['id']}/requests", json={"seats": 1}, headers=rider)
            assert (await next_event(host_ws))["type"] == "request.created"
    finally:
        relay.cancel()
        use_redis(None)  # back to in-memory mode for the other tests
