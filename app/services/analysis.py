"""Process analysis workbook: entries are never overwritten without history and never hard-deleted."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain import analysis as A
from app.domain.roles import can
from app.models import AnalysisEntry, AnalysisRevision, User, utcnow


class AnalysisError(Exception):
    def __init__(self, key: str):
        super().__init__(key)
        self.key = key


def _require(actor: User) -> None:
    if not can(actor.role, "use_analysis"):
        raise AnalysisError("err_not_allowed")


def entries(db: Session, section: str, archived: bool = False) -> list[AnalysisEntry]:
    q = select(AnalysisEntry).where(AnalysisEntry.section == section, AnalysisEntry.archived.is_(archived))
    return list(db.scalars(q.order_by(AnalysisEntry.position, AnalysisEntry.id)))


def single(db: Session, section: str) -> AnalysisEntry | None:
    rows = entries(db, section)
    return rows[0] if rows else None


def save(db: Session, actor: User, section: str, form: dict, entry_id: int | None = None) -> AnalysisEntry:
    _require(actor)
    if section not in A.SECTIONS:
        raise AnalysisError("err_not_found")
    data, missing = A.clean(section, form)
    if missing:
        raise AnalysisError("err_required")
    now = utcnow()
    if entry_id is None and A.SECTIONS[section]["single"]:
        existing = single(db, section)
        entry_id = existing.id if existing else None
    if entry_id is None:
        position = len(entries(db, section)) + 1
        entry = AnalysisEntry(section=section, data=data, position=position, created_by=actor.id, updated_by=actor.id, created_at=now, updated_at=now)
        db.add(entry)
        db.flush()
        db.add(AnalysisRevision(entry_id=entry.id, action="created", data=data, user_id=actor.id, at=now))
    else:
        entry = db.get(AnalysisEntry, entry_id)
        if entry is None or entry.section != section:
            raise AnalysisError("err_not_found")
        if entry.data == data:
            return entry
        entry.data, entry.updated_at, entry.updated_by = data, now, actor.id
        db.add(AnalysisRevision(entry_id=entry.id, action="updated", data=data, user_id=actor.id, at=now))
    db.commit()
    return entry


def set_archived(db: Session, actor: User, entry_id: int, archived: bool) -> AnalysisEntry:
    _require(actor)
    entry = db.get(AnalysisEntry, entry_id)
    if entry is None:
        raise AnalysisError("err_not_found")
    entry.archived = archived
    entry.updated_at, entry.updated_by = utcnow(), actor.id
    db.add(AnalysisRevision(entry_id=entry.id, action="archived" if archived else "restored", data=entry.data, user_id=actor.id))
    db.commit()
    return entry


def export(db: Session, actor: User) -> dict:
    """Complete backup of the workbook including archived entries and every revision."""
    _require(actor)
    rows = list(db.scalars(select(AnalysisEntry).order_by(AnalysisEntry.section, AnalysisEntry.position, AnalysisEntry.id)))
    return {
        "exported_at": utcnow().isoformat() + "Z",
        "entries": [
            {
                "id": e.id,
                "section": e.section,
                "archived": e.archived,
                "data": e.data,
                "created_at": e.created_at.isoformat(),
                "updated_at": e.updated_at.isoformat(),
                "revisions": [{"action": r.action, "at": r.at.isoformat(), "data": r.data} for r in e.revisions],
            }
            for e in rows
        ],
    }
