"""Request helpers: current user, permission guard, CSRF check and page rendering."""

import hmac
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.config import settings
from app.domain.roles import can
from app.models import SessionToken, User
from app.services import notify
from app.services.auth import get_session
from app.web import i18n

COOKIE = "sid"
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))
_TZ = ZoneInfo(settings.timezone)


def _local(dt, fmt: str = "%d.%m. %H:%M") -> str:
    if dt is None:
        return "–"
    return dt.replace(tzinfo=ZoneInfo("UTC")).astimezone(_TZ).strftime(fmt)


def _mins(value) -> str:
    if value is None:
        return "–"
    hours, minutes = divmod(int(round(value)), 60)
    return f"{hours} h {minutes:02d} min" if hours else f"{minutes} min"


def _iso(dt) -> str:
    return dt.isoformat() + "Z" if dt else ""


templates.env.filters["local"] = _local
templates.env.filters["mins"] = _mins
templates.env.filters["iso"] = _iso


class LoginRequired(Exception):
    pass


def db_of(request: Request) -> Session:
    return request.state.db


def current_session(request: Request) -> SessionToken | None:
    return get_session(db_of(request), request.cookies.get(COOKIE))


def require_user(request: Request) -> tuple[User, SessionToken]:
    sess = current_session(request)
    if sess is None:
        raise LoginRequired()
    if sess.user.must_change_password and request.url.path not in ("/passwort", "/logout"):
        raise HTTPException(status_code=303, headers={"Location": "/passwort"})
    return sess.user, sess


def require(request: Request, action: str) -> tuple[User, SessionToken]:
    user, sess = require_user(request)
    if not can(user.role, action):
        raise HTTPException(status_code=403)
    return user, sess


async def form_with_csrf(request: Request, sess: SessionToken | None) -> dict:
    """Parses the form and verifies the CSRF token (constant-time compare)."""
    form = await request.form()
    token = str(form.get("csrf", ""))
    expected = sess.csrf_token if sess else request.cookies.get("login_csrf", "")
    if not expected or not hmac.compare_digest(token, expected):
        raise HTTPException(status_code=403, detail="csrf")
    return form


def redirect(url: str) -> RedirectResponse:
    return RedirectResponse(url, status_code=303)


def render(request: Request, name: str, user: User | None = None, sess: SessionToken | None = None, status_code: int = 200, **ctx):
    lang = user.lang if user else request.cookies.get("lang", "de")
    lang = lang if lang in i18n.LANGS else "de"
    db = db_of(request)
    base = {
        "request": request,
        "user": user,
        "csrf": sess.csrf_token if sess else ctx.pop("login_csrf", ""),
        "lang": lang,
        "t": i18n.translator(lang),
        "L": i18n,
        "demo": settings.demo_mode,
        "badge": notify.badge_count(db, user.id) if user else 0,
        "has_high": notify.has_open_high(db, user.id) if user else False,
        "ok": request.query_params.get("ok", ""),
        "err": request.query_params.get("err", ""),
        "path": request.url.path,
        "can": (lambda action: can(user.role, action)) if user else (lambda action: False),
    }
    base.update(ctx)
    return templates.TemplateResponse(request, name, base, status_code=status_code)
