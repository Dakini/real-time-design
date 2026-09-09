from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from .. import service
from ..database import get_db
from ..db_models import UserRow
from ..deps import get_optional_user
from ..models import CreateGuestLinkRequest, GuestLink

router = APIRouter(tags=["guest-links"])


@router.get("/sessions/{sessionId}/guest-links", response_model=list[GuestLink])
def list_guest_links(
    sessionId: str, user: UserRow | None = Depends(get_optional_user), db: Session = Depends(get_db)
) -> list[GuestLink]:
    return service.list_guest_links(db, sessionId, user)


@router.post("/sessions/{sessionId}/guest-links", response_model=GuestLink, status_code=201)
def create_guest_link(
    sessionId: str,
    body: CreateGuestLinkRequest | None = None,
    user: UserRow | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
) -> GuestLink:
    role = body.role if body is not None else CreateGuestLinkRequest().role
    return service.create_guest_link(db, sessionId, user, role)


@router.delete("/sessions/{sessionId}/guest-links/{linkId}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_guest_link(
    sessionId: str, linkId: str, user: UserRow | None = Depends(get_optional_user), db: Session = Depends(get_db)
) -> None:
    service.revoke_guest_link(db, sessionId, user, linkId)
