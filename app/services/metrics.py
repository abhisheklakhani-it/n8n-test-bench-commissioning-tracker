"""Measured process times from the real task data (input for the value stream analysis)."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain import process as P
from app.models import Bench, StepTemplate, Task, utcnow


def step_times(db: Session) -> list[dict]:
    """Per step: average waiting time (ready -> start) and working time (start -> done, minus pauses) in minutes."""
    now = utcnow()
    rows = []
    for step in db.scalars(select(StepTemplate).order_by(StepTemplate.position)):
        tasks = list(db.scalars(select(Task).where(Task.step_code == step.code)))
        done = [t for t in tasks if t.status == P.PASS and t.started_at and t.finished_at]
        started = [t for t in tasks if t.ready_at and t.started_at]
        work = [P.working_seconds(t.started_at, t.finished_at, t.paused_seconds, t.paused_at, now) / 60 for t in done]
        wait = [P.waiting_seconds(t.ready_at, t.started_at, now) / 60 for t in started]
        avg_work = sum(work) / len(work) if work else None
        avg_wait = sum(wait) / len(wait) if wait else None
        rows.append({"step": step, "done": len(done), "avg_work_min": avg_work, "avg_wait_min": avg_wait})
    return rows


def totals(rows: list[dict]) -> dict:
    work = sum(r["avg_work_min"] or 0 for r in rows)
    wait = sum(r["avg_wait_min"] or 0 for r in rows)
    ratio = P.flow_ratio(work, wait)
    return {"work_min": work, "wait_min": wait, "lead_min": work + wait, "flow_pct": round(100 * ratio, 1) if ratio is not None else None}


def bench_lead_times(db: Session) -> list[tuple[Bench, float]]:
    return [(b, (b.released_at - b.created_at).total_seconds() / 3600) for b in db.scalars(select(Bench).where(Bench.released_at.is_not(None)))]
