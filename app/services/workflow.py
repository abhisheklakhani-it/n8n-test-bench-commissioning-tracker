"""Use cases of the commissioning workflow. Every function checks permissions first,
changes state, emits notifications and writes the audit log in one transaction."""

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain import notifications as N
from app.domain import process as P
from app.domain.roles import TECH, can, can_work_on
from app.models import AppSetting, Bench, StepTemplate, Task, User, utcnow
from app.services import audit, notify


class WorkflowError(Exception):
    """Raised with an i18n key; shown to the user as a friendly message."""

    def __init__(self, key: str):
        super().__init__(key)
        self.key = key


def _deps(db: Session) -> dict[str, list[str]]:
    return {s.code: list(s.depends_on) for s in db.scalars(select(StepTemplate))}


def _statuses(bench: Bench) -> dict[str, str]:
    return {t.step_code: t.status for t in bench.tasks}


def _task_by_step(bench: Bench) -> dict[str, Task]:
    return {t.step_code: t for t in bench.tasks}


def _step_params(task: Task, **extra) -> dict:
    return {"bench": task.bench.code, "step": task.step_code, "name_de": task.step.name_de, "name_en": task.step.name_en, **extra}


def overdue_hours(db: Session) -> int:
    row = db.get(AppSetting, "overdue_hours")
    return int(row.value) if row else 4


def _require_task_access(actor: User, task: Task) -> None:
    if not can(actor.role, "work_on_task") or not can_work_on(actor.role, actor.id, actor.discipline, task.discipline, task.assignee_id):
        raise WorkflowError("err_not_allowed")


def create_bench(db: Session, actor: User, code: str, name: str, location: str = "") -> Bench:
    if not can(actor.role, "create_bench"):
        raise WorkflowError("err_not_allowed")
    code = code.strip().upper()
    if not code or len(code) > 20 or not all(c.isalnum() or c in "-_" for c in code):
        raise WorkflowError("err_bench_code")
    if db.scalar(select(Bench).where(Bench.code == code)):
        raise WorkflowError("err_bench_exists")
    deps = _deps(db)
    P.validate_dependencies(deps)
    bench = Bench(code=code, name=name.strip()[:120] or code, location=location.strip()[:80])
    db.add(bench)
    db.flush()
    now = utcnow()
    for step in db.scalars(select(StepTemplate).order_by(StepTemplate.position)):
        ready = step.code in P.initial_ready(deps)
        db.add(
            Task(
                bench_id=bench.id,
                step_code=step.code,
                position=step.position,
                discipline=step.discipline,
                status=P.READY if ready else P.WAITING,
                ready_at=now if ready else None,
            )
        )
    db.flush()
    db.refresh(bench)
    for task in bench.tasks:
        if task.status == P.READY:
            notify.emit(db, N.TASK_READY, task=task, actor_id=actor.id, params=_step_params(task))
    audit.log(db, actor, "bench_created", bench=code)
    db.commit()
    return bench


def start_task(db: Session, actor: User, task: Task) -> None:
    _require_task_access(actor, task)
    if task.status != P.READY:
        raise WorkflowError("err_wrong_state")
    task.status = P.IN_PROGRESS
    task.started_at = utcnow()
    if task.assignee_id is None:
        task.assignee_id = actor.id
    notify.resolve_for_task(db, task.id, (N.TASK_READY, N.TASK_ASSIGNED, N.TASK_OVERDUE))
    audit.log(db, actor, "task_started", bench=task.bench.code, step=task.step_code)
    db.commit()


def submit_result(db: Session, actor: User, task: Task, result: str, comment: str, measurement: str, checked: list[int]) -> None:
    _require_task_access(actor, task)
    if result not in P.RESULT_STATUSES:
        raise WorkflowError("err_result")
    if task.status not in (P.READY, P.IN_PROGRESS, P.FAIL, P.BLOCKED):
        raise WorkflowError("err_wrong_state")
    comment = comment.strip()[:2000]
    checklist_len = len(task.step.checklist_de)
    checked = sorted({i for i in checked if 0 <= i < checklist_len})
    if result == P.PASS and len(checked) != checklist_len:
        raise WorkflowError("err_checklist")
    if result in (P.FAIL, P.BLOCKED) and not comment:
        raise WorkflowError("err_comment_required")

    now = utcnow()
    if task.started_at is None:
        task.started_at = now
    if task.assignee_id is None:
        task.assignee_id = actor.id
    task.status = result
    task.comment = comment
    task.measurement = measurement.strip()[:200]
    task.checklist_done = checked
    task.finished_at = now if result == P.PASS else None
    db.flush()

    bench = task.bench
    deps = _deps(db)
    by_step = _task_by_step(bench)
    notify.resolve_for_task(db, task.id, (N.TASK_READY, N.TASK_ASSIGNED, N.TASK_OVERDUE, N.STEP_FAILED, N.STEP_BLOCKED))

    if result == P.PASS:
        notify.emit(db, N.STEP_PASSED, task=task, actor_id=actor.id, params=_step_params(task))
        for code in P.newly_ready(deps, _statuses(bench), task.step_code):
            nxt = by_step[code]
            nxt.status, nxt.ready_at, nxt.overdue_notified = P.READY, now, False
            db.flush()
            notify.emit(db, N.TASK_READY, task=nxt, actor_id=actor.id, params=_step_params(nxt, after=task.step_code))
        if P.is_released(_statuses(bench).values()) and bench.released_at is None:
            bench.released_at = now
            notify.emit(db, N.BENCH_RELEASED, bench_id=bench.id, actor_id=actor.id, params={"bench": bench.code})
    else:
        blocked = P.downstream(deps, task.step_code)
        event = N.STEP_FAILED if result == P.FAIL else N.STEP_BLOCKED
        params = _step_params(task, comment=comment, blocked=blocked)
        # The assignee rule must reach the *responsible* person even if they reported it themselves -> actor excluded in emit.
        notify.emit(db, event, task=task, actor_id=actor.id, params=params)
        next_tasks = [by_step[c] for c in P.dependents(deps, task.step_code)]
        notify.emit(db, N.DOWNSTREAM_DELAYED, task=task, actor_id=actor.id, next_tasks=next_tasks, params=params)
    audit.log(db, actor, "task_result", bench=bench.code, step=task.step_code, result=result)
    db.commit()


def assign_task(db: Session, actor: User, task: Task, assignee: User | None) -> None:
    if not can(actor.role, "assign_task") or not can_work_on(actor.role, actor.id, actor.discipline, task.discipline, None):
        raise WorkflowError("err_not_allowed")
    if task.status in (P.PASS,):
        raise WorkflowError("err_wrong_state")
    if assignee is not None and (not assignee.active or assignee.role != TECH or assignee.discipline != task.discipline):
        raise WorkflowError("err_assignee")
    task.assignee_id = assignee.id if assignee else None
    db.flush()
    if assignee is not None:
        notify.resolve_for_task(db, task.id, (N.TASK_READY, N.TASK_ASSIGNED))
        if task.status in (P.READY, P.IN_PROGRESS, P.FAIL, P.BLOCKED):
            notify.emit(db, N.TASK_ASSIGNED, task=task, actor_id=actor.id, params=_step_params(task))
    audit.log(db, actor, "task_assigned", bench=task.bench.code, step=task.step_code, assignee=assignee.username if assignee else None)
    db.commit()


def reopen_task(db: Session, actor: User, task: Task) -> None:
    if not can(actor.role, "reopen_task") or not can_work_on(actor.role, actor.id, actor.discipline, task.discipline, None):
        raise WorkflowError("err_not_allowed")
    bench = task.bench
    deps = _deps(db)
    if not P.can_reopen(deps, _statuses(bench), task.step_code):
        raise WorkflowError("err_reopen")
    by_step = _task_by_step(bench)
    for code in P.downstream(deps, task.step_code):
        t = by_step[code]
        if t.status == P.READY:
            t.status, t.ready_at = P.WAITING, None
            notify.resolve_for_task(db, t.id, (N.TASK_READY, N.TASK_ASSIGNED, N.TASK_OVERDUE))
    task.status, task.finished_at = P.IN_PROGRESS, None
    bench.released_at = None
    audit.log(db, actor, "task_reopened", bench=bench.code, step=task.step_code)
    db.commit()


def check_overdue(db: Session, now=None) -> int:
    """READY tasks nobody started within the configured hours -> escalate once."""
    now = now or utcnow()
    limit = now - timedelta(hours=overdue_hours(db))
    count = 0
    tasks = list(db.scalars(select(Task).where(Task.status == P.READY, Task.overdue_notified.is_(False), Task.ready_at < limit)))
    for task in tasks:
        task.overdue_notified = True
        count += notify.emit(
            db, N.TASK_OVERDUE, task=task, params=_step_params(task, hours=overdue_hours(db)), dedupe=f"overdue:{task.id}:{task.ready_at.isoformat()}"
        )
    if tasks:
        db.commit()
    return count
