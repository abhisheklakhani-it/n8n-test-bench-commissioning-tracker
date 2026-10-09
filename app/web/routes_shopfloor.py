"""Shop-floor mode for technicians: tap your name, enter a PIN, see exactly one task."""

import secrets

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import select

from app.config import settings
from app.domain import process as P
from app.domain.roles import DISCIPLINES, TECH
from app.models import Bench, Task, User, utcnow
from app.seed import DEMO_PIN
from app.services import workflow
from app.services.auth import authenticate_pin, create_session, end_session
from app.services.workflow import WorkflowError
from app.web.deps import COOKIE, current_session, db_of, form_with_csrf, redirect, render, require
from app.web.routes_auth import safe_next

router = APIRouter(prefix="/werker")


def _next(request: Request) -> str:
    value = safe_next(request.query_params.get("next", ""), "")
    return value if value.startswith("/werker/") else ""


def _with_login_csrf(resp, token: str):
    resp.set_cookie("login_csrf", token, httponly=True, samesite="strict", secure=settings.cookie_secure, max_age=3600)
    return resp


@router.get("")
def tiles(request: Request):
    sess = current_session(request)
    if sess and sess.user.role == TECH:
        return redirect(_next(request) or "/werker/aufgabe")
    workers = list(db_of(request).scalars(select(User).where(User.role == TECH, User.active.is_(True), User.pin_hash.is_not(None)).order_by(User.full_name)))
    groups = [(d, [w for w in workers if w.discipline == d]) for d in DISCIPLINES]
    return render(request, "shop_tiles.html", groups=[g for g in groups if g[1]], next=_next(request), shop=True)


@router.get("/pin/{user_id}")
def pin_form(request: Request, user_id: int):
    worker = db_of(request).get(User, user_id)
    if worker is None or worker.role != TECH or not worker.active:
        raise HTTPException(status_code=404)
    token = secrets.token_urlsafe(32)
    resp = render(request, "shop_pin.html", worker=worker, login_csrf=token, next=_next(request), error=request.query_params.get("e", ""),
                  demo_pin=DEMO_PIN if settings.demo_mode else "", shop=True)
    return _with_login_csrf(resp, token)


@router.post("/pin/{user_id}")
async def pin_login(request: Request, user_id: int):
    form = await form_with_csrf(request, None)
    db = db_of(request)
    worker = db.get(User, user_id)
    ip = request.client.host if request.client else "unknown"
    error = authenticate_pin(db, worker, str(form.get("pin", ""))[:12], ip)
    nxt = safe_next(str(form.get("next", "")), "")
    nxt = nxt if nxt.startswith("/werker/") else ""
    if error:
        return redirect(f"/werker/pin/{user_id}?e={error}" + (f"&next={nxt}" if nxt else ""))
    end_session(db, request.cookies.get(COOKIE))
    token = create_session(db, worker, kind="pin")
    resp = redirect(nxt or "/werker/aufgabe")
    resp.set_cookie(COOKIE, token, httponly=True, samesite="lax", secure=settings.cookie_secure, max_age=settings.session_max_hours * 3600)
    resp.delete_cookie("login_csrf")
    return resp


@router.post("/abmelden")
async def shop_logout(request: Request):
    sess = current_session(request)
    await form_with_csrf(request, sess)
    end_session(db_of(request), request.cookies.get(COOKIE))
    resp = redirect("/werker")
    resp.delete_cookie(COOKIE)
    return resp


@router.get("/aufgabe")
def task_screen(request: Request):
    user, sess = require(request, "use_shopfloor")
    db = db_of(request)
    workflow.check_overdue(db)
    tasks = workflow.open_tasks_for(db, user)
    wanted = request.query_params.get("id", "")
    current = next((t for t in tasks if str(t.id) == wanted), tasks[0] if tasks else None)
    now = utcnow()
    worked = P.working_seconds(current.started_at, current.finished_at, current.paused_seconds, current.paused_at, now) if current else None
    others = [t for t in tasks if t is not current]
    return render(request, "shop_task.html", user, sess, task=current, others=others, worked=worked, new=request.query_params.get("neu") == "1",
                  open_count=len(tasks), shop=True, autorefresh=current is None or current.status == P.READY)


@router.get("/pruefstand/{code}")
def bench_qr(request: Request, code: str):
    """Target of the QR code on the test bench: opens my task for this bench."""
    sess = current_session(request)
    if sess is None or sess.user.role != TECH:
        return redirect(f"/werker?next=/werker/pruefstand/{code.upper()[:20]}")
    db = db_of(request)
    bench = db.scalar(select(Bench).where(Bench.code == code.upper()[:20]))
    task = next((t for t in workflow.open_tasks_for(db, sess.user) if bench and t.bench_id == bench.id), None)
    return redirect(f"/werker/aufgabe?id={task.id}" if task else "/werker/aufgabe?err=err_no_task_bench")


def _task(request: Request, task_id: int) -> Task:
    task = db_of(request).get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404)
    return task


@router.post("/aufgabe/{task_id}/{action}")
async def task_action(request: Request, task_id: int, action: str):
    user, sess = require(request, "use_shopfloor")
    form = await form_with_csrf(request, sess)
    db = db_of(request)
    task = _task(request, task_id)
    back = f"/werker/aufgabe?id={task_id}"
    try:
        if action == "start":
            workflow.start_task(db, user, task)
            return redirect(back + "&ok=ok_started")
        if action == "pause":
            workflow.pause_task(db, user, task)
            return redirect(back)
        if action == "weiter":
            workflow.resume_task(db, user, task)
            return redirect(back)
        if action == "hilfe":
            workflow.request_help(db, user, task)
            return redirect(back + "&ok=ok_help")
        if action == "ergebnis":
            checked = [int(v) for v in form.getlist("check") if str(v).isdigit()]
            values = {k[2:]: str(v) for k, v in form.items() if k.startswith("v_")}
            workflow.submit_result(db, user, task, str(form.get("result", "")), str(form.get("comment", "")), "", checked, values)
            return redirect("/werker/aufgabe?ok=ok_saved")
    except WorkflowError as e:
        db.rollback()
        return redirect(back + f"&err={e.key}")
    raise HTTPException(status_code=404)
