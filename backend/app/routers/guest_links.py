from __future__ import annotations

from fastapi import APIRouter, Depends, status

from .. import service
from ..deps import get_optional_user
from ..models import CreateGuestLinkRequest, GuestLink
from ..store import UserRecord, store

router = APIRouter(tags=["guest-links"])


@router.get("/sessions/{sessionId}/guest-links", response_model=list[GuestLink])
def list_guest_links(sessionId: str, user: UserRecord | None = Depends(get_optional_user)) -> list[GuestLink]:
    return service.list_guest_links(store, sessionId, user)


@router.post("/sessions/{sessionId}/guest-links", response_model=GuestLink, status_code=201)
def create_guest_link(
    sessionId: str,
    body: CreateGuestLinkRequest | None = None,
    user: UserRecord | None = Depends(get_optional_user),
) -> GuestLink:
    role = body.role if body is not None else CreateGuestLinkRequest().role
    return service.create_guest_link(store, sessionId, user, role)


@router.delete("/sessions/{sessionId}/guest-links/{linkId}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_guest_link(sessionId: str, linkId: str, user: UserRecord | None = Depends(get_optional_user)) -> None:
    service.revoke_guest_link(store, sessionId, user, linkId)
