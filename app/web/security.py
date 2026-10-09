"""HTTP security headers for every response."""

from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings

CSP = (
    "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; "
    "connect-src 'self'; font-src 'self'; object-src 'none'; base-uri 'none'; "
    "form-action 'self'; frame-ancestors 'none'"
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        h = response.headers
        h["Content-Security-Policy"] = CSP
        h["X-Content-Type-Options"] = "nosniff"
        h["X-Frame-Options"] = "DENY"
        h["Referrer-Policy"] = "same-origin"
        h["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(), payment=()"
        h["Cross-Origin-Opener-Policy"] = "same-origin"
        if settings.cookie_secure:
            h["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        if request.url.path not in ("/static/app.css", "/static/app.js"):
            h["Cache-Control"] = "no-store"
        return response
