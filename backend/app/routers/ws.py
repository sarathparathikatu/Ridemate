import asyncio

import jwt
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.security import decode_access_token
from app.db.session import SessionLocal
from app.models import User
from app.realtime.connections import manager

router = APIRouter(tags=["realtime"])

AUTH_TIMEOUT_SECONDS = 10
CLOSE_UNAUTHORIZED = 4401  # application-defined close codes live in 4000-4999


@router.websocket("/ws")
async def events_socket(ws: WebSocket) -> None:
    """Live events for the logged-in user. First message: {"type": "auth", "token": ...}."""
    await ws.accept()
    # Browsers can't set an Authorization header on a WebSocket, and a token in the URL
    # would be written to server and proxy logs, so the first message carries it.
    try:
        hello = await asyncio.wait_for(ws.receive_json(), timeout=AUTH_TIMEOUT_SECONDS)
        if not isinstance(hello, dict):
            raise ValueError("expected a JSON object")
        user_id = decode_access_token(str(hello.get("token", "")))
    except WebSocketDisconnect:
        return
    except (TimeoutError, ValueError, jwt.InvalidTokenError):
        await ws.close(code=CLOSE_UNAUTHORIZED)
        return

    async with SessionLocal() as db:
        user = await db.get(User, user_id)
        if user is None or user.is_suspended:
            await ws.close(code=CLOSE_UNAUTHORIZED)
            return

    manager.add(user_id, ws)
    try:
        await ws.send_json({"type": "ready"})
        while True:
            await ws.receive_text()  # clients only send keep-alive pings; we wait for close
    except WebSocketDisconnect:
        pass
    finally:
        manager.remove(user_id, ws)
