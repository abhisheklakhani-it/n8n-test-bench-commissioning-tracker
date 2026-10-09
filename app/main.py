"""Application factory: wires database, middleware, routes and error pages."""

import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.db import Database
from app.seed import ensure_process, seed_demo
from app.web import routes_admin, routes_auth, routes_dashboards, routes_work
from app.web.deps import LoginRequired, current_session, render
from app.web.security import SecurityHeadersMiddleware

log = logging.getLogger("commissioning")


def create_app(database_url: str | None = None, demo_seed: bool | None = None) -> FastAPI:
    db = Database(database_url or settings.database_url)
    db.create_all()
    with db.SessionLocal() as s:
        if settings.demo_mode if demo_seed is None else demo_seed:
            seed_demo(s)
        else:
            ensure_process(s)

    app = FastAPI(title="Test Bench Commissioning", docs_url=None, redoc_url=None, openapi_url=None)
    app.state.db = db

    @app.middleware("http")
    async def db_session(request: Request, call_next):
        request.state.db = db.SessionLocal()
        try:
            return await call_next(request)
        finally:
            request.state.db.close()

    app.add_middleware(SecurityHeadersMiddleware)
    app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="static")
    for module in (routes_auth, routes_work, routes_dashboards, routes_admin):
        app.include_router(module.router)

    @app.exception_handler(LoginRequired)
    async def _login_required(request: Request, exc: LoginRequired):
        return RedirectResponse("/login", status_code=303)

    @app.exception_handler(HTTPException)
    async def _http_error(request: Request, exc: HTTPException):
        if exc.status_code in (301, 302, 303) and exc.headers:
            return RedirectResponse(exc.headers["Location"], status_code=303)
        sess = current_session(request)
        return render(request, "error.html", sess.user if sess else None, sess, status_code=exc.status_code, code=exc.status_code)

    @app.exception_handler(Exception)
    async def _server_error(request: Request, exc: Exception):
        log.exception("unhandled error on %s", request.url.path)  # details only in the server log
        return render(request, "error.html", None, None, status_code=500, code=500)

    return app
