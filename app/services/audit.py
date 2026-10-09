"""Append-only audit trail of decisions (who did what, when)."""

from sqlalchemy.orm import Session

from app.models import AuditLog, User


def log(db: Session, actor: User | None, action: str, **details) -> None:
    db.add(AuditLog(user_id=actor.id if actor else None, action=action, details=details))
