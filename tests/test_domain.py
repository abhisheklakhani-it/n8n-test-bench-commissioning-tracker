from datetime import datetime, timedelta

import pytest

from app.domain import notifications as N
from app.domain import process as P
from app.domain.roles import ADMIN, ANALYST, LEAD, PERMISSIONS, ROLES, TECH, can, can_work_on

DEPS = {"S01": [], "S02": ["S01"], "S03": ["S02"], "S04": ["S03"], "S05": ["S03"], "S06": ["S04", "S05"], "S07": ["S06"]}


def statuses(**kw):
    base = {s: P.WAITING for s in DEPS}
    base.update(kw)
    return base


def test_dependents_and_downstream():
    assert P.dependents(DEPS, "S03") == ["S04", "S05"]
    assert P.downstream(DEPS, "S03") == ["S04", "S05", "S06", "S07"]
    assert P.downstream(DEPS, "S07") == []


def test_initial_ready():
    assert P.initial_ready(DEPS) == ["S01"]


def test_parallel_branches_start_together():
    st = statuses(S01=P.PASS, S02=P.PASS, S03=P.PASS)
    assert P.newly_ready(DEPS, st, "S03") == ["S04", "S05"]


def test_join_waits_for_every_branch():
    st = statuses(S01=P.PASS, S02=P.PASS, S03=P.PASS, S04=P.PASS, S05=P.IN_PROGRESS)
    assert P.newly_ready(DEPS, st, "S04") == []
    st["S05"] = P.PASS
    assert P.newly_ready(DEPS, st, "S05") == ["S06"]


def test_progress_and_release():
    assert P.progress_pct([P.PASS, P.PASS, P.WAITING, P.FAIL]) == 50
    assert P.is_released([P.PASS] * 7)
    assert not P.is_released([P.PASS] * 6 + [P.READY])
    assert not P.is_released([])


def test_validate_dependencies_rejects_cycles_and_unknown_steps():
    P.validate_dependencies(DEPS)
    with pytest.raises(ValueError):
        P.validate_dependencies({"A": ["B"], "B": ["A"]})
    with pytest.raises(ValueError):
        P.validate_dependencies({"A": ["X"]})


def test_reopen_only_while_no_following_step_started():
    st = statuses(S01=P.PASS, S02=P.READY)
    assert P.can_reopen(DEPS, st, "S01")
    st["S02"] = P.IN_PROGRESS
    assert not P.can_reopen(DEPS, st, "S01")
    assert not P.can_reopen(DEPS, statuses(S01=P.READY), "S01")


def test_inbox_order_unread_then_priority_then_oldest_first():
    t0 = datetime(2026, 1, 1, 8)
    items = [
        ("low-new", None, N.LOW, t0 + timedelta(hours=3)),
        ("normal-old", None, N.NORMAL, t0),
        ("high-new", None, N.HIGH, t0 + timedelta(hours=2)),
        ("high-old", None, N.HIGH, t0 + timedelta(hours=1)),
        ("read-high", t0, N.HIGH, t0),
    ]
    ordered = [name for name, *rest in sorted(items, key=lambda i: N.inbox_sort_key(i[1], i[2], i[3]))]
    assert ordered == ["high-old", "high-new", "normal-old", "low-new", "read-high"]


def test_low_priority_never_counts_in_badge():
    assert N.counts_in_badge(N.HIGH) and N.counts_in_badge(N.NORMAL)
    assert not N.counts_in_badge(N.LOW) and not N.counts_in_badge(N.OFF)


def test_every_event_has_a_default_rule():
    assert set(N.DEFAULT_RULES) == set(N.EVENT_TYPES)


@pytest.mark.parametrize("action", sorted(PERMISSIONS))
@pytest.mark.parametrize("role", ROLES)
def test_permission_matrix(role, action):
    expected = {
        ADMIN: {"view_central_dashboard", "view_team_dashboard", "view_my_tasks", "work_on_task", "assign_task", "reopen_task",
                "create_bench", "manage_users", "manage_rules", "view_audit", "view_kpis", "print_qr", "reset_demo", "edit_steps"},
        LEAD: {"view_team_dashboard", "view_my_tasks", "work_on_task", "assign_task", "reopen_task", "view_kpis", "print_qr", "edit_steps"},
        TECH: {"view_my_tasks", "work_on_task", "use_shopfloor"},
        ANALYST: {"view_kpis", "use_analysis"},  # the private analysis is not visible to anybody else
    }[role]
    assert can(role, action) == (action in expected)


def test_object_level_task_access():
    assert can_work_on(ADMIN, 1, None, "ELEC", 99)
    assert can_work_on(LEAD, 1, "ELEC", "ELEC", 99)
    assert not can_work_on(LEAD, 1, "SW", "ELEC", None)
    assert can_work_on(TECH, 1, "ELEC", "ELEC", None)
    assert can_work_on(TECH, 1, "ELEC", "ELEC", 1)
    assert not can_work_on(TECH, 1, "ELEC", "ELEC", 2)  # assigned to a colleague
    assert not can_work_on(TECH, 1, "SW", "ELEC", None)  # other discipline
