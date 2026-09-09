"""Deterministic demo data, seeded into an empty database."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from .clock import now_ms
from .db_models import CanvasElementRow, GuestLinkRow, ParticipantRow, SessionRow, UserRow
from .models import (
    ConnectorElement,
    GuestLink,
    GuestRole,
    InterviewSession,
    NodeElement,
    Participant,
    Role,
    SessionState,
    StickyElement,
)
from .security import hash_password


def seed_demo_data(db: Session) -> None:
    now = datetime.now(timezone.utc)

    def iso(offset_minutes: float) -> str:
        t = now + timedelta(minutes=offset_minutes)
        return t.strftime("%Y-%m-%dT%H:%M:%S.") + f"{t.microsecond // 1000:03d}Z"

    owner = UserRow(
        id="user_owner",
        email="jordan@linewarmer.io",
        displayName="Jordan Reyes",
        createdAt=iso(0),
        password_hash=hash_password("linewarmer-demo"),
    )
    db.add(owner)

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
        db.add(SessionRow(**s.model_dump(mode="json"), cursor=0))

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
    db.add(GuestLinkRow(**link.model_dump(mode="json")))

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
    db.add(ParticipantRow(**owner_participant.model_dump(mode="json")))

    ms = now_ms()
    ratelimiter_elements = [
        NodeElement(id="el_client", componentType="browser-client", label="Web Client", description="mobile / browser", x=120, y=220, width=160, height=60, createdBy="pt_owner", updatedAt=ms),
        NodeElement(id="el_gateway", componentType="api-gateway", label="API Gateway", description="authn · throttling", x=380, y=170, width=176, height=60, createdBy="pt_owner", updatedAt=ms),
        NodeElement(id="el_cache", componentType="cache", label="Redis Cache", description="token bucket", x=660, y=220, width=160, height=60, createdBy="pt_owner", updatedAt=ms),
        NodeElement(id="el_db", componentType="relational-db", label="Postgres", description="quotas · rules", x=400, y=400, width=176, height=60, createdBy="pt_owner", updatedAt=ms),
        StickyElement(id="el_goal", text="Handle 100k req/s with per-key counters, no single point of failure.", x=100, y=60, width=176, height=96, createdBy="pt_owner", updatedAt=ms),
        ConnectorElement(id="el_c1", fromId="el_client", toId="el_gateway", label="HTTPS", style="curved", dashed=False, arrowEnd=True, createdBy="pt_owner", updatedAt=ms),
        ConnectorElement(id="el_c2", fromId="el_gateway", toId="el_cache", label="read", style="curved", dashed=False, arrowEnd=True, createdBy="pt_owner", updatedAt=ms),
        ConnectorElement(id="el_c3", fromId="el_gateway", toId="el_db", label="persist", style="curved", dashed=True, arrowEnd=True, createdBy="pt_owner", updatedAt=ms),
    ]
    chatscale_elements = [
        NodeElement(id="el_ws", componentType="server", label="WebSocket Fleet", description="sticky sessions", x=220, y=180, width=176, height=60, createdBy="pt_owner", updatedAt=ms),
        NodeElement(id="el_fanout", componentType="pubsub", label="Fan-out broker", description="per-room topics", x=520, y=260, width=176, height=60, createdBy="pt_owner", updatedAt=ms),
        ConnectorElement(id="el_ws_c", fromId="el_ws", toId="el_fanout", label="events", style="curved", dashed=False, arrowEnd=True, createdBy="pt_owner", updatedAt=ms),
    ]

    for session_id, elements in (
        ("ses_ratelimiter", ratelimiter_elements),
        ("ses_chatscale", chatscale_elements),
        ("ses_cdn", []),
    ):
        for el in elements:
            db.add(CanvasElementRow(sessionId=session_id, id=el.id, data=el.model_dump(mode="json")))
