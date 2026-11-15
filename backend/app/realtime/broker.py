"""Publish events to users, wherever their WebSocket happens to be connected.

With several server processes behind a load balancer, the host's socket may live on
process A while the rider's request is handled by process B. So B publishes to a Redis
channel, and every process relays what it hears to its own sockets (pub/sub fan-out).
Without Redis there is only one process, so delivery is direct.
"""

import asyncio
import json
import logging

from app.core.redis import get_redis
from app.realtime.connections import manager

CHANNEL = "ridemate:events"
log = logging.getLogger(__name__)


async def publish(user_ids: list[int], event: dict) -> None:
    user_ids = sorted(set(user_ids))
    redis = get_redis()
    if redis is None:
        await manager.deliver(user_ids, event)
        return
    try:
        await redis.publish(CHANNEL, json.dumps({"user_ids": user_ids, "event": event}))
    except Exception:
        # Notifications are best-effort: a Redis hiccup must never fail the user's request
        # (the data is already committed; the other side sees it on their next refresh).
        log.warning("could not publish event %s", event.get("type"), exc_info=True)


async def relay_forever() -> None:
    """One per server process (started in main.py): Redis channel -> local sockets."""
    redis = get_redis()
    if redis is None:
        return
    while True:
        pubsub = redis.pubsub()
        try:
            await pubsub.subscribe(CHANNEL)
            async for message in pubsub.listen():
                if message["type"] == "message":
                    data = json.loads(message["data"])
                    await manager.deliver(data["user_ids"], data["event"])
        except asyncio.CancelledError:
            raise
        except Exception:
            log.warning("lost the Redis event channel; retrying in 2s", exc_info=True)
            await asyncio.sleep(2)
        finally:
            await pubsub.aclose()
