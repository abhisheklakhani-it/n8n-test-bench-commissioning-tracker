"""Pure notification rules: event types, default priorities, inbox ordering."""

from dataclasses import dataclass
from datetime import datetime

HIGH, NORMAL, LOW, OFF = 1, 2, 3, 0
PRIORITIES = (HIGH, NORMAL, LOW, OFF)

STEP_FAILED = "STEP_FAILED"
STEP_BLOCKED = "STEP_BLOCKED"
TASK_READY = "TASK_READY"
TASK_ASSIGNED = "TASK_ASSIGNED"
TASK_OVERDUE = "TASK_OVERDUE"
DOWNSTREAM_DELAYED = "DOWNSTREAM_DELAYED"
STEP_PASSED = "STEP_PASSED"
BENCH_RELEASED = "BENCH_RELEASED"

EVENT_TYPES = (
    STEP_FAILED,
    STEP_BLOCKED,
    TASK_READY,
    TASK_ASSIGNED,
    TASK_OVERDUE,
    DOWNSTREAM_DELAYED,
    STEP_PASSED,
    BENCH_RELEASED,
)


@dataclass(frozen=True)
class Rule:
    priority: int
    to_assignee: bool = False
    to_team: bool = False
    to_team_lead: bool = False
    to_admin: bool = False
    to_next_team: bool = False


# Defaults (the department lead can change them in the app):
#  HIGH   = something is broken and blocks others  -> act now
#  NORMAL = it is your turn / work was handed to you -> act today
#  LOW    = information only, never interrupts       -> visible in dashboards
DEFAULT_RULES: dict[str, Rule] = {
    STEP_FAILED: Rule(HIGH, to_assignee=True, to_team_lead=True, to_admin=True),
    STEP_BLOCKED: Rule(HIGH, to_assignee=True, to_team_lead=True, to_admin=True),
    TASK_READY: Rule(NORMAL, to_assignee=True, to_team=True),
    TASK_ASSIGNED: Rule(NORMAL, to_assignee=True),
    TASK_OVERDUE: Rule(NORMAL, to_assignee=True, to_team=True, to_team_lead=True),
    DOWNSTREAM_DELAYED: Rule(LOW, to_next_team=True),
    STEP_PASSED: Rule(LOW, to_team_lead=True),
    BENCH_RELEASED: Rule(LOW, to_admin=True),
}

# TASK_READY goes to the assignee if one exists, otherwise to the whole team of that step.


def inbox_sort_key(read_at: datetime | None, priority: int, created_at: datetime) -> tuple:
    """Unread first, then priority (HIGH before NORMAL before LOW), then oldest first.
    Oldest-first inside a priority is FIFO: nothing waits forever behind newer messages."""
    return (read_at is not None, priority, created_at)


def counts_in_badge(priority: int) -> bool:
    """LOW messages never interrupt: they are not counted in the red bell badge."""
    return priority in (HIGH, NORMAL)
