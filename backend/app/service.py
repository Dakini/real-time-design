"""Business logic, mirroring `frontend/src/services/mock/mockApi.ts`.

Routers translate HTTP/WS concerns into calls here; this module is the only
place that queries or mutates the database.
"""

from __future__ import annotations

import threading

from pydantic import TypeAdapter
from sqlalchemy.orm import Session

from .canvas_ops import apply_op
from .clock import now_iso, now_ms
from .db_models import (
    CanvasElementRow,
    CanvasOperationRow,
    GuestLinkRow,
    InterviewerSessionTokenRow,
    ParticipantRow,
    ParticipantTokenHashRow,
    SessionRow,
    UserRow,
)
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

PARTICIPANT_COLORS = ["amberdeep", "warm", "remote", "live"]

# Guards compound check-then-write operations (e.g. "revoke existing link,
# then create a new one") against races between requests served on different
# threads; a single global lock is enough at this scale.
_write_lock = threading.RLock()

_canvas_element_adapter: TypeAdapter[CanvasElement] = TypeAdapter(CanvasElement)


def _next_color(db: Session, session_id: str) -> str:
    used = db.query(ParticipantRow).filter_by(sessionId=session_id).count()
    return PARTICIPANT_COLORS[used % len(PARTICIPANT_COLORS)]


# ---------------------------------------------------------------- auth --

def get_current_user_model(user: UserRow | None) -> User | None:
    return User.model_validate(user, from_attributes=True) if user else None


def sign_in(db: Session, email: str, password: str | None) -> tuple[User, str]:
    """Upsert-by-email sign in. Returns (user, raw session token)."""
    with _write_lock:
        user = db.query(UserRow).filter_by(email=email).one_or_none()
        if user is None:
            user = UserRow(
                id=new_id("user"),
                email=email,
                displayName=email.split("@")[0] or "Interviewer",
                createdAt=now_iso(),
                password_hash=hash_password(password) if password else hash_password(secure_token()),
            )
            db.add(user)
        elif password and not verify_password(password, user.password_hash):
            raise bad_request("Incorrect password.", code="invalid_credentials")

        token = new_bearer_token()
        db.add(InterviewerSessionTokenRow(tokenHash=hash_token(token), userId=user.id))
        db.commit()
        db.refresh(user)
        return User.model_validate(user, from_attributes=True), token


def sign_out(db: Session, raw_token: str | None) -> None:
    if not raw_token:
        return
    with _write_lock:
        db.query(InterviewerSessionTokenRow).filter_by(tokenHash=hash_token(raw_token)).delete()
        db.commit()


# ------------------------------------------------------------ sessions --

def require_session_row(db: Session, session_id: str) -> SessionRow:
    row = db.get(SessionRow, session_id)
    if row is None:
        raise session_not_found()
    return row


def require_session(db: Session, session_id: str) -> InterviewSession:
    return InterviewSession.model_validate(require_session_row(db, session_id), from_attributes=True)


def require_owner_row(db: Session, session_id: str, user: UserRow | None) -> SessionRow:
    row = require_session_row(db, session_id)
    if user is None or row.ownerUserId != user.id:
        raise owner_only()
    return row


def list_sessions(db: Session, user: UserRow) -> list[InterviewSession]:
    rows = (
        db.query(SessionRow)
        .filter(SessionRow.ownerUserId == user.id, SessionRow.state != SessionState.archived.value)
        .order_by(SessionRow.updatedAt.desc())
        .all()
    )
    return [InterviewSession.model_validate(r, from_attributes=True) for r in rows]


def create_session(db: Session, user: UserRow, title: str, prompt: str, scheduled_at: str | None) -> InterviewSession:
    now = now_iso()
    with _write_lock:
        row = SessionRow(
            id=new_id("ses"),
            ownerUserId=user.id,
            title=title.strip() or "Untitled interview",
            prompt=prompt.strip(),
            state=SessionState.draft.value,
            candidateEditingEnabled=True,
            cursorsVisible=True,
            scheduledAt=scheduled_at,
            startedAt=None,
            endedAt=None,
            createdAt=now,
            updatedAt=now,
            cursor=0,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
    return InterviewSession.model_validate(row, from_attributes=True)


def update_session(db: Session, session_id: str, user: UserRow | None, patch: SessionPatch) -> InterviewSession:
    with _write_lock:
        row = require_owner_row(db, session_id, user)
        changes = patch.model_dump(exclude_unset=True)
        if not changes:
            raise bad_request("Patch body must include at least one field.")
        for key, value in changes.items():
            setattr(row, key, value)
        row.updatedAt = now_iso()
        db.commit()
        db.refresh(row)
    return InterviewSession.model_validate(row, from_attributes=True)


def start_session(db: Session, session_id: str, user: UserRow | None) -> InterviewSession:
    with _write_lock:
        row = require_owner_row(db, session_id, user)
        if row.state in (SessionState.ended.value, SessionState.archived.value):
            raise conflict("The session is ended or archived and cannot be started.")
        row.state = SessionState.live.value
        row.startedAt = row.startedAt or now_iso()
        row.updatedAt = now_iso()
        db.commit()
        db.refresh(row)
    return InterviewSession.model_validate(row, from_attributes=True)


def end_session(db: Session, session_id: str, user: UserRow | None) -> InterviewSession:
    with _write_lock:
        row = require_owner_row(db, session_id, user)
        row.state = SessionState.ended.value
        row.candidateEditingEnabled = False
        row.endedAt = now_iso()
        row.updatedAt = row.endedAt
        db.commit()
        db.refresh(row)
    return InterviewSession.model_validate(row, from_attributes=True)


def archive_session(db: Session, session_id: str, user: UserRow | None) -> InterviewSession:
    with _write_lock:
        row = require_owner_row(db, session_id, user)
        row.state = SessionState.archived.value
        row.updatedAt = now_iso()
        db.commit()
        db.refresh(row)
    return InterviewSession.model_validate(row, from_attributes=True)


def duplicate_session(db: Session, session_id: str, user: UserRow | None) -> InterviewSession:
    with _write_lock:
        source = require_owner_row(db, session_id, user)
        copy = create_session(db, user, f"{source.title} (copy)", source.prompt, None)
        source_elements = db.query(CanvasElementRow).filter_by(sessionId=source.id).order_by(CanvasElementRow.seq).all()
        for el in source_elements:
            db.add(CanvasElementRow(sessionId=copy.id, id=el.id, data=el.data))
        db.commit()
    return copy


# --------------------------------------------------------- guest links --

def list_guest_links(db: Session, session_id: str, user: UserRow | None) -> list[GuestLink]:
    require_owner_row(db, session_id, user)
    rows = db.query(GuestLinkRow).filter(GuestLinkRow.sessionId == session_id, GuestLinkRow.revokedAt.is_(None)).all()
    return [GuestLink.model_validate(r, from_attributes=True) for r in rows]


def create_guest_link(db: Session, session_id: str, user: UserRow | None, role: GuestRole) -> GuestLink:
    with _write_lock:
        require_owner_row(db, session_id, user)
        existing = db.query(GuestLinkRow).filter(
            GuestLinkRow.sessionId == session_id,
            GuestLinkRow.roleGranted == role.value,
            GuestLinkRow.revokedAt.is_(None),
        ).all()
        for link in existing:
            link.revokedAt = now_iso()

        row = GuestLinkRow(
            id=new_id("lnk"),
            sessionId=session_id,
            token=secure_token(),
            roleGranted=role.value,
            expiresAt=None,
            maxUses=10,
            uses=0,
            revokedAt=None,
            createdAt=now_iso(),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
    return GuestLink.model_validate(row, from_attributes=True)


def revoke_guest_link(db: Session, session_id: str, user: UserRow | None, link_id: str) -> None:
    with _write_lock:
        require_owner_row(db, session_id, user)
        row = db.get(GuestLinkRow, link_id)
        if row is None or row.sessionId != session_id:
            raise not_found("Link not found")
        row.revokedAt = now_iso()
        db.commit()


# --------------------------------------------------------- participants --

def list_participants(db: Session, session_id: str) -> list[Participant]:
    rows = db.query(ParticipantRow).filter(ParticipantRow.sessionId == session_id, ParticipantRow.leftAt.is_(None)).all()
    return [Participant.model_validate(r, from_attributes=True) for r in rows]


def join_with_token(db: Session, token: str, display_name: str) -> tuple[InterviewSession, Participant, str]:
    with _write_lock:
        link = db.query(GuestLinkRow).filter_by(token=token).one_or_none()
        if link is None:
            raise AppError(404, "link_invalid", "This link is not valid.")
        if link.revokedAt is not None:
            raise AppError(403, "link_revoked", "This link has been revoked by the interviewer.")
        if link.expiresAt is not None and link.expiresAt < now_iso():
            raise AppError(403, "link_expired", "This link has expired.")

        session_row = require_session_row(db, link.sessionId)
        if session_row.state == SessionState.archived.value:
            raise AppError(403, "session_archived", "This interview is no longer available.")
        if session_row.state == SessionState.ended.value:
            raise AppError(403, "session_ended", "This interview has ended.")

        active_count = (
            db.query(ParticipantRow)
            .filter(ParticipantRow.sessionId == session_row.id, ParticipantRow.leftAt.is_(None))
            .count()
        )
        if link.maxUses is not None and active_count >= link.maxUses:
            raise AppError(409, "session_full", "This interview is full.")

        name = display_name.strip()
        if len(name) < 2:
            raise AppError(400, "invalid_display_name", "Please enter your name.")

        link.uses += 1
        participant_row = ParticipantRow(
            id=new_id("pt"),
            sessionId=session_row.id,
            userId=None,
            displayName=name[:40],
            role=link.roleGranted,
            color=_next_color(db, session_row.id),
            joinedAt=now_iso(),
            leftAt=None,
        )
        db.add(participant_row)

        raw_token = new_bearer_token()
        db.add(ParticipantTokenHashRow(tokenHash=hash_token(raw_token), participantId=participant_row.id))
        db.commit()
        db.refresh(session_row)
        db.refresh(participant_row)

        return (
            InterviewSession.model_validate(session_row, from_attributes=True),
            Participant.model_validate(participant_row, from_attributes=True),
            raw_token,
        )


def join_as_owner(db: Session, session_id: str, user: UserRow | None) -> tuple[InterviewSession, Participant]:
    if user is None:
        raise AppError(401, "unauthenticated", "Not authenticated")
    with _write_lock:
        session_row = require_session_row(db, session_id)
        existing = db.query(ParticipantRow).filter(
            ParticipantRow.sessionId == session_id,
            ParticipantRow.userId == user.id,
            ParticipantRow.leftAt.is_(None),
        ).one_or_none()
        if existing is not None:
            return (
                InterviewSession.model_validate(session_row, from_attributes=True),
                Participant.model_validate(existing, from_attributes=True),
            )

        role = Role.owner.value if session_row.ownerUserId == user.id else Role.interviewer.value
        participant_row = ParticipantRow(
            id=new_id("pt"),
            sessionId=session_id,
            userId=user.id,
            displayName=user.displayName,
            role=role,
            color=_next_color(db, session_id),
            joinedAt=now_iso(),
            leftAt=None,
        )
        db.add(participant_row)
        db.commit()
        db.refresh(session_row)
        db.refresh(participant_row)
        return (
            InterviewSession.model_validate(session_row, from_attributes=True),
            Participant.model_validate(participant_row, from_attributes=True),
        )


def remove_participant(db: Session, session_id: str, user: UserRow | None, participant_id: str) -> None:
    with _write_lock:
        require_owner_row(db, session_id, user)
        row = db.get(ParticipantRow, participant_id)
        if row is None or row.sessionId != session_id:
            raise not_found("Participant not found")
        row.leftAt = now_iso()
        db.query(ParticipantTokenHashRow).filter_by(participantId=participant_id).delete()
        db.commit()


# --------------------------------------------------------------- canvas --

def snapshot(db: Session, session_id: str) -> CanvasSnapshot:
    session_row = db.get(SessionRow, session_id)
    cursor = session_row.cursor if session_row is not None else 0
    rows = db.query(CanvasElementRow).filter_by(sessionId=session_id).order_by(CanvasElementRow.seq).all()
    elements = [_canvas_element_adapter.validate_python(r.data) for r in rows]
    return CanvasSnapshot(sessionId=session_id, cursor=cursor, elements=elements, updatedAt=now_iso())


def get_canvas(db: Session, session_id: str) -> CanvasSnapshot:
    require_session_row(db, session_id)
    return snapshot(db, session_id)


def commit_ops(db: Session, session_id: str, actor_id: str, items: list[tuple[str, CanvasOp]]) -> list[CanvasOperationEnvelope]:
    """Apply a batch of (clientOperationId, op) pairs, dropping already-applied ids."""
    with _write_lock:
        session_row = require_session_row(db, session_id)
        element_rows = db.query(CanvasElementRow).filter_by(sessionId=session_id).order_by(CanvasElementRow.seq).all()
        elements = [_canvas_element_adapter.validate_python(r.data) for r in element_rows]
        seen = {
            row.clientOperationId
            for row in db.query(CanvasOperationRow.clientOperationId).filter_by(sessionId=session_id).all()
        }
        cursor = session_row.cursor
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
            db.add(CanvasOperationRow(
                id=env.id,
                sessionId=session_id,
                clientOperationId=env.clientOperationId,
                actorId=env.actorId,
                op=op.model_dump(mode="json"),
                serverReceivedAt=env.serverReceivedAt,
                cursor=env.cursor,
            ))
            seen.add(client_op_id)
            envelopes.append(env)

        if envelopes:
            db.query(CanvasElementRow).filter_by(sessionId=session_id).delete()
            for el in elements:
                db.add(CanvasElementRow(sessionId=session_id, id=el.id, data=el.model_dump(mode="json")))
            session_row.cursor = cursor
        db.commit()
    return envelopes


def commit_server_ops(db: Session, session_id: str, actor_id: str, ops: list[CanvasOp]) -> list[CanvasOperationEnvelope]:
    items = [(new_id("cop"), op) for op in ops]
    return commit_ops(db, session_id, actor_id, items)


def clear_canvas(db: Session, session_id: str, user: UserRow | None, actor_id: str) -> list[CanvasOperationEnvelope]:
    require_owner_row(db, session_id, user)
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
