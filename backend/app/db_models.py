"""SQLAlchemy ORM models backing the persistent store.

Column names intentionally match the Pydantic field names in `models.py`
one-for-one, so a row converts to its API model with a single call:
`SomeModel.model_validate(row, from_attributes=True)`.
"""

from __future__ import annotations

from sqlalchemy import JSON, BigInteger, Boolean, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class UserRow(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    displayName: Mapped[str] = mapped_column(String)
    createdAt: Mapped[str] = mapped_column(String)
    password_hash: Mapped[str] = mapped_column(String)


class InterviewerSessionTokenRow(Base):
    __tablename__ = "interviewer_session_tokens"

    tokenHash: Mapped[str] = mapped_column(String, primary_key=True)
    userId: Mapped[str] = mapped_column(ForeignKey("users.id"))


class SessionRow(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    ownerUserId: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String)
    prompt: Mapped[str] = mapped_column(String)
    state: Mapped[str] = mapped_column(String)
    candidateEditingEnabled: Mapped[bool] = mapped_column(Boolean)
    cursorsVisible: Mapped[bool] = mapped_column(Boolean)
    scheduledAt: Mapped[str | None] = mapped_column(String, nullable=True)
    startedAt: Mapped[str | None] = mapped_column(String, nullable=True)
    endedAt: Mapped[str | None] = mapped_column(String, nullable=True)
    createdAt: Mapped[str] = mapped_column(String)
    updatedAt: Mapped[str] = mapped_column(String)
    # Canvas operation cursor for this session; not part of the InterviewSession
    # API model, so `model_validate(row, from_attributes=True)` simply ignores it.
    cursor: Mapped[int] = mapped_column(Integer, default=0)


class GuestLinkRow(Base):
    __tablename__ = "guest_links"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    sessionId: Mapped[str] = mapped_column(ForeignKey("sessions.id"), index=True)
    token: Mapped[str] = mapped_column(String, unique=True, index=True)
    roleGranted: Mapped[str] = mapped_column(String)
    expiresAt: Mapped[str | None] = mapped_column(String, nullable=True)
    maxUses: Mapped[int | None] = mapped_column(Integer, nullable=True)
    uses: Mapped[int] = mapped_column(Integer, default=0)
    revokedAt: Mapped[str | None] = mapped_column(String, nullable=True)
    createdAt: Mapped[str] = mapped_column(String)


class ParticipantRow(Base):
    __tablename__ = "participants"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    sessionId: Mapped[str] = mapped_column(ForeignKey("sessions.id"), index=True)
    userId: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    displayName: Mapped[str] = mapped_column(String)
    role: Mapped[str] = mapped_column(String)
    color: Mapped[str] = mapped_column(String)
    joinedAt: Mapped[str] = mapped_column(String)
    leftAt: Mapped[str | None] = mapped_column(String, nullable=True)


class ParticipantTokenHashRow(Base):
    __tablename__ = "participant_token_hashes"

    tokenHash: Mapped[str] = mapped_column(String, primary_key=True)
    participantId: Mapped[str] = mapped_column(ForeignKey("participants.id"))


class CanvasElementRow(Base):
    __tablename__ = "canvas_elements"
    __table_args__ = (UniqueConstraint("sessionId", "id", name="uq_canvas_elements_session_id"),)

    seq: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id: Mapped[str] = mapped_column(String)
    sessionId: Mapped[str] = mapped_column(ForeignKey("sessions.id"), index=True)
    data: Mapped[dict] = mapped_column(JSON)


class CanvasOperationRow(Base):
    __tablename__ = "canvas_operations"
    __table_args__ = (UniqueConstraint("sessionId", "clientOperationId", name="uq_canvas_ops_session_client_op"),)

    seq: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id: Mapped[str] = mapped_column(String)
    sessionId: Mapped[str] = mapped_column(ForeignKey("sessions.id"), index=True)
    clientOperationId: Mapped[str] = mapped_column(String)
    actorId: Mapped[str] = mapped_column(String)
    op: Mapped[dict] = mapped_column(JSON)
    # Epoch milliseconds, which overflow a 32-bit INTEGER on Postgres.
    serverReceivedAt: Mapped[int] = mapped_column(BigInteger)
    cursor: Mapped[int] = mapped_column(Integer)
