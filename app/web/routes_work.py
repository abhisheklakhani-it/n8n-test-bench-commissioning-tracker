"""Daily work: my tasks, task page (instructions + form), inbox, test bench page."""

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import or_, select

from app.domain import process as P
from app.domain.roles import TECH, can, can_work_on
from app.models import Bench, Notification, StepTemplate, Task, User, utcnow
from app.services import notify, workflow
from app.services.workflow import WorkflowError
from app.web.deps import db_of, form_with_csrf, redirect, render, require, require_user
from app.web.routes_auth import home_for

router = APIRouter()


def _task_or_404(request: Request, task_id: int) -> Task:
    task = db_of(request).get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404)
    return task


@router.get("/")
def home(request: Request):
    user, _ = require_user(request)
    return redirect(home_for(user.role))


@router.get("/aufgaben")
def my_tasks(request: Request):
    user, sess = require(request, "view_my_tasks")
    db = db_of(request)
    workflow.check_overdue(db)
    q = select(Task).where(Task.status.in_(P.OPEN_STATUSES))
    if user.role == TECH:  # own discipline, assigned to me or still unassigned
        q = q.where(Task.discipline == user.discipline, or_(Task.assignee_id == user.id, Task.assignee_id.is_(None)))
    else:  # leads and the department lead see tasks assigned to them personally
        q = q.where(Task.assignee_id == user.id)
    tasks = list(db.scalars(q.order_by(Task.ready_at)))
    groups = {
        "problem": [t for t in tasks if t.status in (P.FAIL, P.BLOCKED)],
        "doing": [t for t in tasks if t.status == P.IN_PROGRESS],
        "ready": [t for t in tasks if t.status == P.READY],
    }
    upcoming = 0
    if user.discipline:
        upcoming = len(list(db.scalars(select(Task.id).where(Task.discipline == user.discipline, Task.status == P.WAITING))))
    return render(request, "my_tasks.html", user, sess, groups=groups, upcoming=upcoming, autorefresh=True)


@router.get("/aufgabe/{task_id}")
def task_page(request: Request, task_id: int):
    user, sess = require_user(request)
    db = db_of(request)
    task = _task_or_404(request, task_id)
    steps = {s.code: s for s in db.scalars(select(StepTemplate))}
    by_step = {t.step_code: t for t in task.bench.tasks}
    deps = {c: list(s.depends_on) for c, s in steps.items()}
    before = [by_step[c] for c in deps[task.step_code]]
    after = [by_step[c] for c in P.dependents(deps, task.step_code)]
    may_work = can(user.role, "work_on_task") and can_work_on(user.role, user.id, user.discipline, task.discipline, task.assignee_id)
    may_assign = can(user.role, "assign_task") and can_work_on(user.role, user.id, user.discipline, task.discipline, None)
    may_reopen = may_assign and P.can_reopen(deps, {t.step_code: t.status for t in task.bench.tasks}, task.step_code)
    team = []
    if may_assign:
        team = list(db.scalars(select(User).where(User.role == TECH, User.discipline == task.discipline, User.active.is_(True)).order_by(User.full_name)))
    now = utcnow()
    worked = P.working_seconds(task.started_at, task.finished_at, task.paused_seconds, task.paused_at, now)
    waited = P.waiting_seconds(task.ready_at, task.started_at, now)
    return render(request, "task.html", user, sess, task=task, before=before, after=after, may_work=may_work,
                  may_assign=may_assign, may_reopen=may_reopen, team=team,
                  worked=worked / 60 if worked is not None else None, waited=waited / 60 if waited is not None else None)


async def _task_action(request: Request, task_id: int, action):
    user, sess = require_user(request)
    form = await form_with_csrf(request, sess)
    db = db_of(request)
    task = _task_or_404(request, task_id)
    try:
        target = action(db, user, task, form)
    except WorkflowError as e:
        db.rollback()
        return redirect(f"/aufgabe/{task_id}?err={e.key}")
    return redirect(target)


@router.post("/aufgabe/{task_id}/start")
async def task_start(request: Request, task_id: int):
    def act(db, user, task, form):
        workflow.start_task(db, user, task)
        return f"/aufgabe/{task.id}?ok=ok_started"

    return await _task_action(request, task_id, act)


@router.post("/aufgabe/{task_id}/ergebnis")
async def task_result(request: Request, task_id: int):
    def act(db, user, task, form):
        checked = []
        for value in form.getlist("check"):
            try:
                checked.append(int(value))
            except ValueError:
                continue
        values = {k[2:]: str(v) for k, v in form.items() if k.startswith("v_")}
        workflow.submit_result(
            db, user, task, str(form.get("result", "")), str(form.get("comment", "")), str(form.get("measurement", "")), checked, values
        )
        return "/aufgaben?ok=ok_saved" if user.role == TECH else f"/aufgabe/{task.id}?ok=ok_saved"

    return await _task_action(request, task_id, act)


@router.post("/aufgabe/{task_id}/zuweisen")
async def task_assign(request: Request, task_id: int):
    def act(db, user, task, form):
        raw = str(form.get("assignee", ""))
        assignee = db.get(User, int(raw)) if raw.isdigit() else None
        if raw and assignee is None:
            raise WorkflowError("err_assignee")
        workflow.assign_task(db, user, task, assignee)
        return f"/aufgabe/{task.id}?ok=ok_assigned"

    return await _task_action(request, task_id, act)


@router.post("/aufgabe/{task_id}/wiedereroeffnen")
async def task_reopen(request: Request, task_id: int):
    def act(db, user, task, form):
        workflow.reopen_task(db, user, task)
        return f"/aufgabe/{task.id}?ok=ok_reopened"

    return await _task_action(request, task_id, act)


@router.get("/meldungen")
def inbox(request: Request):
    user, sess = require_user(request)
    db = db_of(request)
    workflow.check_overdue(db)
    return render(request, "inbox.html", user, sess, items=notify.inbox(db, user.id), autorefresh=True)


@router.post("/meldungen/gelesen")
async def inbox_mark_all(request: Request):
    user, sess = require_user(request)
    await form_with_csrf(request, sess)
    db = db_of(request)
    for n in db.scalars(select(Notification).where(Notification.user_id == user.id, Notification.read_at.is_(None))):
        n.read_at = utcnow()
    db.commit()
    return redirect("/meldungen")


@router.get("/meldung/{notification_id}")
def open_notification(request: Request, notification_id: int):
    """Click on a message -> mark it read -> go straight to the place where the work is done."""
    user, sess = require_user(request)
    db = db_of(request)
    n = db.get(Notification, notification_id)
    if n is None or n.user_id != user.id:
        raise HTTPException(status_code=404)
    if n.read_at is None:
        n.read_at = utcnow()
        db.commit()
    if n.task_id and sess.kind == "pin":  # shop-floor tablet: open the big one-task screen
        return redirect(f"/werker/aufgabe?id={n.task_id}")
    if n.task_id:
        return redirect(f"/aufgabe/{n.task_id}")
    if n.bench is not None:
        return redirect(f"/pruefstand/{n.bench.code}")
    return redirect("/meldungen")


@router.get("/pruefstand/{code}")
def bench_page(request: Request, code: str):
    user, sess = require_user(request)
    bench = db_of(request).scalar(select(Bench).where(Bench.code == code.upper()))
    if bench is None:
        raise HTTPException(status_code=404)
    return render(request, "bench.html", user, sess, bench=bench, pct=P.progress_pct(t.status for t in bench.tasks), autorefresh=True)
