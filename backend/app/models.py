"""Pydantic schemas mirroring the components in openapi.yaml.

Field names and shapes are kept identical to `frontend/src/services/types.ts`
so the JSON on the wire matches the frontend's expectations exactly.
"""

from __future__ import annotations

from enum import Enum
from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field


class Role(str, Enum):
    owner = "owner"
    interviewer = "interviewer"
    candidate = "candidate"
    observer = "observer"


class GuestRole(str, Enum):
    candidate = "candidate"
    observer = "observer"


class SessionState(str, Enum):
    draft = "draft"
    live = "live"
    ended = "ended"
    archived = "archived"


class ErrorResponse(BaseModel):
    code: str
    message: str


# ---------------------------------------------------------------- auth --

class User(BaseModel):
    id: str
    email: str
    displayName: str
    createdAt: str


class SignInRequest(BaseModel):
    email: str
    password: str | None = None


# ------------------------------------------------------------ sessions --

class InterviewSession(BaseModel):
    id: str
    ownerUserId: str
    title: str
    prompt: str
    state: SessionState
    candidateEditingEnabled: bool
    cursorsVisible: bool
    scheduledAt: str | None
    startedAt: str | None
    endedAt: str | None
    createdAt: str
    updatedAt: str


class CreateSessionRequest(BaseModel):
    title: str
    prompt: str
    scheduledAt: str | None = None


class SessionPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = None
    prompt: str | None = None
    candidateEditingEnabled: bool | None = None
    cursorsVisible: bool | None = None
    scheduledAt: str | None = None


# --------------------------------------------------------- guest links --

class GuestLink(BaseModel):
    id: str
    sessionId: str
    token: str
    roleGranted: GuestRole
    expiresAt: str | None
    maxUses: int | None
    uses: int
    revokedAt: str | None
    createdAt: str


class CreateGuestLinkRequest(BaseModel):
    role: GuestRole = GuestRole.candidate


# --------------------------------------------------------- participants --

class Participant(BaseModel):
    id: str
    sessionId: str
    userId: str | None
    displayName: str = Field(max_length=40)
    role: Role
    color: Literal["amberdeep", "warm", "remote", "live"]
    joinedAt: str
    leftAt: str | None


class JoinResult(BaseModel):
    session: InterviewSession
    participant: Participant


class JoinWithTokenResponse(JoinResult):
    participantToken: str


class JoinWithTokenRequest(BaseModel):
    token: str
    displayName: str


class ClearCanvasRequest(BaseModel):
    actorId: str


# --------------------------------------------------------- canvas doc --

class BaseElementFields(BaseModel):
    id: str
    createdBy: str
    updatedAt: int


class NodeElement(BaseElementFields):
    kind: Literal["node"] = "node"
    componentType: str
    label: str
    description: str
    x: float
    y: float
    width: float
    height: float


class StickyElement(BaseElementFields):
    kind: Literal["sticky"] = "sticky"
    text: str
    x: float
    y: float
    width: float
    height: float


class TextElement(BaseElementFields):
    kind: Literal["text"] = "text"
    text: str
    x: float
    y: float


class StrokeElement(BaseElementFields):
    kind: Literal["stroke"] = "stroke"
    points: list[float]
    color: Literal["ink", "amber", "remote", "warm"]
    width: float
    highlighter: bool


class ConnectorElement(BaseElementFields):
    kind: Literal["connector"] = "connector"
    fromId: str
    toId: str
    label: str
    style: Literal["straight", "elbow", "curved"]
    dashed: bool
    arrowEnd: bool


CanvasElement = Annotated[
    Union[NodeElement, StickyElement, TextElement, StrokeElement, ConnectorElement],
    Field(discriminator="kind"),
]


class CanvasOpUpsert(BaseModel):
    type: Literal["upsert"] = "upsert"
    element: CanvasElement


class CanvasOpDelete(BaseModel):
    type: Literal["delete"] = "delete"
    id: str


class CanvasOpClear(BaseModel):
    type: Literal["clear"] = "clear"


CanvasOp = Annotated[
    Union[CanvasOpUpsert, CanvasOpDelete, CanvasOpClear],
    Field(discriminator="type"),
]


class CanvasOperationEnvelope(BaseModel):
    id: str
    clientOperationId: str
    actorId: str
    op: CanvasOp
    serverReceivedAt: int
    cursor: int


class CanvasSnapshot(BaseModel):
    sessionId: str
    cursor: int
    elements: list[CanvasElement]
    updatedAt: str


# ----------------------------------------------------------- realtime --

class CursorPoint(BaseModel):
    x: float
    y: float


class PresenceState(BaseModel):
    participantId: str
    displayName: str
    role: Role
    color: str
    cursor: CursorPoint | None
    selection: list[str]
    online: bool


class RoomJoinedMessage(BaseModel):
    type: Literal["room_joined"] = "room_joined"
    snapshot: CanvasSnapshot
    presence: list[PresenceState]


class DocumentUpdateMessage(BaseModel):
    type: Literal["document_update"] = "document_update"
    ops: list[CanvasOperationEnvelope]


class PresenceUpdateMessage(BaseModel):
    type: Literal["presence_update"] = "presence_update"
    presence: list[PresenceState]


class PermissionChangedMessage(BaseModel):
    type: Literal["permission_changed"] = "permission_changed"
    session: InterviewSession


class SessionEndedMessage(BaseModel):
    type: Literal["session_ended"] = "session_ended"
    session: InterviewSession


class RoomErrorMessage(BaseModel):
    type: Literal["error"] = "error"
    code: Literal["forbidden", "editing_locked", "offline"]
    message: str


ServerMessage = Annotated[
    Union[
        RoomJoinedMessage,
        DocumentUpdateMessage,
        PresenceUpdateMessage,
        PermissionChangedMessage,
        SessionEndedMessage,
        RoomErrorMessage,
    ],
    Field(discriminator="type"),
]


class ClientOpItem(BaseModel):
    clientOperationId: str
    op: CanvasOp


class ClientOpsMessage(BaseModel):
    type: Literal["ops"] = "ops"
    ops: list[ClientOpItem] = Field(min_length=1)


class ClientPresenceMessage(BaseModel):
    type: Literal["presence"] = "presence"
    cursor: CursorPoint | None = None
    selection: list[str] | None = None


ClientMessage = Annotated[
    Union[ClientOpsMessage, ClientPresenceMessage],
    Field(discriminator="type"),
]
