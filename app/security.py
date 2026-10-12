"""Password hashing, server-backed sessions, and CSRF helpers."""

from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import secrets

import bcrypt
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models.admin import AdminUser, AuthSession

settings = get_settings()


def hash_password(password: str) -> str:
    """Hash an administrator password with bcrypt; never store plaintext."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Safely compare a supplied password with its bcrypt hash."""
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def bootstrap_admin(username: str, password: str, db: Session) -> AdminUser:
    """Create the one initial admin account; refuse duplicate setup."""
    if not username or not password:
        raise ValueError("Administrator username and password are required")
    if len(password.encode("utf-8")) > 72:
        raise ValueError("Administrator password must be at most 72 UTF-8 bytes")
    if db.scalar(select(AdminUser.id).limit(1)) is not None:
        raise ValueError("An administrator account already exists")
    admin = AdminUser(username=username, password_hash=hash_password(password))
    db.add(admin)
    db.commit()
    db.refresh(admin)
    return admin


def authenticate_admin(username: str, password: str, db: Session) -> AdminUser | None:
    """Return the administrator on valid credentials without revealing which field failed."""
    admin = db.scalar(select(AdminUser).where(AdminUser.username == username))
    if admin is None or not verify_password(password, admin.password_hash):
        return None
    return admin


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_authenticated_session(admin: AdminUser, request: Request, db: Session) -> None:
    """Create an opaque server-backed session and store only its token in the signed cookie."""
    token = secrets.token_urlsafe(32)
    csrf_token = secrets.token_urlsafe(32)
    auth_session = AuthSession(
        admin_user_id=admin.id,
        token_hash=_token_hash(token),
        expires_at=datetime.now(timezone.utc) + timedelta(seconds=settings.session_max_age_seconds),
    )
    db.add(auth_session)
    db.commit()
    request.session.clear()
    request.session.update({"session_token": token, "csrf_token": csrf_token})


def get_current_admin(request: Request, db: Session) -> AdminUser:
    """Resolve the signed-cookie token to a valid server-side session."""
    session_data = request.scope.get("session", {})
    token = session_data.get("session_token")
    if not isinstance(token, str):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    auth_session = db.scalar(select(AuthSession).where(AuthSession.token_hash == _token_hash(token)))
    if auth_session is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    expires_at = auth_session.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= datetime.now(timezone.utc):
        db.delete(auth_session)
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    admin = db.get(AdminUser, auth_session.admin_user_id)
    if admin is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    return admin


def require_admin(request: Request, db: Session = Depends(get_db)) -> AdminUser:
    """FastAPI dependency applied to all business APIs."""
    return get_current_admin(request, db)


def verify_csrf_token(request: Request, submitted_token: str | None) -> None:
    expected_token = request.scope.get("session", {}).get("csrf_token")
    if not isinstance(expected_token, str) or not isinstance(submitted_token, str):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid CSRF token")
    if not hmac.compare_digest(expected_token, submitted_token):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid CSRF token")


def verify_csrf(request: Request) -> None:
    """Require a session-bound CSRF token for unsafe API methods."""
    if request.method not in {"POST", "PUT", "PATCH", "DELETE"}:
        return
    verify_csrf_token(request, request.headers.get("x-csrf-token"))


def logout_session(request: Request, db: Session) -> None:
    """Delete the persistent session record and clear the browser cookie data."""
    token = request.scope.get("session", {}).get("session_token")
    if isinstance(token, str):
        auth_session = db.scalar(select(AuthSession).where(AuthSession.token_hash == _token_hash(token)))
        if auth_session is not None:
            db.delete(auth_session)
            db.commit()
    request.session.clear()
