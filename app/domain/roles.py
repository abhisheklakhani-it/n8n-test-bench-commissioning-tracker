"""Roles, disciplines and the permission matrix (single source of truth, unit-tested)."""

ADMIN, LEAD, TECH, ANALYST = "ADMIN", "LEAD", "TECH", "ANALYST"
ROLES = (ADMIN, LEAD, TECH, ANALYST)

DISCIPLINES = ("MECH", "ELEC", "MEAS", "SW", "TEST", "PM")

# action -> roles allowed (object-level checks, e.g. own discipline, are done in the use cases)
PERMISSIONS: dict[str, frozenset[str]] = {
    "view_central_dashboard": frozenset({ADMIN}),
    "view_team_dashboard": frozenset({ADMIN, LEAD}),
    "view_my_tasks": frozenset({ADMIN, LEAD, TECH}),
    "work_on_task": frozenset({ADMIN, LEAD, TECH}),
    "assign_task": frozenset({ADMIN, LEAD}),
    "reopen_task": frozenset({ADMIN, LEAD}),
    "create_bench": frozenset({ADMIN}),
    "manage_users": frozenset({ADMIN}),
    "manage_rules": frozenset({ADMIN}),
    "view_audit": frozenset({ADMIN}),
    "view_kpis": frozenset({ADMIN, LEAD, ANALYST}),
    "print_qr": frozenset({ADMIN, LEAD}),
    "reset_demo": frozenset({ADMIN}),
    "use_shopfloor": frozenset({TECH}),
    # the process analysis is personal working material of the analyst (thesis author)
    "use_analysis": frozenset({ANALYST}),
}


def can(role: str, action: str) -> bool:
    return role in PERMISSIONS.get(action, frozenset())


def can_work_on(role: str, user_id: int, discipline: str | None, task_discipline: str, assignee_id: int | None) -> bool:
    """Admin: any task. Lead: tasks of the own discipline. Technician: own discipline, and only
    if the task is unassigned or assigned to them."""
    if role == ADMIN:
        return True
    if discipline != task_discipline:
        return False
    if role == LEAD:
        return True
    return role == TECH and assignee_id in (None, user_id)
