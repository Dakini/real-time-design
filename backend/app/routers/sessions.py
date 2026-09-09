from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from .. import service
from ..deps import get_optional_user, require_room_access, require_user
from ..models import CreateSessionRequest, InterviewSession, PermissionChangedMessage, SessionEndedMessage, SessionPatch
from ..realtime import manager
from ..store import UserRecord, store

router = APIRouter(tags=["sessions"])


@router.get("/sessions", response_model=list[InterviewSession])
def list_sessions(user: UserRecord = Depends(require_user)) -> list[InterviewSession]:
    return service.list_sessions(store, user)


@router.post("/sessions", response_model=InterviewSession, status_code=201)
def create_session(body: CreateSessionRequest, user: UserRecord = Depends(require_user)) -> InterviewSession:
    return service.create_session(store, user, body.title, body.prompt, body.scheduledAt)


@router.get("/sessions/{sessionId}", response_model=InterviewSession)
def get_session(sessionId: str, request: Request) -> InterviewSession:
    require_room_access(sessionId, request)
    return service.require_session(store, sessionId)


@router.patch("/sessions/{sessionId}", response_model=InterviewSession)
async def update_session(
    sessionId: str, patch: SessionPatch, user: UserRecord | None = Depends(get_optional_user)
) -> InterviewSession:
    session = service.update_session(store, sessionId, user, patch)
    await manager.broadcast(sessionId, PermissionChangedMessage(session=session))
    return session


@router.post("/sessions/{sessionId}/start", response_model=InterviewSession)
async def start_session(sessionId: str, user: UserRecord | None = Depends(get_optional_user)) -> InterviewSession:
    session = service.start_session(store, sessionId, user)
    await manager.broadcast(sessionId, PermissionChangedMessage(session=session))
    return session


@router.post("/sessions/{sessionId}/end", response_model=InterviewSession)
async def end_session(sessionId: str, user: UserRecord | None = Depends(get_optional_user)) -> InterviewSession:
    session = service.end_session(store, sessionId, user)
    await manager.broadcast(sessionId, SessionEndedMessage(session=session))
    return session


@router.post("/sessions/{sessionId}/archive", response_model=InterviewSession)
def archive_session(sessionId: str, user: UserRecord | None = Depends(get_optional_user)) -> InterviewSession:
    return service.archive_session(store, sessionId, user)


@router.post("/sessions/{sessionId}/duplicate", response_model=InterviewSession, status_code=201)
def duplicate_session(sessionId: str, user: UserRecord | None = Depends(get_optional_user)) -> InterviewSession:
    return service.duplicate_session(store, sessionId, user)
