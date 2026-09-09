"""In-memory data store: plain dicts guarded by a lock, no persistence.

This is intentionally the single place mutable state lives. Routers never
touch these dicts directly — they go through `app.service`.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from .models import (
    CanvasElement,
    CanvasOperationEnvelope,
    ConnectorElement,
    GuestLink,
    GuestRole,
    InterviewSession,
    NodeElement,
    Participant,
    Role,
    SessionState,
    StickyElement,
    User,
)
from .security import hash_password

PARTICIPANT_COLORS = ["amberdeep", "warm", "remote", "live"]


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.") + f"{datetime.now(timezone.utc).microsecond // 1000:03d}Z"


def now_ms() -> int:
    return int(datetime.now(timezone.utc).timestamp() * 1000)


@dataclass
class UserRecord:
    id: str
    email: str
    displayName: str
    createdAt: str
    password_hash: str

    def to_model(self) -> User:
        return User(id=self.id, email=self.email, displayName=self.displayName, createdAt=self.createdAt)


class Store:
    def __init__(self) -> None:
        self.lock = threading.RLock()

        self.users: dict[str, UserRecord] = {}
        self.users_by_email: dict[str, str] = {}

        # interviewerSession cookie: sha256(token) -> userId
        self.interviewer_session_tokens: dict[str, str] = {}

        self.sessions: dict[str, InterviewSession] = {}

        self.links: dict[str, GuestLink] = {}
        self.links_by_token: dict[str, str] = {}

        self.participants: dict[str, Participant] = {}
        # participantToken bearer credential: sha256(token) -> participantId
        self.participant_token_hashes: dict[str, str] = {}

        self.elements: dict[str, list[CanvasElement]] = {}
        self.operations: dict[str, list[CanvasOperationEnvelope]] = {}
        self.cursors: dict[str, int] = {}

    def next_color(self, session_id: str) -> str:
        used = sum(1 for p in self.participants.values() if p.sessionId == session_id)
        return PARTICIPANT_COLORS[used % len(PARTICIPANT_COLORS)]

    def reset(self) -> None:
        """Test helper: wipe and reseed deterministic demo data."""
        self.users.clear()
        self.users_by_email.clear()
        self.interviewer_session_tokens.clear()
        self.sessions.clear()
        self.links.clear()
        self.links_by_token.clear()
        self.participants.clear()
        self.participant_token_hashes.clear()
        self.elements.clear()
        self.operations.clear()
        self.cursors.clear()
        seed_demo_data(self)


store = Store()


def seed_demo_data(db: Store) -> None:
    now = datetime.now(timezone.utc)

    def iso(offset_minutes: float) -> str:
        t = now + timedelta(minutes=offset_minutes)
        return t.strftime("%Y-%m-%dT%H:%M:%S.") + f"{t.microsecond // 1000:03d}Z"

    owner = UserRecord(
        id="user_owner",
        email="jordan@linewarmer.io",
        displayName="Jordan Reyes",
        createdAt=iso(0),
        password_hash=hash_password("linewarmer-demo"),
    )
    db.users[owner.id] = owner
    db.users_by_email[owner.email] = owner.id

    sessions = [
        InterviewSession(
            id="ses_ratelimiter",
            ownerUserId=owner.id,
            title="Design a global rate limiter",
            prompt=(
                "Design a distributed rate limiter that enforces per-key quotas at "
                "100k req/s. Cover storage, failure modes, and consistency trade-offs."
            ),
            state=SessionState.live,
            candidateEditingEnabled=True,
            cursorsVisible=True,
            scheduledAt=iso(-30),
            startedAt=iso(-28),
            endedAt=None,
            createdAt=iso(-1440),
            updatedAt=iso(-2),
        ),
        InterviewSession(
            id="ses_chatscale",
            ownerUserId=owner.id,
            title="Chat at 10M concurrent users",
            prompt="Design a realtime chat backend for 10M concurrent connections with delivery guarantees.",
            state=SessionState.ended,
            candidateEditingEnabled=False,
            cursorsVisible=True,
            scheduledAt=iso(-2880),
            startedAt=iso(-2880),
            endedAt=iso(-2820),
            createdAt=iso(-4320),
            updatedAt=iso(-2820),
        ),
        InterviewSession(
            id="ses_cdn",
            ownerUserId=owner.id,
            title="CDN and edge cache strategy",
            prompt="Design an edge caching layer for a media-heavy product across three regions.",
            state=SessionState.draft,
            candidateEditingEnabled=True,
            cursorsVisible=True,
            scheduledAt=iso(2880),
            startedAt=None,
            endedAt=None,
            createdAt=iso(-120),
            updatedAt=iso(-120),
        ),
    ]
    for s in sessions:
        db.sessions[s.id] = s

    link = GuestLink(
        id="lnk_seed",
        sessionId="ses_ratelimiter",
        token="demo-candidate-token",
        roleGranted=GuestRole.candidate,
        expiresAt=None,
        maxUses=10,
        uses=1,
        revokedAt=None,
        createdAt=iso(-40),
    )
    db.links[link.id] = link
    db.links_by_token[link.token] = link.id

    owner_participant = Participant(
        id="pt_owner",
        sessionId="ses_ratelimiter",
        userId=owner.id,
        displayName=owner.displayName,
        role=Role.owner,
        color="amberdeep",
        joinedAt=iso(-28),
        leftAt=None,
    )
    db.participants[owner_participant.id] = owner_participant

    ms = now_ms()
    ratelimiter_elements: list[CanvasElement] = [
        NodeElement(id="el_client", componentType="browser-client", label="Web Client", description="mobile / browser", x=120, y=220, width=160, height=60, createdBy="pt_owner", updatedAt=ms),
        NodeElement(id="el_gateway", componentType="api-gateway", label="API Gateway", description="authn · throttling", x=380, y=170, width=176, height=60, createdBy="pt_owner", updatedAt=ms),
        NodeElement(id="el_cache", componentType="cache", label="Redis Cache", description="token bucket", x=660, y=220, width=160, height=60, createdBy="pt_owner", updatedAt=ms),
        NodeElement(id="el_db", componentType="relational-db", label="Postgres", description="quotas · rules", x=400, y=400, width=176, height=60, createdBy="pt_owner", updatedAt=ms),
        StickyElement(id="el_goal", text="Handle 100k req/s with per-key counters, no single point of failure.", x=100, y=60, width=176, height=96, createdBy="pt_owner", updatedAt=ms),
        ConnectorElement(id="el_c1", fromId="el_client", toId="el_gateway", label="HTTPS", style="curved", dashed=False, arrowEnd=True, createdBy="pt_owner", updatedAt=ms),
        ConnectorElement(id="el_c2", fromId="el_gateway", toId="el_cache", label="read", style="curved", dashed=False, arrowEnd=True, createdBy="pt_owner", updatedAt=ms),
        ConnectorElement(id="el_c3", fromId="el_gateway", toId="el_db", label="persist", style="curved", dashed=True, arrowEnd=True, createdBy="pt_owner", updatedAt=ms),
    ]

    chatscale_elements: list[CanvasElement] = [
        NodeElement(id="el_ws", componentType="server", label="WebSocket Fleet", description="sticky sessions", x=220, y=180, width=176, height=60, createdBy="pt_owner", updatedAt=ms),
        NodeElement(id="el_fanout", componentType="pubsub", label="Fan-out broker", description="per-room topics", x=520, y=260, width=176, height=60, createdBy="pt_owner", updatedAt=ms),
        ConnectorElement(id="el_ws_c", fromId="el_ws", toId="el_fanout", label="events", style="curved", dashed=False, arrowEnd=True, createdBy="pt_owner", updatedAt=ms),
    ]

    db.elements["ses_ratelimiter"] = ratelimiter_elements
    db.elements["ses_chatscale"] = chatscale_elements
    db.elements["ses_cdn"] = []

    db.operations["ses_ratelimiter"] = []
    db.operations["ses_chatscale"] = []
    db.operations["ses_cdn"] = []

    db.cursors["ses_ratelimiter"] = 0
    db.cursors["ses_chatscale"] = 0
    db.cursors["ses_cdn"] = 0


seed_demo_data(store)
