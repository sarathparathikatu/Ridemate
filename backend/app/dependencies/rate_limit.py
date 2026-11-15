"""Rate limiting as FastAPI dependencies: `dependencies=[Depends(per_user(...))]`.

Fixed-window counter: one counter per (action, who, current window), stored with an
expiry so it cleans itself up. Simple and cheap: one INCR per request. The trade-off: up
to 2x the limit can squeeze through around a window boundary (end of one window + start
of the next). A sliding window or token bucket smooths that out at more cost.
"""

import time

from fastapi import HTTPException, Request, status

from app.core import kv
from app.core.config import get_settings
from app.dependencies.auth import CurrentUser

_clock = time.time  # tests freeze this so a run can't straddle a window boundary


async def _count(action: str, who: str, limit: int, window_seconds: int) -> None:
    if not get_settings().rate_limit_enabled:
        return
    now = _clock()
    window = int(now // window_seconds)
    hits = await kv.incr(f"rl:{action}:{who}:{window}", ttl_seconds=window_seconds)
    if hits > limit:
        retry_after = window_seconds - int(now % window_seconds)
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"Too many attempts. Try again in {retry_after} seconds.",
            headers={"Retry-After": str(retry_after)},
        )


def per_ip(action: str, limit: int, window_seconds: int):
    """For endpoints used before login (no user yet), e.g. login and register."""

    async def dependency(request: Request) -> None:
        # Behind a reverse proxy, run uvicorn with --proxy-headers so this is the real
        # client address and not the proxy's.
        ip = request.client.host if request.client else "unknown"
        await _count(action, ip, limit, window_seconds)

    return dependency


def per_user(action: str, limit: int, window_seconds: int):
    async def dependency(current_user: CurrentUser) -> None:
        await _count(action, str(current_user.id), limit, window_seconds)

    return dependency
