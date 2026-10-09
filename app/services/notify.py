"""Turns workflow events into notifications according to the configurable rules."""

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.domain import notifications as N
from app.domain.roles import ADMIN, LEAD, TECH
from app.models import Notification, NotificationRule, Task, User, utcnow


def get_rule(db: Session, event_type: str) -> N.Rule:
    row = db.get(NotificationRule, event_type)
    if row is None:
        return N.DEFAULT_RULES[event_type]
    return N.Rule(row.priority, row.to_assignee, row.to_team, row.to_team_lead, row.to_admin, row.to_next_team)


def ensure_default_rules(db: Session) -> None:
    for event_type, rule in N.DEFAULT_RULES.items():
        if db.get(NotificationRule, event_type) is None:
            db.add(NotificationRule(event_type=event_type, **rule.__dict__))
    db.commit()


def _active(db: Session, *conditions) -> list[User]:
    return list(db.scalars(select(User).where(User.active.is_(True), *conditions)))


def recipients(db: Session, rule: N.Rule, task: Task | None, next_tasks: list[Task] | None = None) -> set[int]:
    ids: set[int] = set()
    if task is not None:
        if rule.to_assignee and task.assignee_id:
            ids.add(task.assignee_id)
        elif rule.to_team:  # nobody assigned yet -> the whole team of that discipline
            ids |= {u.id for u in _active(db, User.role == TECH, User.discipline == task.discipline)}
        if rule.to_team_lead:
            ids |= {u.id for u in _active(db, User.role == LEAD, User.discipline == task.discipline)}
    if rule.to_admin:
        ids |= {u.id for u in _active(db, User.role == ADMIN)}
    if rule.to_next_team:
        for nxt in next_tasks or []:
            if nxt.assignee_id:
                ids.add(nxt.assignee_id)
            else:
                ids |= {u.id for u in _active(db, User.role == TECH, User.discipline == nxt.discipline)}
    return ids


def emit(
    db: Session,
    event_type: str,
    *,
    task: Task | None = None,
    bench_id: int | None = None,
    actor_id: int | None = None,
    next_tasks: list[Task] | None = None,
    params: dict | None = None,
    dedupe: str | None = None,
) -> int:
    """Creates one notification per recipient. The person who caused the event is never notified."""
    rule = get_rule(db, event_type)
    if rule.priority == N.OFF:
        return 0
    targets = recipients(db, rule, task, next_tasks) - ({actor_id} if actor_id else set())
    created = 0
    for user_id in sorted(targets):
        key = f"{dedupe}:{user_id}" if dedupe else None
        if key and db.scalar(select(Notification.id).where(Notification.dedupe_key == key)):
            continue
        db.add(
            Notification(
                user_id=user_id,
                event_type=event_type,
                priority=rule.priority,
                bench_id=bench_id if bench_id is not None else (task.bench_id if task else None),
                task_id=task.id if task else None,
                params=params or {},
                dedupe_key=key,
            )
        )
        created += 1
    return created


def resolve_for_task(db: Session, task_id: int, event_types: tuple[str, ...]) -> None:
    """Work done -> the matching notifications are no longer open for anybody."""
    db.execute(
        update(Notification)
        .where(Notification.task_id == task_id, Notification.event_type.in_(event_types), Notification.resolved_at.is_(None))
        .values(resolved_at=utcnow())
    )


def inbox(db: Session, user_id: int, limit: int = 100) -> list[Notification]:
    rows = list(db.scalars(select(Notification).where(Notification.user_id == user_id).order_by(Notification.created_at.desc()).limit(limit)))
    open_rows = [n for n in rows if n.resolved_at is None]
    done_rows = [n for n in rows if n.resolved_at is not None]
    open_rows.sort(key=lambda n: N.inbox_sort_key(n.read_at, n.priority, n.created_at))
    return open_rows + done_rows


def badge_count(db: Session, user_id: int) -> int:
    return db.scalar(
        select(func.count())
        .select_from(Notification)
        .where(
            Notification.user_id == user_id,
            Notification.read_at.is_(None),
            Notification.resolved_at.is_(None),
            Notification.priority.in_([N.HIGH, N.NORMAL]),
        )
    )


def has_open_high(db: Session, user_id: int) -> bool:
    return bool(
        db.scalar(
            select(Notification.id).where(
                Notification.user_id == user_id, Notification.priority == N.HIGH, Notification.resolved_at.is_(None), Notification.read_at.is_(None)
            )
        )
    )
