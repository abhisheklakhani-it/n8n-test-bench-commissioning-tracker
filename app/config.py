"""Application settings, read once from environment variables."""

import os
from dataclasses import dataclass


def _bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    return default if value is None else value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./data/app.db")
    # Secure cookies need HTTPS. Keep False only for local http://localhost development.
    cookie_secure: bool = _bool("COOKIE_SECURE", False)
    # Demo mode: fictional seed data, demo banner, demo accounts shown on the login page.
    demo_mode: bool = _bool("DEMO_MODE", True)
    demo_password: str = os.getenv("DEMO_PASSWORD", "Demo-Pruefstand-2026!")
    session_idle_minutes: int = int(os.getenv("SESSION_IDLE_MINUTES", "480"))
    session_max_hours: int = int(os.getenv("SESSION_MAX_HOURS", "12"))
    login_max_failures: int = int(os.getenv("LOGIN_MAX_FAILURES", "5"))
    login_lock_minutes: int = int(os.getenv("LOGIN_LOCK_MINUTES", "10"))
    timezone: str = os.getenv("APP_TIMEZONE", "Europe/Berlin")


settings = Settings()
