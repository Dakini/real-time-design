"""Business logic, mirroring `frontend/src/services/mock/mockApi.ts`.

Routers translate HTTP/WS concerns into calls here; this module is the only
place that mutates the store.
"""

from __future__ import annotations

from .canvas_ops import apply_op
from .errors import AppError, bad_request, conflict, forbidden, not_found, owner_only, session_not_found
from .ids import new_id, secure_token
from .models import (
    CanvasElement,
    CanvasOp,
    CanvasOpClear,
    CanvasOperationEnvelope,
    CanvasSnapshot,
    GuestLink,
    GuestRole,
    InterviewSession,
    Participant,
    Role,
    SessionPatch,
    SessionState,
    User,
)
from .security import hash_password, hash_token, new_bearer_token, verify_password
from .store import PARTICIPANT_COLORS, Store, UserRecord, now_iso, now_ms, store


# ---------------------------------------------------------------- auth --

def get_current_user_model(user: UserRecord | None) -> User | None:
    return user.to_model() if user else None


def sign_in(db: Store, email: str, password: str | None) -> tuple[User, str]:
    """Upsert-by-email sign in. Returns (user, raw session token)."""
    with db.lock:
        user_id = db.users_by_email.get(email)
        if user_id is None:
            user = UserRecord(
                id=new_id("user"),
                email=email,
                displayName=email.split("@")[0] or "Interviewer",
                createdAt=now_iso(),
                password_hash=hash_password(password) if password else hash_password(secure_token()),
            )
            db.users[user.id] = user
            db.users_by_email[email] = user.id
        else:
            user = db.users[user_id]
            if password and not verify_password(password, user.password_hash):
                raise bad_request("Incorrect password.", code="invalid_credentials")

        token = new_bearer_token()
        db.interviewer_session_tokens[hash_token(token)] = user.id
        return user.to_model(), token


def sign_out(db: Store, raw_token: str | None) -> None:
    if not raw_token:
        return
    with db.lock:
        db.interviewer_session_tokens.pop(hash_token(raw_token), None)


# ------------------------------------------------------------ sessions --

def require_session(db: Store, session_id: str) -> InterviewSession:
    session = db.sessions.get(session_id)
    if session is None:
        raise session_not_found()
    return session


def require_owner(db: Store, session_id: str, user: UserRecord | None) -> InterviewSession:
    session = require_session(db, session_id)
    if user is None or session.ownerUserId != user.id:
        raise owner_only()
    return session


def list_sessions(db: Store, user: UserRecord) -> list[InterviewSession]:
    sessions = [s for s in db.sessions.values() if s.ownerUserId == user.id and s.state != SessionState.archived]
    sessions.sort(key=lambda s: s.updatedAt, reverse=True)
    return sessions


def create_session(db: Store, user: UserRecord, title: str, prompt: str, scheduled_at: str | None) -> InterviewSession:
    now = now_iso()
    session = InterviewSession(
        id=new_id("ses"),
        ownerUserId=user.id,
        title=title.strip() or "Untitled interview",
        prompt=prompt.strip(),
        state=SessionState.draft,
        candidateEditingEnabled=True,
        cursorsVisible=True,
        scheduledAt=scheduled_at,
        startedAt=None,
        endedAt=None,
        createdAt=now,
        updatedAt=now,
    )
    with db.lock:
        db.sessions[session.id] = session
        db.elements[session.id] = []
        db.operations[session.id] = []
        db.cursors[session.id] = 0
    return session


def update_session(db: Store, session_id: str, user: UserRecord | None, patch: SessionPatch) -> InterviewSession:
    session = require_owner(db, session_id, user)
    changes = patch.model_dump(exclude_unset=True)
    if not changes:
        raise bad_request("Patch body must include at least one field.")
    for key, value in changes.items():
        setattr(session, key, value)
    session.updatedAt = now_iso()
    return session


def start_session(db: Store, session_id: str, user: UserRecord | None) -> InterviewSession:
    session = require_owner(db, session_id, user)
    if session.state in (SessionState.ended, SessionState.archived):
        raise conflict("The session is ended or archived and cannot be started.")
    session.state = SessionState.live
    session.startedAt = session.startedAt or now_iso()
    session.updatedAt = now_iso()
    return session


def end_session(db: Store, session_id: str, user: UserRecord | None) -> InterviewSession:
    session = require_owner(db, session_id, user)
    session.state = SessionState.ended
    session.candidateEditingEnabled = False
    session.endedAt = now_iso()
    session.updatedAt = session.endedAt
    return session


def archive_session(db: Store, session_id: str, user: UserRecord | None) -> InterviewSession:
    session = require_owner(db, session_id, user)
    session.state = SessionState.archived
    session.updatedAt = now_iso()
    return session


def duplicate_session(db: Store, session_id: str, user: UserRecord | None) -> InterviewSession:
    source = require_owner(db, session_id, user)
    copy = create_session(db, user, f"{source.title} (copy)", source.prompt, None)
    with db.lock:
        db.elements[copy.id] = [el.model_copy() for el in db.elements.get(source.id, [])]
    return copy


# --------------------------------------------------------- guest links --

def list_guest_links(db: Store, session_id: str, user: UserRecord | None) -> list[GuestLink]:
    require_owner(db, session_id, user)
    return [l for l in db.links.values() if l.sessionId == session_id and l.revokedAt is None]


def create_guest_link(db: Store, session_id: str, user: UserRecord | None, role: GuestRole) -> GuestLink:
    require_owner(db, session_id, user)
    with db.lock:
        for link in db.links.values():
            if link.sessionId == session_id and link.roleGranted == role and link.revokedAt is None:
                link.revokedAt = now_iso()
        link = GuestLink(
            id=new_id("lnk"),
            sessionId=session_id,
            token=secure_token(),
            roleGranted=role,
            expiresAt=None,
            maxUses=10,
            uses=0,
            revokedAt=None,
            createdAt=now_iso(),
        )
        db.links[link.id] = link
        db.links_by_token[link.token] = link.id
    return link


def revoke_guest_link(db: Store, session_id: str, user: UserRecord | None, link_id: str) -> None:
    require_owner(db, session_id, user)
    link = db.links.get(link_id)
    if link is None or link.sessionId != session_id:
        raise not_found("Link not found")
    link.revokedAt = now_iso()


# --------------------------------------------------------- participants --

def list_participants(db: Store, session_id: str) -> list[Participant]:
    return [p for p in db.participants.values() if p.sessionId == session_id and p.leftAt is None]


def join_with_token(db: Store, token: str, display_name: str) -> tuple[InterviewSession, Participant, str]:
    with db.lock:
        link_id = db.links_by_token.get(token)
        link = db.links.get(link_id) if link_id else None
        if link is None:
            raise AppError(404, "link_invalid", "This link is not valid.")
        if link.revokedAt is not None:
            raise AppError(403, "link_revoked", "This link has been revoked by the interviewer.")
        if link.expiresAt is not None and link.expiresAt < now_iso():
            raise AppError(403, "link_expired", "This link has expired.")

        session = require_session(db, link.sessionId)
        if session.state == SessionState.archived:
            raise AppError(403, "session_archived", "This interview is no longer available.")
        if session.state == SessionState.ended:
            raise AppError(403, "session_ended", "This interview has ended.")

        active = [p for p in db.participants.values() if p.sessionId == session.id and p.leftAt is None]
        if link.maxUses is not None and len(active) >= link.maxUses:
            raise AppError(409, "session_full", "This interview is full.")

        name = display_name.strip()
        if len(name) < 2:
            raise AppError(400, "invalid_display_name", "Please enter your name.")

        link.uses += 1
        participant = Participant(
            id=new_id("pt"),
            sessionId=session.id,
            userId=None,
            displayName=name[:40],
            role=Role(link.roleGranted.value),
            color=db.next_color(session.id),
            joinedAt=now_iso(),
            leftAt=None,
        )
        db.participants[participant.id] = participant

        raw_token = new_bearer_token()
        db.participant_token_hashes[hash_token(raw_token)] = participant.id

        return session, participant, raw_token


def join_as_owner(db: Store, session_id: str, user: UserRecord | None) -> tuple[InterviewSession, Participant]:
    if user is None:
        raise AppError(401, "unauthenticated", "Not authenticated")
    session = require_session(db, session_id)
    with db.lock:
        existing = next(
            (p for p in db.participants.values() if p.sessionId == session_id and p.userId == user.id and p.leftAt is None),
            None,
        )
        if existing is not None:
            return session, existing
        role = Role.owner if session.ownerUserId == user.id else Role.interviewer
        participant = Participant(
            id=new_id("pt"),
            sessionId=session_id,
            userId=user.id,
            displayName=user.displayName,
            role=role,
            color=db.next_color(session_id),
            joinedAt=now_iso(),
            leftAt=None,
        )
        db.participants[participant.id] = participant
    return session, participant


def remove_participant(db: Store, session_id: str, user: UserRecord | None, participant_id: str) -> None:
    require_owner(db, session_id, user)
    participant = db.participants.get(participant_id)
    if participant is None or participant.sessionId != session_id:
        raise not_found("Participant not found")
    participant.leftAt = now_iso()
    for token_hash, pid in list(db.participant_token_hashes.items()):
        if pid == participant_id:
            del db.participant_token_hashes[token_hash]


# --------------------------------------------------------------- canvas --

def snapshot(db: Store, session_id: str) -> CanvasSnapshot:
    return CanvasSnapshot(
        sessionId=session_id,
        cursor=db.cursors.get(session_id, 0),
        elements=[el.model_copy() for el in db.elements.get(session_id, [])],
        updatedAt=now_iso(),
    )


def get_canvas(db: Store, session_id: str) -> CanvasSnapshot:
    require_session(db, session_id)
    return snapshot(db, session_id)


def commit_ops(db: Store, session_id: str, actor_id: str, items: list[tuple[str, CanvasOp]]) -> list[CanvasOperationEnvelope]:
    """Apply a batch of (clientOperationId, op) pairs, dropping already-applied ids."""
    with db.lock:
        log = db.operations.setdefault(session_id, [])
        seen = {e.clientOperationId for e in log}
        elements = db.elements.get(session_id, [])
        cursor = db.cursors.get(session_id, 0)
        envelopes: list[CanvasOperationEnvelope] = []
        for client_op_id, op in items:
            if client_op_id in seen:
                continue
            cursor += 1
            env = CanvasOperationEnvelope(
                id=new_id("op"),
                clientOperationId=client_op_id,
                actorId=actor_id,
                op=op,
                serverReceivedAt=now_ms(),
                cursor=cursor,
            )
            elements = apply_op(elements, op)
            log.append(env)
            seen.add(client_op_id)
            envelopes.append(env)
        db.elements[session_id] = elements
        db.cursors[session_id] = cursor
    return envelopes


def commit_server_ops(db: Store, session_id: str, actor_id: str, ops: list[CanvasOp]) -> list[CanvasOperationEnvelope]:
    items = [(new_id("cop"), op) for op in ops]
    return commit_ops(db, session_id, actor_id, items)


def clear_canvas(db: Store, session_id: str, user: UserRecord | None, actor_id: str) -> list[CanvasOperationEnvelope]:
    require_owner(db, session_id, user)
    return commit_server_ops(db, session_id, actor_id, [CanvasOpClear()])


# ------------------------------------------------------------- realtime --

def can_write(session: InterviewSession, participant: Participant) -> bool:
    if session.state in (SessionState.ended, SessionState.archived):
        return False
    if participant.role == Role.observer:
        return False
    if participant.role == Role.candidate:
        return session.candidateEditingEnabled
    return True
