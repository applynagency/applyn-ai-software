"""Per-room WebSocket connection registry with presence and broadcast.

The manager is a process singleton. It tracks live connections per war room,
delivers broadcast events to every local socket, mirrors them to other workers
via the Redis broker, and derives presence from the live connection set.

It is safe to call ``broadcast`` from an ordinary HTTP request even when no
sockets are connected (it simply fans out to zero local sockets and publishes to
Redis, which is a no-op without Redis).
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass

from app.core.logging import get_logger
from app.realtime import broker

logger = get_logger(__name__)


@dataclass
class Connection:
    conn_id: str
    websocket: object
    user_id: str
    user_name: str
    role: str | None

    async def send(self, event: dict) -> None:
        await self.websocket.send_json(event)


class ConnectionManager:
    def __init__(self) -> None:
        self._rooms: dict[str, dict[str, Connection]] = {}
        self._sub_tasks: dict[str, asyncio.Task] = {}

    # ------------------------------------------------------------- lifecycle
    async def connect(
        self, room_id: str, websocket, *, user_id: str, user_name: str, role: str | None
    ) -> str:
        """Register an already-accepted websocket. Returns its connection id."""
        conn_id = uuid.uuid4().hex
        conn = Connection(conn_id, websocket, user_id, user_name, role)
        room = self._rooms.setdefault(room_id, {})
        first = len(room) == 0
        room[conn_id] = conn
        if first:
            self._start_subscriber(room_id)
        return conn_id

    def disconnect(self, room_id: str, conn_id: str) -> None:
        room = self._rooms.get(room_id)
        if not room:
            return
        room.pop(conn_id, None)
        if not room:
            self._rooms.pop(room_id, None)
            task = self._sub_tasks.pop(room_id, None)
            if task is not None:
                task.cancel()

    # ------------------------------------------------------------- broadcast
    async def broadcast(self, room_id: str, event: dict) -> None:
        """Deliver to all local sockets and mirror to other workers."""
        await self._local_broadcast(room_id, event)
        await broker.publish(room_id, event)

    async def _local_broadcast(self, room_id: str, event: dict) -> None:
        room = self._rooms.get(room_id)
        if not room:
            return
        dead: list[str] = []
        for conn_id, conn in list(room.items()):
            try:
                await conn.send(event)
            except Exception:  # noqa: BLE001 - drop broken sockets
                dead.append(conn_id)
        for conn_id in dead:
            self.disconnect(room_id, conn_id)

    def _start_subscriber(self, room_id: str) -> None:
        async def _run() -> None:
            try:
                async for event in broker.subscribe(room_id):
                    await self._local_broadcast(room_id, event)
            except asyncio.CancelledError:  # pragma: no cover - shutdown path
                raise
            except Exception as exc:  # noqa: BLE001
                logger.warning("warroom_subscriber_error", room_id=room_id, error=str(exc))

        try:
            self._sub_tasks[room_id] = asyncio.create_task(_run())
        except RuntimeError:  # pragma: no cover - no running loop
            pass

    # ------------------------------------------------------------- presence
    def presence(self, room_id: str) -> list[dict]:
        """Distinct users currently connected to the room."""
        room = self._rooms.get(room_id, {})
        by_user: dict[str, dict] = {}
        for conn in room.values():
            entry = by_user.setdefault(
                conn.user_id,
                {"user_id": conn.user_id, "name": conn.user_name, "connections": 0},
            )
            entry["connections"] += 1
        return list(by_user.values())

    def connection_count(self, room_id: str) -> int:
        return len(self._rooms.get(room_id, {}))

    def reset(self) -> None:
        """Test helper: drop all rooms and cancel subscriber tasks."""
        for task in self._sub_tasks.values():
            task.cancel()
        self._sub_tasks.clear()
        self._rooms.clear()


manager = ConnectionManager()
