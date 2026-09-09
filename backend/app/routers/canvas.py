from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status

from .. import service
from ..deps import get_optional_user, require_room_access
from ..models import CanvasSnapshot, ClearCanvasRequest, DocumentUpdateMessage
from ..realtime import manager
from ..store import UserRecord, store

router = APIRouter(tags=["canvas"])


@router.get("/sessions/{sessionId}/canvas", response_model=CanvasSnapshot)
def get_canvas(sessionId: str, request: Request) -> CanvasSnapshot:
    require_room_access(sessionId, request)
    return service.get_canvas(store, sessionId)


@router.post("/sessions/{sessionId}/canvas/clear", status_code=status.HTTP_204_NO_CONTENT)
async def clear_canvas(
    sessionId: str, body: ClearCanvasRequest, user: UserRecord | None = Depends(get_optional_user)
) -> None:
    envelopes = service.clear_canvas(store, sessionId, user, body.actorId)
    await manager.broadcast(sessionId, DocumentUpdateMessage(ops=envelopes))
