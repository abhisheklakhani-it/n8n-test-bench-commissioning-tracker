"""Team leads maintain what workers see and answer for the steps of their own team."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain import process as P
from app.domain.roles import ADMIN, LEAD, can
from app.models import StepRevision, StepTemplate, User, utcnow
from app.services import audit
from app.services.workflow import WorkflowError


def can_edit(actor: User, step: StepTemplate) -> bool:
    return can(actor.role, "edit_steps") and (actor.role == ADMIN or (actor.role == LEAD and actor.discipline == step.discipline))


def all_steps(db: Session) -> list[StepTemplate]:
    return list(db.scalars(select(StepTemplate).order_by(StepTemplate.position)))


def history(db: Session, code: str) -> list[StepRevision]:
    return list(db.scalars(select(StepRevision).where(StepRevision.step_code == code).order_by(StepRevision.version.desc())))


def update_step(db: Session, actor: User, step: StepTemplate, form) -> bool:
    """Saves a new version. Running tasks keep their snapshot; only tasks not yet started use the new version.
    Returns False if nothing changed."""
    if not can_edit(actor, step):
        raise WorkflowError("err_not_allowed")
    spec, errors = P.parse_step_spec(form, step.measurements or [])
    if errors:
        raise WorkflowError(errors[0])
    current = step.to_spec()
    current.pop("version")
    if current == spec:
        return False
    if not history(db, step.code):  # keep the original definition as version 1
        db.add(StepRevision(step_code=step.code, version=step.version, data=current, user_id=None, at=step.updated_at or utcnow()))
    step.instructions_de, step.instructions_en = spec["instructions_de"], spec["instructions_en"]
    step.checklist_de, step.checklist_en = spec["checklist_de"], spec["checklist_en"]
    step.measurements = spec["measurements"]
    step.version += 1
    step.updated_at = utcnow()
    db.add(StepRevision(step_code=step.code, version=step.version, data=spec, user_id=actor.id))
    audit.log(db, actor, "step_changed", step=step.code, version=step.version)
    db.commit()
    return True
