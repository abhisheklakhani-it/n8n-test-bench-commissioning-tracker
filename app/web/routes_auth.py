"""Sign-in, sign-out, password change and language switch."""

import secrets

from fastapi import APIRouter, Request

from app.config import settings
from app.domain.roles import ADMIN, LEAD
from app.seed import DEMO_USERS
from app.services import audit
from app.services.auth import authenticate, create_session, end_all_sessions, end_session, hash_password, password_problems, verify_password
from app.web.deps import COOKIE, current_session, db_of, form_with_csrf, redirect, render, require_user

router = APIRouter()
DEMO_USERNAMES = {u[0] for u in DEMO_USERS}


def home_for(role: str) -> str:
    return {ADMIN: "/leitung", LEAD: "/team"}.get(role, "/aufgaben")


def safe_next(value: str, fallback: str = "/") -> str:
    """Only local paths (prevents open redirects)."""
    return value if value.startswith("/") and not value.startswith("//") and "\\" not in value else fallback


def _login_page(request: Request, error: str = "", status_code: int = 200):
    token = secrets.token_urlsafe(32)
    demo_accounts = [u for u in DEMO_USERS if u[0] in ("leitung", "tl.elektrik", "tech.elektrik", "tech.software", "tech.pruefung")]
    resp = render(request, "login.html", login_csrf=token, error=error, demo_accounts=demo_accounts,
                  demo_password=settings.demo_password if settings.demo_mode else "", status_code=status_code)
    resp.set_cookie("login_csrf", token, httponly=True, samesite="strict", secure=settings.cookie_secure, max_age=3600)
    return resp


@router.get("/login")
def login_form(request: Request):
    sess = current_session(request)
    if sess:
        return redirect(home_for(sess.user.role))
    return _login_page(request)


@router.post("/login")
async def login(request: Request):
    form = await form_with_csrf(request, None)
    db = db_of(request)
    ip = request.client.host if request.client else "unknown"
    user, error = authenticate(db, str(form.get("username", "")), str(form.get("password", "")), ip)
    if user is None:
        return _login_page(request, error, status_code=401)
    end_session(db, request.cookies.get(COOKIE))
    token = create_session(db, user)
    audit.log(db, user, "login")
    db.commit()
    resp = redirect("/passwort" if user.must_change_password else home_for(user.role))
    resp.set_cookie(COOKIE, token, httponly=True, samesite="lax", secure=settings.cookie_secure, max_age=settings.session_max_hours * 3600)
    resp.delete_cookie("login_csrf")
    return resp


@router.post("/logout")
async def logout(request: Request):
    sess = current_session(request)
    await form_with_csrf(request, sess)
    end_session(db_of(request), request.cookies.get(COOKIE))
    resp = redirect("/login")
    resp.delete_cookie(COOKIE)
    return resp


@router.get("/passwort")
def password_form(request: Request):
    user, sess = require_user(request)
    return render(request, "password.html", user, sess)


@router.post("/passwort")
async def password_change(request: Request):
    user, sess = require_user(request)
    form = await form_with_csrf(request, sess)
    db = db_of(request)
    if settings.demo_mode and user.username in DEMO_USERNAMES:
        return redirect("/passwort?err=err_demo_protected")
    current, new, repeat = (str(form.get(k, "")) for k in ("current", "new", "repeat"))
    if not verify_password(user.password_hash, current):
        return redirect("/passwort?err=err_pw_current")
    if new != repeat:
        return redirect("/passwort?err=err_pw_repeat")
    problems = password_problems(new, user.username)
    if problems:
        return redirect(f"/passwort?err={problems[0]}")
    user.password_hash = hash_password(new)
    user.must_change_password = False
    end_all_sessions(db, user.id)
    audit.log(db, user, "password_changed")
    db.commit()
    token = create_session(db, user)
    resp = redirect(home_for(user.role) + "?ok=ok_password")
    resp.set_cookie(COOKIE, token, httponly=True, samesite="lax", secure=settings.cookie_secure, max_age=settings.session_max_hours * 3600)
    return resp


@router.post("/sprache")
async def switch_language(request: Request):
    user, sess = require_user(request)
    form = await form_with_csrf(request, sess)
    user.lang = "en" if user.lang == "de" else "de"
    db_of(request).commit()
    return redirect(safe_next(str(form.get("next", "/"))))
