"""WebSocket room fanout: who's connected to which session, and presence."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from fastapi import WebSocket

from .models import PresenceState, ServerMessage


@dataclass
class RoomConnection:
    websocket: WebSocket
    participant_id: str


class ConnectionManager:
    def __init__(self) -> None:
        self._rooms: dict[str, list[RoomConnection]] = {}
        self._presence: dict[str, dict[str, PresenceState]] = {}
        self._lock = asyncio.Lock()

    async def register(self, session_id: str, conn: RoomConnection, presence: PresenceState) -> None:
        async with self._lock:
            self._rooms.setdefault(session_id, []).append(conn)
            self._presence.setdefault(session_id, {})[conn.participant_id] = presence

    async def unregister(self, session_id: str, conn: RoomConnection) -> None:
        async with self._lock:
            conns = self._rooms.get(session_id)
            if conns and conn in conns:
                conns.remove(conn)
            self._presence.get(session_id, {}).pop(conn.participant_id, None)

    def presence_list(self, session_id: str) -> list[PresenceState]:
        return list(self._presence.get(session_id, {}).values())

    def update_presence(self, session_id: str, participant_id: str, **patch: object) -> PresenceState | None:
        state = self._presence.get(session_id, {}).get(participant_id)
        if state is None:
            return None
        updated = state.model_copy(update=patch)
        self._presence[session_id][participant_id] = updated
        return updated

    async def broadcast(self, session_id: str, message: ServerMessage) -> None:
        conns = list(self._rooms.get(session_id, []))
        payload = message.model_dump(mode="json")
        for conn in conns:
            try:
                await conn.websocket.send_json(payload)
            except Exception:
                pass

    async def send(self, websocket: WebSocket, message: ServerMessage) -> None:
        await websocket.send_json(message.model_dump(mode="json"))

    async def disconnect_participant(self, session_id: str, participant_id: str) -> None:
        """Force-close any live connection for a participant who has been removed."""
        conns = [c for c in self._rooms.get(session_id, []) if c.participant_id == participant_id]
        for conn in conns:
            try:
                await conn.websocket.close(code=4403)
            except Exception:
                pass
            await self.unregister(session_id, conn)


manager = ConnectionManager()
