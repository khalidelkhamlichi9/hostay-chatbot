"""Admin password verification (bcrypt in prod) and CSRF helpers."""

import secrets
from typing import Optional

from fastapi import HTTPException, Request
from passlib.context import CryptContext

from config import Settings, get_settings

_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")

CSRF_COOKIE_ADMIN = "admin_csrf"
CSRF_COOKIE_LOGIN = "login_csrf"


def verify_admin_password(plain: str, settings: Optional[Settings] = None) -> bool:
    settings = settings or get_settings()
    if settings.admin_pass_hash:
        try:
            return _pwd.verify(plain, settings.admin_pass_hash)
        except (ValueError, TypeError):
            return False
    if settings.admin_pass:
        return secrets.compare_digest(plain.encode("utf-8"), settings.admin_pass.encode("utf-8"))
    return False


def ensure_admin_csrf(request: Request) -> str:
    """Return CSRF token for admin session; flag response to set cookie if new."""
    token = request.cookies.get(CSRF_COOKIE_ADMIN)
    if not token:
        token = secrets.token_urlsafe(32)
        request.state.admin_set_csrf_cookie = True
    else:
        request.state.admin_set_csrf_cookie = False
    request.state.admin_csrf_token = token
    return token


def verify_admin_csrf(request: Request, submitted: str | None) -> None:
    expected = request.cookies.get(CSRF_COOKIE_ADMIN)
    if not submitted or not expected or not secrets.compare_digest(submitted, expected):
        raise HTTPException(status_code=403, detail="CSRF validation failed")


def new_login_csrf() -> str:
    return secrets.token_urlsafe(32)


def verify_login_csrf(request: Request, submitted: str | None) -> None:
    expected = request.cookies.get(CSRF_COOKIE_LOGIN)
    if not submitted or not expected or not secrets.compare_digest(submitted, expected):
        raise HTTPException(status_code=403, detail="CSRF validation failed (login)")
