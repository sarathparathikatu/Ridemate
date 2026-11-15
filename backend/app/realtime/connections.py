from fastapi import WebSocket


class ConnectionManager:
    """Open WebSockets on THIS server process, grouped by user (one user, many tabs)."""

    def __init__(self) -> None:
        self._sockets: dict[int, set[WebSocket]] = {}

    def add(self, user_id: int, ws: WebSocket) -> None:
        self._sockets.setdefault(user_id, set()).add(ws)

    def remove(self, user_id: int, ws: WebSocket) -> None:
        sockets = self._sockets.get(user_id)
        if sockets is not None:
            sockets.discard(ws)
            if not sockets:
                del self._sockets[user_id]

    async def deliver(self, user_ids: list[int], event: dict) -> None:
        for user_id in user_ids:
            for ws in list(self._sockets.get(user_id, ())):
                try:
                    await ws.send_json(event)
                except Exception:  # the tab went away mid-send; forget that socket
                    self.remove(user_id, ws)


manager = ConnectionManager()
