"""ORM models. Times are stored in UTC (naive datetimes = UTC)."""

from datetime import UTC, datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20))  # ADMIN | LEAD | TECH  (see domain.roles)
    discipline: Mapped[str | None] = mapped_column(String(20), nullable=True)  # MECH, ELEC, ...
    lang: Mapped[str] = mapped_column(String(2), default="de")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False)
    # 4-6 digit PIN for the shop-floor tablet login (Argon2 hash), technicians only
    pin_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class SessionToken(Base):
    __tablename__ = "sessions"
    id: Mapped[int] = mapped_column(primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    csrf_token: Mapped[str] = mapped_column(String(64))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(10), default="password")  # "password" | "pin" (shop floor, shorter timeout)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    last_seen: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    user: Mapped[User] = relationship()


class LoginAttempt(Base):
    __tablename__ = "login_attempts"
    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(200), index=True)  # "user:<name>" or "ip:<addr>"
    at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class StepTemplate(Base):
    """One step of the commissioning process (configurable checklist + dependencies)."""

    __tablename__ = "step_templates"
    code: Mapped[str] = mapped_column(String(10), primary_key=True)  # S01 ...
    position: Mapped[int] = mapped_column(Integer)
    name_de: Mapped[str] = mapped_column(String(120))
    name_en: Mapped[str] = mapped_column(String(120))
    discipline: Mapped[str] = mapped_column(String(20))
    depends_on: Mapped[list] = mapped_column(JSON, default=list)
    instructions_de: Mapped[str] = mapped_column(Text, default="")
    instructions_en: Mapped[str] = mapped_column(Text, default="")
    checklist_de: Mapped[list] = mapped_column(JSON, default=list)
    checklist_en: Mapped[list] = mapped_column(JSON, default=list)
    # answers the worker gives besides the checklist:
    # [{"key", "label_de", "label_en", "kind": "number"|"text", "unit", "min", "max"}]
    measurements: Mapped[list] = mapped_column(JSON, default=list)
    version: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    def to_spec(self) -> dict:
        """What the worker sees and has to answer for this step (copied into a task when it starts)."""
        return {"version": self.version, "instructions_de": self.instructions_de, "instructions_en": self.instructions_en,
                "checklist_de": list(self.checklist_de), "checklist_en": list(self.checklist_en), "measurements": list(self.measurements or [])}


class StepSpec:
    """Read-only view of a step specification (live template or a task's snapshot)."""

    def __init__(self, data: dict):
        self.version = data.get("version", 1)
        self.instructions_de = data.get("instructions_de", "")
        self.instructions_en = data.get("instructions_en", "")
        self.checklist_de = data.get("checklist_de", [])
        self.checklist_en = data.get("checklist_en", [])
        self.measurements = data.get("measurements", [])


class StepRevision(Base):
    """Every change a team lead makes to a step is kept (who, when, what)."""

    __tablename__ = "step_revisions"
    id: Mapped[int] = mapped_column(primary_key=True)
    step_code: Mapped[str] = mapped_column(ForeignKey("step_templates.code"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    data: Mapped[dict] = mapped_column(JSON, default=dict)
    at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    user: Mapped[User | None] = relationship()


class Bench(Base):
    __tablename__ = "benches"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    location: Mapped[str] = mapped_column(String(80), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    released_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    tasks: Mapped[list["Task"]] = relationship(back_populates="bench", order_by="Task.position")


class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (UniqueConstraint("bench_id", "step_code"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    bench_id: Mapped[int] = mapped_column(ForeignKey("benches.id", ondelete="CASCADE"), index=True)
    step_code: Mapped[str] = mapped_column(ForeignKey("step_templates.code"))
    position: Mapped[int] = mapped_column(Integer)
    discipline: Mapped[str] = mapped_column(String(20), index=True)
    status: Mapped[str] = mapped_column(String(20), default="WAITING", index=True)
    assignee_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    ready_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    comment: Mapped[str] = mapped_column(Text, default="")
    measurement: Mapped[str] = mapped_column(String(200), default="")
    checklist_done: Mapped[list] = mapped_column(JSON, default=list)
    values: Mapped[dict] = mapped_column(JSON, default=dict)  # measured values {key: number}
    paused_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    paused_seconds: Mapped[int] = mapped_column(Integer, default=0)
    # copy of the step specification taken when the work starts (later edits do not change running work)
    spec_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
    overdue_notified: Mapped[bool] = mapped_column(Boolean, default=False)
    bench: Mapped[Bench] = relationship(back_populates="tasks")
    step: Mapped[StepTemplate] = relationship()
    assignee: Mapped[User | None] = relationship()

    @property
    def spec(self) -> StepSpec:
        return StepSpec(self.spec_snapshot if self.spec_snapshot else self.step.to_spec())


class NotificationRule(Base):
    """Set by the department lead: priority and recipients per event type."""

    __tablename__ = "notification_rules"
    event_type: Mapped[str] = mapped_column(String(30), primary_key=True)
    priority: Mapped[int] = mapped_column(Integer)  # 1 high, 2 normal, 3 low/info, 0 off
    to_assignee: Mapped[bool] = mapped_column(Boolean, default=False)
    to_team: Mapped[bool] = mapped_column(Boolean, default=False)
    to_team_lead: Mapped[bool] = mapped_column(Boolean, default=False)
    to_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    to_next_team: Mapped[bool] = mapped_column(Boolean, default=False)


class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    event_type: Mapped[str] = mapped_column(String(30))
    priority: Mapped[int] = mapped_column(Integer, index=True)
    bench_id: Mapped[int | None] = mapped_column(ForeignKey("benches.id", ondelete="CASCADE"), nullable=True)
    task_id: Mapped[int | None] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), nullable=True)
    params: Mapped[dict] = mapped_column(JSON, default=dict)
    dedupe_key: Mapped[str | None] = mapped_column(String(120), unique=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    bench: Mapped[Bench | None] = relationship()
    task: Mapped[Task | None] = relationship()


class AppSetting(Base):
    __tablename__ = "app_settings"
    key: Mapped[str] = mapped_column(String(50), primary_key=True)
    value: Mapped[str] = mapped_column(String(200))


class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(primary_key=True)
    at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action: Mapped[str] = mapped_column(String(50))
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    user: Mapped[User | None] = relationship()


class AnalysisEntry(Base):
    """One record of the process analysis (value stream, interview, action, KPI ...).
    Never hard-deleted: archiving hides it, every change is kept as a revision."""

    __tablename__ = "analysis_entries"
    id: Mapped[int] = mapped_column(primary_key=True)
    section: Mapped[str] = mapped_column(String(20), index=True)
    data: Mapped[dict] = mapped_column(JSON, default=dict)
    position: Mapped[int] = mapped_column(Integer, default=0)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    revisions: Mapped[list["AnalysisRevision"]] = relationship(back_populates="entry", order_by="AnalysisRevision.id.desc()")


class AnalysisRevision(Base):
    __tablename__ = "analysis_revisions"
    id: Mapped[int] = mapped_column(primary_key=True)
    entry_id: Mapped[int] = mapped_column(ForeignKey("analysis_entries.id", ondelete="CASCADE"), index=True)
    action: Mapped[str] = mapped_column(String(20))  # created | updated | archived | restored
    data: Mapped[dict] = mapped_column(JSON, default=dict)
    at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    entry: Mapped[AnalysisEntry] = relationship(back_populates="revisions")
    user: Mapped[User | None] = relationship()
