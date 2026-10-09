"""Passwords (Argon2id), server-side sessions and login throttling."""

import hashlib
import secrets
from datetime import datetime, timedelta

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import LoginAttempt, SessionToken, User, utcnow

_hasher = PasswordHasher()  # Argon2id with library defaults
# Used to spend the same time when a user does not exist (no user enumeration by timing).
_DUMMY_HASH = _hasher.hash("not-a-real-password-" + secrets.token_hex(8))


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def password_problems(password: str, username: str = "") -> list[str]:
    """Returns i18n keys of violated rules (empty list = OK)."""
    problems = []
    if len(password) < 12:
        problems.append("pw_rule_length")
    if not any(c.isalpha() for c in password) or not any(c.isdigit() for c in password):
        problems.append("pw_rule_mix")
    if username and username.lower() in password.lower():
        problems.append("pw_rule_username")
    return problems


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def create_session(db: Session, user: User) -> str:
    token = secrets.token_urlsafe(32)
    db.add(SessionToken(token_hash=_sha256(token), csrf_token=secrets.token_urlsafe(32), user_id=user.id))
    db.commit()
    return token


def get_session(db: Session, token: str | None) -> SessionToken | None:
    if not token:
        return None
    sess = db.scalar(select(SessionToken).where(SessionToken.token_hash == _sha256(token)))
    if sess is None:
        return None
    now = utcnow()
    expired = now - sess.last_seen > timedelta(minutes=settings.session_idle_minutes) or now - sess.created_at > timedelta(
        hours=settings.session_max_hours
    )
    if expired or not sess.user.active:
        db.delete(sess)
        db.commit()
        return None
    if now - sess.last_seen > timedelta(seconds=60):
        sess.last_seen = now
        db.commit()
    return sess


def end_session(db: Session, token: str | None) -> None:
    if token:
        db.execute(delete(SessionToken).where(SessionToken.token_hash == _sha256(token)))
        db.commit()


def end_all_sessions(db: Session, user_id: int) -> None:
    db.execute(delete(SessionToken).where(SessionToken.user_id == user_id))


def is_locked(db: Session, keys: list[str], now: datetime | None = None) -> bool:
    since = (now or utcnow()) - timedelta(minutes=settings.login_lock_minutes)
    for key in keys:
        n = db.scalar(select(func.count()).select_from(LoginAttempt).where(LoginAttempt.key == key, LoginAttempt.at >= since))
        if n >= settings.login_max_failures:
            return True
    return False


def record_failure(db: Session, keys: list[str]) -> None:
    for key in keys:
        db.add(LoginAttempt(key=key))
    db.commit()


def clear_failures(db: Session, key: str) -> None:
    db.execute(delete(LoginAttempt).where(LoginAttempt.key == key))
    db.commit()


def authenticate(db: Session, username: str, password: str, ip: str) -> tuple[User | None, str]:
    """Returns (user, error_key). Same generic error for unknown user and wrong password."""
    username = username.strip().lower()[:80]
    keys = [f"user:{username}", f"ip:{ip}"]
    if is_locked(db, keys):
        return None, "login_locked"
    user = db.scalar(select(User).where(User.username == username))
    if user is None or not user.active:
        verify_password(_DUMMY_HASH, password)
        record_failure(db, keys)
        return None, "login_failed"
    if not verify_password(user.password_hash, password):
        record_failure(db, keys)
        return None, "login_failed"
    clear_failures(db, keys[0])
    return user, ""
