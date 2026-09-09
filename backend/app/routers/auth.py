from __future__ import annotations

import os

from fastapi import APIRouter, Depends, Response, status

from .. import service
from ..deps import SESSION_COOKIE, get_optional_user, get_session_cookie
from ..models import SignInRequest, User
from ..store import UserRecord, store

router = APIRouter(tags=["auth"])

# Off by default so local dev/tests over plain HTTP work; set COOKIE_SECURE=true
# behind HTTPS in production so the cookie is never sent in the clear.
_COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "false").lower() == "true"


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        httponly=True,
        secure=_COOKIE_SECURE,
        samesite="lax",
        path="/",
    )


@router.get("/auth/me", response_model=User | None)
def get_current_user(user: UserRecord | None = Depends(get_optional_user)) -> User | None:
    return service.get_current_user_model(user)


@router.post("/auth/sign-in", response_model=User)
def sign_in(body: SignInRequest, response: Response) -> User:
    user, token = service.sign_in(store, body.email, body.password)
    _set_session_cookie(response, token)
    return user


@router.post("/auth/sign-out", status_code=status.HTTP_204_NO_CONTENT)
def sign_out(response: Response, token: str | None = Depends(get_session_cookie)) -> None:
    service.sign_out(store, token)
    response.delete_cookie(SESSION_COOKIE, path="/")
