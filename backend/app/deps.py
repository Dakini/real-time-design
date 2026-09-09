"""Auth dependencies: interviewerSession cookie and participantToken bearer."""

from __future__ import annotations

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from .database import get_db
from .db_models import InterviewerSessionTokenRow, ParticipantRow, ParticipantTokenHashRow, SessionRow, UserRow
from .errors import forbidden, session_not_found, unauthorized
from .models import Participant
from .security import hash_token

SESSION_COOKIE = "lw_session"


def get_session_cookie(request: Request) -> str | None:
    return request.cookies.get(SESSION_COOKIE)


def get_optional_user(request: Request, db: Session = Depends(get_db)) -> UserRow | None:
    token = get_session_cookie(request)
    if not token:
        return None
    token_row = db.get(InterviewerSessionTokenRow, hash_token(token))
    if token_row is None:
        return None
    return db.get(UserRow, token_row.userId)


def require_user(request: Request, db: Session = Depends(get_db)) -> UserRow:
    user = get_optional_user(request, db)
    if user is None:
        raise unauthorized()
    return user


def get_bearer_token(request: Request) -> str | None:
    header = request.headers.get("authorization")
    if not header or not header.lower().startswith("bearer "):
        return None
    return header[7:].strip()


def get_optional_participant(request: Request, db: Session = Depends(get_db)) -> Participant | None:
    token = get_bearer_token(request)
    if not token:
        return None
    token_row = db.get(ParticipantTokenHashRow, hash_token(token))
    if token_row is None:
        return None
    row = db.get(ParticipantRow, token_row.participantId)
    if row is None or row.leftAt is not None:
        return None
    return Participant.model_validate(row, from_attributes=True)


def require_room_access(
    session_id: str, request: Request, db: Session
) -> tuple[UserRow | None, Participant | None]:
    """Owner/interviewer via cookie, or any active participant via bearer token."""
    session_row = db.get(SessionRow, session_id)
    if session_row is None:
        raise session_not_found()

    user = get_optional_user(request, db)
    if user is not None:
        if session_row.ownerUserId == user.id:
            return user, None
        has_active_membership = (
            db.query(ParticipantRow)
            .filter(
                ParticipantRow.sessionId == session_id,
                ParticipantRow.userId == user.id,
                ParticipantRow.leftAt.is_(None),
            )
            .first()
            is not None
        )
        if has_active_membership:
            return user, None

    participant = get_optional_participant(request, db)
    if participant is not None and participant.sessionId == session_id:
        return None, participant

    raise forbidden()
