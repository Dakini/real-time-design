"""Auth dependencies: interviewerSession cookie and participantToken bearer."""

from __future__ import annotations

from fastapi import Request

from .errors import forbidden, session_not_found, unauthorized
from .security import hash_token
from .store import Store, UserRecord, store
from .models import Participant

SESSION_COOKIE = "lw_session"


def get_store() -> Store:
    return store


def get_session_cookie(request: Request) -> str | None:
    return request.cookies.get(SESSION_COOKIE)


def get_optional_user(request: Request) -> UserRecord | None:
    token = get_session_cookie(request)
    if not token:
        return None
    user_id = store.interviewer_session_tokens.get(hash_token(token))
    if user_id is None:
        return None
    return store.users.get(user_id)


def require_user(request: Request) -> UserRecord:
    user = get_optional_user(request)
    if user is None:
        raise unauthorized()
    return user


def get_bearer_token(request: Request) -> str | None:
    header = request.headers.get("authorization")
    if not header or not header.lower().startswith("bearer "):
        return None
    return header[7:].strip()


def get_optional_participant(request: Request) -> Participant | None:
    token = get_bearer_token(request)
    if not token:
        return None
    participant_id = store.participant_token_hashes.get(hash_token(token))
    if participant_id is None:
        return None
    participant = store.participants.get(participant_id)
    if participant is None or participant.leftAt is not None:
        return None
    return participant


def require_room_access(session_id: str, request: Request) -> tuple[UserRecord | None, Participant | None]:
    """Owner/interviewer via cookie, or any active participant via bearer token."""
    session = store.sessions.get(session_id)
    if session is None:
        raise session_not_found()

    user = get_optional_user(request)
    if user is not None:
        if session.ownerUserId == user.id:
            return user, None
        has_active_membership = any(
            p.sessionId == session_id and p.userId == user.id and p.leftAt is None
            for p in store.participants.values()
        )
        if has_active_membership:
            return user, None

    participant = get_optional_participant(request)
    if participant is not None and participant.sessionId == session_id:
        return None, participant

    raise forbidden()
