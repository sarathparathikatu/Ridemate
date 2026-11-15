import redis.asyncio as redis

from app.core.config import get_settings

_client: redis.Redis | None = None
_configured = False


def get_redis() -> redis.Redis | None:
    """The shared Redis client, or None when REDIS_URL isn't set (in-memory mode)."""
    global _client, _configured
    if not _configured:
        url = get_settings().redis_url
        # decode_responses: get str back instead of bytes.
        _client = redis.from_url(url, decode_responses=True) if url else None
        _configured = True
    return _client


def use_redis(client: redis.Redis | None) -> None:
    """Swap the client (tests use an in-memory fake Redis)."""
    global _client, _configured
    _client, _configured = client, True
