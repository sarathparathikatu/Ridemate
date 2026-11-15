"""Integration-test setup: tests call the real app (in-process) against the real MySQL.

Every test user's email starts with "rmtest-", and all of them are deleted after each
test (ON DELETE CASCADE removes their trips and requests too).
"""

import os
import uuid
from datetime import UTC, datetime, timedelta

import fakeredis
import pytest
import redis.asyncio as redis_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete

from app.core import kv
from app.db.session import SessionLocal, engine
from app.main import app
from app.models import User

TEST_EMAIL_PREFIX = "rmtest-"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(autouse=True)
def no_rate_limits(monkeypatch):
    # Tests create many users from one "IP"; test_rate_limits switches this back on.
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "rate_limit_enabled", False)


@pytest.fixture
async def client():
    kv.reset_memory()  # fresh cache and rate-limit counters for every test
    # ASGITransport calls the app directly: no server, no network, same code paths.
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    async with SessionLocal() as session:
        await session.execute(delete(User).where(User.email.startswith(TEST_EMAIL_PREFIX)))
        await session.commit()
    await engine.dispose()  # each test runs in its own event loop; don't reuse connections


async def make_user(client: AsyncClient, name: str, phone: str | None = None) -> dict:
    """Register + log in a fresh user; returns the Authorization header to send."""
    email = f"{TEST_EMAIL_PREFIX}{name.lower()}-{uuid.uuid4().hex[:8]}@example.com"
    body = {"email": email, "password": "supersecret1", "display_name": name, "phone": phone}
    assert (await client.post("/auth/register", json=body)).status_code == 201
    r = await client.post("/auth/login", data={"username": email, "password": "supersecret1"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def place_ids(client: AsyncClient) -> dict[str, int]:
    return {p["name"]: p["id"] for p in (await client.get("/places")).json()}


def minutes_from_now(minutes: int) -> str:
    return (datetime.now(UTC) + timedelta(minutes=minutes)).isoformat()


async def make_test_redis():
    """Real Redis when TEST_REDIS_URL is set (CI runs a Redis server), else an in-memory fake."""
    url = os.environ.get("TEST_REDIS_URL")
    if not url:
        return fakeredis.FakeAsyncRedis(decode_responses=True)
    client = redis_asyncio.from_url(url, decode_responses=True)
    await client.flushdb()  # TEST_REDIS_URL points at a database number used only by tests
    return client
