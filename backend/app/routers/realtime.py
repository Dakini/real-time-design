from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import ValidationError, TypeAdapter

from .. import service
from ..deps import SESSION_COOKIE
from ..models import (
    ClientMessage,
    DocumentUpdateMessage,
    PresenceState,
    PresenceUpdateMessage,
    RoomErrorMessage,
    RoomJoinedMessage,
)
from ..realtime import RoomConnection, manager
from ..security import hash_token
from ..store import store

router = APIRouter(tags=["realtime"])

_client_message_adapter: TypeAdapter[ClientMessage] = TypeAdapter(ClientMessage)


def _authorize(websocket: WebSocket, session_id: str, participant_id: str, token: str | None) -> bool:
    participant = store.participants.get(participant_id)
    if participant is None or participant.sessionId != session_id or participant.leftAt is not None:
        return False

    # Browsers cannot set an Authorization header on a WebSocket handshake, so the
    # participant bearer token is also accepted as a `token` query param.
    if token:
        pid = store.participant_token_hashes.get(hash_token(token))
        if pid == participant.id:
            return True

    auth_header = websocket.headers.get("authorization")
    if auth_header and auth_header.lower().startswith("bearer "):
        header_token = auth_header[7:].strip()
        pid = store.participant_token_hashes.get(hash_token(header_token))
        return pid == participant.id

    cookie_token = websocket.cookies.get(SESSION_COOKIE)
    if cookie_token:
        user_id = store.interviewer_session_tokens.get(hash_token(cookie_token))
        return user_id is not None and participant.userId == user_id

    return False


@router.websocket("/sessions/{sessionId}/room")
async def connect_room(websocket: WebSocket, sessionId: str, participantId: str, token: str | None = None) -> None:
    await websocket.accept()

    session = store.sessions.get(sessionId)
    if session is None:
        await websocket.close(code=4404, reason="Session not found")
        return

    if not _authorize(websocket, sessionId, participantId, token):
        await manager.send(
            websocket,
            RoomErrorMessage(code="forbidden", message="You are not a participant of this session."),
        )
        await websocket.close(code=4403, reason="Forbidden")
        return

    participant = store.participants[participantId]
    presence = PresenceState(
        participantId=participant.id,
        displayName=participant.displayName,
        role=participant.role,
        color=participant.color,
        cursor=None,
        selection=[],
        online=True,
    )
    conn = RoomConnection(websocket=websocket, participant_id=participant.id)
    await manager.register(sessionId, conn, presence)

    await manager.send(
        websocket,
        RoomJoinedMessage(snapshot=service.snapshot(store, sessionId), presence=manager.presence_list(sessionId)),
    )
    await manager.broadcast(sessionId, PresenceUpdateMessage(presence=manager.presence_list(sessionId)))

    try:
        while True:
            data = await websocket.receive_json()
            try:
                message = _client_message_adapter.validate_python(data)
            except ValidationError:
                continue

            if message.type == "ops":
                current_session = store.sessions.get(sessionId)
                if current_session is None:
                    continue
                if not service.can_write(current_session, participant):
                    await manager.send(
                        websocket,
                        RoomErrorMessage(code="editing_locked", message="Editing is locked for you right now."),
                    )
                    await manager.send(
                        websocket,
                        RoomJoinedMessage(
                            snapshot=service.snapshot(store, sessionId),
                            presence=manager.presence_list(sessionId),
                        ),
                    )
                    continue
                items = [(item.clientOperationId, item.op) for item in message.ops]
                envelopes = service.commit_ops(store, sessionId, participant.id, items)
                await manager.broadcast(sessionId, DocumentUpdateMessage(ops=envelopes))

            elif message.type == "presence":
                patch: dict[str, object] = {}
                if "cursor" in data:
                    patch["cursor"] = message.cursor
                if "selection" in data:
                    patch["selection"] = message.selection
                updated = manager.update_presence(sessionId, participant.id, **patch)
                if updated is not None:
                    await manager.broadcast(sessionId, PresenceUpdateMessage(presence=manager.presence_list(sessionId)))
    except WebSocketDisconnect:
        pass
    finally:
        await manager.unregister(sessionId, conn)
        await manager.broadcast(sessionId, PresenceUpdateMessage(presence=manager.presence_list(sessionId)))
