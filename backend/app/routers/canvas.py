from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from .. import service
from ..database import get_db
from ..db_models import UserRow
from ..deps import get_optional_user, require_room_access
from ..models import CanvasSnapshot, ClearCanvasRequest, DocumentUpdateMessage
from ..realtime import manager

router = APIRouter(tags=["canvas"])


@router.get("/sessions/{sessionId}/canvas", response_model=CanvasSnapshot)
def get_canvas(sessionId: str, request: Request, db: Session = Depends(get_db)) -> CanvasSnapshot:
    require_room_access(sessionId, request, db)
    return service.get_canvas(db, sessionId)


@router.post("/sessions/{sessionId}/canvas/clear", status_code=status.HTTP_204_NO_CONTENT)
async def clear_canvas(
    sessionId: str,
    body: ClearCanvasRequest,
    user: UserRow | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
) -> None:
    envelopes = service.clear_canvas(db, sessionId, user, body.actorId)
    await manager.broadcast(sessionId, DocumentUpdateMessage(ops=envelopes))
