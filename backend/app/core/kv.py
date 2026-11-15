"""Tiny key-value store with expiry: Redis when configured, process memory otherwise.

Used by the search cache and the rate limiter. The in-memory version is only correct
for a single server process; that is exactly why production sets REDIS_URL.
"""

import time

from app.core.redis import get_redis

_memory: dict[str, tuple[str, float | None]] = {}  # key -> (value, expires_at)


def _alive(key: str) -> tuple[str, float | None] | None:
    entry = _memory.get(key)
    if entry and entry[1] is not None and entry[1] <= time.monotonic():
        del _memory[key]
        return None
    return entry


async def get(key: str) -> str | None:
    if (redis := get_redis()) is not None:
        return await redis.get(key)
    entry = _alive(key)
    return entry[0] if entry else None


async def set(key: str, value: str, ttl_seconds: int) -> None:
    if (redis := get_redis()) is not None:
        await redis.set(key, value, ex=ttl_seconds)
        return
    _memory[key] = (value, time.monotonic() + ttl_seconds)


async def incr(key: str, ttl_seconds: int | None = None) -> int:
    """Add 1 and return the new value. The expiry is set when the key is first created."""
    if (redis := get_redis()) is not None:
        # MULTI/EXEC: "create with expiry if missing" and INCR run as one unit, so a crash
        # between them can't leave a counter that never expires.
        async with redis.pipeline(transaction=True) as pipe:
            if ttl_seconds is not None:
                pipe.set(key, 0, ex=ttl_seconds, nx=True)
            pipe.incr(key)
            *_, value = await pipe.execute()
        return int(value)
    entry = _alive(key)
    value = int(entry[0]) + 1 if entry else 1
    expires_at = entry[1] if entry else (time.monotonic() + ttl_seconds if ttl_seconds else None)
    _memory[key] = (str(value), expires_at)
    return value


def reset_memory() -> None:
    """Tests: start each test with an empty in-memory store."""
    _memory.clear()
