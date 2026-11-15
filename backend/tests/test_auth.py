import uuid

import pytest

from tests.conftest import TEST_EMAIL_PREFIX

pytestmark = pytest.mark.anyio


async def login(client) -> dict:
    email = f"{TEST_EMAIL_PREFIX}auth-{uuid.uuid4().hex[:8]}@example.com"
    body = {"email": email, "password": "supersecret1", "display_name": "Auth Tester"}
    assert (await client.post("/auth/register", json=body)).status_code == 201
    r = await client.post("/auth/login", data={"username": email, "password": "supersecret1"})
    assert r.status_code == 200
    return r.json()


async def test_refresh_rotates_tokens(client):
    first = await login(client)
    assert first["refresh_token"] and first["access_token"]

    r = await client.post("/auth/refresh", json={"refresh_token": first["refresh_token"]})
    assert r.status_code == 200
    second = r.json()
    assert second["refresh_token"] != first["refresh_token"]

    me = await client.get("/users/me", headers={"Authorization": f"Bearer {second['access_token']}"})
    assert me.status_code == 200


async def test_reusing_an_old_refresh_token_revokes_the_whole_login(client, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "refresh_reuse_grace_seconds", 0)  # no race allowance
    first = await login(client)
    second = (await client.post("/auth/refresh", json={"refresh_token": first["refresh_token"]})).json()

    # A thief replays the old token: refused, and the family is burned...
    stolen = await client.post("/auth/refresh", json={"refresh_token": first["refresh_token"]})
    assert stolen.status_code == 401
    # ...so even the legitimate newer token no longer works.
    legit = await client.post("/auth/refresh", json={"refresh_token": second["refresh_token"]})
    assert legit.status_code == 401


async def test_logout_revokes_refresh_token(client):
    tokens = await login(client)
    assert (await client.post("/auth/logout", json={"refresh_token": tokens["refresh_token"]})).status_code == 204
    r = await client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert r.status_code == 401
    # Unknown tokens are ignored, not reported (no information leak).
    assert (await client.post("/auth/logout", json={"refresh_token": "nope"})).status_code == 204
