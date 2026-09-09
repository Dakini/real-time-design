from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from .. import service
from ..database import get_db
from ..db_models import UserRow
from ..deps import get_optional_user, require_room_access
from ..errors import unauthorized
from ..models import JoinResult, JoinWithTokenRequest, JoinWithTokenResponse, Participant, PresenceUpdateMessage
from ..realtime import manager

router = APIRouter(tags=["participants"])


@router.get("/sessions/{sessionId}/participants", response_model=list[Participant])
def list_participants(sessionId: str, request: Request, db: Session = Depends(get_db)) -> list[Participant]:
    require_room_access(sessionId, request, db)
    return service.list_participants(db, sessionId)


@router.post("/sessions/{sessionId}/participants/me", response_model=JoinResult)
def join_as_owner(
    sessionId: str, user: UserRow | None = Depends(get_optional_user), db: Session = Depends(get_db)
) -> JoinResult:
    if user is None:
        raise unauthorized()
    session, participant = service.join_as_owner(db, sessionId, user)
    return JoinResult(session=session, participant=participant)


@router.delete("/sessions/{sessionId}/participants/{participantId}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_participant(
    sessionId: str,
    participantId: str,
    user: UserRow | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
) -> None:
    service.remove_participant(db, sessionId, user, participantId)
    await manager.disconnect_participant(sessionId, participantId)
    await manager.broadcast(sessionId, PresenceUpdateMessage(presence=manager.presence_list(sessionId)))


@router.post("/join", response_model=JoinWithTokenResponse)
def join_with_token(body: JoinWithTokenRequest, db: Session = Depends(get_db)) -> JoinWithTokenResponse:
    session, participant, token = service.join_with_token(db, body.token, body.displayName)
    return JoinWithTokenResponse(session=session, participant=participant, participantToken=token)
