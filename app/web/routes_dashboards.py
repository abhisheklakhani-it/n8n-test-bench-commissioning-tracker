"""Dashboards: central (department lead), team (per discipline) and the polling endpoint."""

from datetime import timedelta

import segno
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy import func, select

from app.config import settings
from app.domain import process as P
from app.domain.roles import ADMIN, DISCIPLINES, TECH
from app.models import AuditLog, Bench, Notification, StepTemplate, Task, User, utcnow
from app.seed import reset_demo_work
from app.services import audit, metrics, notify, workflow
from app.services.workflow import WorkflowError
from app.web.deps import current_session, db_of, form_with_csrf, redirect, render, require

router = APIRouter()


def _overdue_limit(db):
    return utcnow() - timedelta(hours=workflow.overdue_hours(db))


@router.get("/team")
def team_dashboard(request: Request):
    user, sess = require(request, "view_team_dashboard")
    db = db_of(request)
    workflow.check_overdue(db)
    discipline = user.discipline
    if user.role == ADMIN:
        requested = request.query_params.get("d", "ELEC")
        discipline = requested if requested in DISCIPLINES else "ELEC"
    if discipline is None:
        raise HTTPException(status_code=403)
    tasks = list(db.scalars(select(Task).where(Task.discipline == discipline).order_by(Task.ready_at)))
    members = list(db.scalars(select(User).where(User.role == TECH, User.discipline == discipline, User.active.is_(True)).order_by(User.full_name)))
    load = {m.id: sum(1 for t in tasks if t.assignee_id == m.id and t.status in P.OPEN_STATUSES) for m in members}
    limit = _overdue_limit(db)
    groups = {
        "problem": [t for t in tasks if t.status in (P.FAIL, P.BLOCKED)],
        "ready": [t for t in tasks if t.status == P.READY],
        "doing": [t for t in tasks if t.status == P.IN_PROGRESS],
        "waiting": [t for t in tasks if t.status == P.WAITING],
        "done": sorted([t for t in tasks if t.status == P.PASS], key=lambda t: t.finished_at, reverse=True)[:8],
    }
    return render(request, "team.html", user, sess, discipline=discipline, groups=groups, members=members, load=load,
                  overdue_limit=limit, disciplines=DISCIPLINES, autorefresh=True)


@router.get("/leitung")
def central_dashboard(request: Request):
    user, sess = require(request, "view_central_dashboard")
    db = db_of(request)
    workflow.check_overdue(db)
    benches = list(db.scalars(select(Bench).order_by(Bench.code)))
    steps = list(db.scalars(select(StepTemplate).order_by(StepTemplate.position)))
    all_tasks = [t for b in benches for t in b.tasks]
    limit = _overdue_limit(db)
    released = [b for b in benches if b.released_at]
    lead_days = [(b.released_at - b.created_at).total_seconds() / 86400 for b in released]
    kpi = {
        "benches": len(benches),
        "active": len(benches) - len(released),
        "released": len(released),
        "problems": sum(1 for t in all_tasks if t.status in (P.FAIL, P.BLOCKED)),
        "overdue": sum(1 for t in all_tasks if t.status == P.READY and t.ready_at and t.ready_at < limit),
        "lead_days": round(sum(lead_days) / len(lead_days), 1) if lead_days else None,
    }
    per_discipline = {
        d: {s: sum(1 for t in all_tasks if t.discipline == d and t.status == s) for s in (P.READY, P.IN_PROGRESS, P.FAIL, P.BLOCKED)}
        for d in DISCIPLINES
    }
    problems = [t for t in all_tasks if t.status in (P.FAIL, P.BLOCKED)]
    work_actions = ["task_result", "task_started", "bench_created", "task_assigned"]
    activity = list(db.scalars(select(AuditLog).where(AuditLog.action.in_(work_actions)).order_by(AuditLog.id.desc()).limit(12)))
    return render(request, "boss.html", user, sess, benches=benches, steps=steps, kpi=kpi, per_discipline=per_discipline,
                  problems=problems, activity=activity, progress=lambda b: P.progress_pct(t.status for t in b.tasks), autorefresh=True)


@router.post("/pruefstaende")
async def create_bench(request: Request):
    user, sess = require(request, "create_bench")
    form = await form_with_csrf(request, sess)
    db = db_of(request)
    try:
        bench = workflow.create_bench(db, user, str(form.get("code", "")), str(form.get("name", "")), str(form.get("location", "")))
    except WorkflowError as e:
        db.rollback()
        return redirect(f"/leitung?err={e.key}")
    return redirect(f"/pruefstand/{bench.code}?ok=ok_bench_created")


@router.get("/api/status")
def status(request: Request):
    """Polled by the browser every few seconds: bell badge + a version to refresh dashboards."""
    sess = current_session(request)
    if sess is None:
        return JSONResponse({"auth": False}, status_code=401)
    db = db_of(request)
    version = f"{db.scalar(select(func.max(AuditLog.id))) or 0}-{db.scalar(select(func.max(Notification.id))) or 0}"
    open_tasks = len(workflow.open_tasks_for(db, sess.user)) if sess.user.role == TECH else 0
    return {"auth": True, "badge": notify.badge_count(db, sess.user_id), "high": notify.has_open_high(db, sess.user_id), "v": version, "open": open_tasks}


@router.get("/healthz")
def healthz(request: Request):
    db_of(request).scalar(select(1))
    return {"status": "ok"}


@router.get("/kennzahlen")
def kpi_page(request: Request):
    """Measured waiting and working times per step: the live input for the value stream analysis."""
    user, sess = require(request, "view_kpis")
    db = db_of(request)
    rows = metrics.step_times(db)
    return render(request, "kpi.html", user, sess, rows=rows, total=metrics.totals(rows), leads=metrics.bench_lead_times(db))


@router.get("/qr")
def qr_codes(request: Request):
    """Printable QR codes: one per test bench, opens the worker's task for that bench."""
    user, sess = require(request, "print_qr")
    base = str(request.base_url).rstrip("/")
    codes = []
    for bench in db_of(request).scalars(select(Bench).order_by(Bench.code)):
        url = f"{base}/werker/pruefstand/{bench.code}"
        codes.append((bench, url, segno.make(url, error="m").svg_inline(scale=5, dark="#14213d")))
    login_url = f"{base}/werker"
    return render(request, "qr.html", user, sess, codes=codes, login_url=login_url,
                  login_svg=segno.make(login_url, error="m").svg_inline(scale=5, dark="#14213d"))


@router.post("/demo/zuruecksetzen")
async def demo_reset(request: Request):
    user, sess = require(request, "reset_demo")
    await form_with_csrf(request, sess)
    if not settings.demo_mode:
        raise HTTPException(status_code=403)
    db = db_of(request)
    reset_demo_work(db)
    audit.log(db, user, "demo_reset")
    db.commit()
    return redirect("/leitung?ok=ok_demo_reset")
