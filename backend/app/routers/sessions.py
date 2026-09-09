from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from .. import service
from ..database import get_db
from ..db_models import UserRow
from ..deps import get_optional_user, require_room_access, require_user
from ..models import CreateSessionRequest, InterviewSession, PermissionChangedMessage, SessionEndedMessage, SessionPatch
from ..realtime import manager

router = APIRouter(tags=["sessions"])


@router.get("/sessions", response_model=list[InterviewSession])
def list_sessions(user: UserRow = Depends(require_user), db: Session = Depends(get_db)) -> list[InterviewSession]:
    return service.list_sessions(db, user)


@router.post("/sessions", response_model=InterviewSession, status_code=201)
def create_session(
    body: CreateSessionRequest, user: UserRow = Depends(require_user), db: Session = Depends(get_db)
) -> InterviewSession:
    return service.create_session(db, user, body.title, body.prompt, body.scheduledAt)


@router.get("/sessions/{sessionId}", response_model=InterviewSession)
def get_session(sessionId: str, request: Request, db: Session = Depends(get_db)) -> InterviewSession:
    require_room_access(sessionId, request, db)
    return service.require_session(db, sessionId)


@router.patch("/sessions/{sessionId}", response_model=InterviewSession)
async def update_session(
    sessionId: str,
    patch: SessionPatch,
    user: UserRow | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
) -> InterviewSession:
    session = service.update_session(db, sessionId, user, patch)
    await manager.broadcast(sessionId, PermissionChangedMessage(session=session))
    return session


@router.post("/sessions/{sessionId}/start", response_model=InterviewSession)
async def start_session(
    sessionId: str, user: UserRow | None = Depends(get_optional_user), db: Session = Depends(get_db)
) -> InterviewSession:
    session = service.start_session(db, sessionId, user)
    await manager.broadcast(sessionId, PermissionChangedMessage(session=session))
    return session


@router.post("/sessions/{sessionId}/end", response_model=InterviewSession)
async def end_session(
    sessionId: str, user: UserRow | None = Depends(get_optional_user), db: Session = Depends(get_db)
) -> InterviewSession:
    session = service.end_session(db, sessionId, user)
    await manager.broadcast(sessionId, SessionEndedMessage(session=session))
    return session


@router.post("/sessions/{sessionId}/archive", response_model=InterviewSession)
def archive_session(
    sessionId: str, user: UserRow | None = Depends(get_optional_user), db: Session = Depends(get_db)
) -> InterviewSession:
    return service.archive_session(db, sessionId, user)


@router.post("/sessions/{sessionId}/duplicate", response_model=InterviewSession, status_code=201)
def duplicate_session(
    sessionId: str, user: UserRow | None = Depends(get_optional_user), db: Session = Depends(get_db)
) -> InterviewSession:
    return service.duplicate_session(db, sessionId, user)
