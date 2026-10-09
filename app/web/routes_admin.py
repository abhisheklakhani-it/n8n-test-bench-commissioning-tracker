"""Administration for the department lead: notification rules, users, audit log."""

import re
import secrets

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import select

from app.config import settings
from app.domain import notifications as N
from app.domain.roles import ADMIN, DISCIPLINES, LEAD, ROLES, TECH
from app.models import AppSetting, AuditLog, NotificationRule, User
from app.services import audit
from app.services.auth import end_all_sessions, hash_password, password_problems
from app.web.deps import db_of, form_with_csrf, redirect, render, require
from app.web.routes_auth import DEMO_USERNAMES

router = APIRouter()
USERNAME_RE = re.compile(r"^[a-z0-9._-]{3,40}$")


@router.get("/regeln")
def rules_page(request: Request):
    user, sess = require(request, "manage_rules")
    db = db_of(request)
    rules = {r.event_type: r for r in db.scalars(select(NotificationRule))}
    hours = db.get(AppSetting, "overdue_hours")
    return render(request, "rules.html", user, sess, rules=[rules[e] for e in N.EVENT_TYPES if e in rules], hours=hours.value if hours else "4")


@router.post("/regeln")
async def rules_save(request: Request):
    user, sess = require(request, "manage_rules")
    form = await form_with_csrf(request, sess)
    db = db_of(request)
    changes = {}
    for rule in db.scalars(select(NotificationRule)):
        raw = str(form.get(f"{rule.event_type}.priority", rule.priority))
        priority = int(raw) if raw.isdigit() and int(raw) in N.PRIORITIES else rule.priority
        flags = {f: form.get(f"{rule.event_type}.{f}") == "on" for f in ("to_assignee", "to_team", "to_team_lead", "to_admin", "to_next_team")}
        before = (rule.priority, rule.to_assignee, rule.to_team, rule.to_team_lead, rule.to_admin, rule.to_next_team)
        rule.priority = priority
        for f, v in flags.items():
            setattr(rule, f, v)
        after = (rule.priority, rule.to_assignee, rule.to_team, rule.to_team_lead, rule.to_admin, rule.to_next_team)
        if before != after:
            changes[rule.event_type] = {"priority": priority, **flags}
    hours = str(form.get("overdue_hours", "4"))
    if hours.isdigit() and 1 <= int(hours) <= 72:
        setting = db.get(AppSetting, "overdue_hours")
        if setting.value != hours:
            changes["overdue_hours"] = int(hours)
            setting.value = hours
    if changes:
        audit.log(db, user, "rules_changed", changes=changes)
    db.commit()
    return redirect("/regeln?ok=ok_rules")


@router.post("/regeln/standard")
async def rules_reset(request: Request):
    user, sess = require(request, "manage_rules")
    await form_with_csrf(request, sess)
    db = db_of(request)
    for event_type, rule in N.DEFAULT_RULES.items():
        row = db.get(NotificationRule, event_type)
        for k, v in rule.__dict__.items():
            setattr(row, k, v)
    audit.log(db, user, "rules_reset")
    db.commit()
    return redirect("/regeln?ok=ok_rules")


@router.get("/benutzer")
def users_page(request: Request):
    user, sess = require(request, "manage_users")
    users = list(db_of(request).scalars(select(User).order_by(User.role, User.discipline, User.full_name)))
    return render(request, "users.html", user, sess, users=users, roles=ROLES, disciplines=DISCIPLINES, temp_password="")


@router.post("/benutzer")
async def users_create(request: Request):
    user, sess = require(request, "manage_users")
    form = await form_with_csrf(request, sess)
    db = db_of(request)
    username = str(form.get("username", "")).strip().lower()
    full_name = str(form.get("full_name", "")).strip()[:120]
    role = str(form.get("role", ""))
    discipline = str(form.get("discipline", "")) or None
    password = str(form.get("password", ""))
    if not USERNAME_RE.match(username) or not full_name:
        return redirect("/benutzer?err=err_user_input")
    if role not in ROLES or (role in (LEAD, TECH) and discipline not in DISCIPLINES):
        return redirect("/benutzer?err=err_user_role")
    if role == ADMIN:
        discipline = None
    if db.scalar(select(User).where(User.username == username)):
        return redirect("/benutzer?err=err_user_exists")
    problems = password_problems(password, username)
    if problems:
        return redirect(f"/benutzer?err={problems[0]}")
    db.add(User(username=username, full_name=full_name, role=role, discipline=discipline, password_hash=hash_password(password), must_change_password=True))
    audit.log(db, user, "user_created", username=username, role=role, discipline=discipline)
    db.commit()
    return redirect("/benutzer?ok=ok_user_created")


def _target(request: Request, user_id: int) -> User:
    target = db_of(request).get(User, user_id)
    if target is None:
        raise HTTPException(status_code=404)
    return target


@router.post("/benutzer/{user_id}/aktiv")
async def users_toggle(request: Request, user_id: int):
    user, sess = require(request, "manage_users")
    await form_with_csrf(request, sess)
    db = db_of(request)
    target = _target(request, user_id)
    if target.id == user.id:
        return redirect("/benutzer?err=err_self")
    if settings.demo_mode and target.username in DEMO_USERNAMES:
        return redirect("/benutzer?err=err_demo_protected")
    target.active = not target.active
    if not target.active:
        end_all_sessions(db, target.id)
    audit.log(db, user, "user_activated" if target.active else "user_deactivated", username=target.username)
    db.commit()
    return redirect("/benutzer?ok=ok_saved")


@router.post("/benutzer/{user_id}/passwort")
async def users_reset_password(request: Request, user_id: int):
    user, sess = require(request, "manage_users")
    await form_with_csrf(request, sess)
    db = db_of(request)
    target = _target(request, user_id)
    if settings.demo_mode and target.username in DEMO_USERNAMES:
        return redirect("/benutzer?err=err_demo_protected")
    temp = "Tmp-" + secrets.token_urlsafe(9) + "7"
    target.password_hash = hash_password(temp)
    target.must_change_password = True
    end_all_sessions(db, target.id)
    audit.log(db, user, "password_reset", username=target.username)
    db.commit()
    # shown exactly once to the admin, who hands it over personally
    return render(request, "users.html", user, sess, users=list(db.scalars(select(User).order_by(User.role, User.discipline, User.full_name))),
                  roles=ROLES, disciplines=DISCIPLINES, temp_password=temp, temp_for=target.username)


@router.get("/protokoll")
def audit_page(request: Request):
    user, sess = require(request, "view_audit")
    rows = list(db_of(request).scalars(select(AuditLog).order_by(AuditLog.id.desc()).limit(200)))
    return render(request, "audit.html", user, sess, rows=rows)
