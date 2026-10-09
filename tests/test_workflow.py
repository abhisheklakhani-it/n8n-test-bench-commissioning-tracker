from datetime import timedelta

import pytest
from sqlalchemy import select

from app.domain import notifications as N
from app.domain import process as P
from app.models import Notification, NotificationRule, Task, User
from app.services import workflow
from app.services.workflow import WorkflowError


def u(db, username):
    return db.scalar(select(User).where(User.username == username))


def task(bench, code):
    return next(t for t in bench.tasks if t.step_code == code)


def notes(db, event_type=None, bench_id=None):
    q = select(Notification)
    if event_type:
        q = q.where(Notification.event_type == event_type)
    if bench_id:
        q = q.where(Notification.bench_id == bench_id)
    return list(db.scalars(q))


def recipients(db, event_type, bench_id):
    return sorted(db.get(User, n.user_id).username for n in notes(db, event_type, bench_id))


def all_checks(t):
    return list(range(len(t.step.checklist_de)))


def passed(db, bench, code, username):
    t = task(bench, code)
    workflow.submit_result(db, u(db, username), t, P.PASS, "", "", all_checks(t))


@pytest.fixture()
def bench(db):
    return workflow.create_bench(db, u(db, "leitung"), "ps-99", "Test", "Halle 9")


def test_new_bench_makes_first_step_ready_and_notifies_only_that_team(db, bench):
    assert bench.code == "PS-99"
    assert task(bench, "S01").status == P.READY
    assert all(t.status == P.WAITING for t in bench.tasks if t.step_code != "S01")
    assert recipients(db, N.TASK_READY, bench.id) == ["tech.mechanik"]


def test_handover_goes_to_next_team_only(db, bench):
    passed(db, bench, "S01", "tech.mechanik")
    assert task(bench, "S02").status == P.READY
    ready = [n for n in notes(db, N.TASK_READY, bench.id) if n.task_id == task(bench, "S02").id]
    assert sorted(db.get(User, n.user_id).username for n in ready) == ["tech.elektrik", "tech.elektrik2"]
    assert all(n.priority == N.NORMAL for n in ready)


def test_parallel_steps_and_join(db, bench):
    for code, who in [("S01", "tech.mechanik"), ("S02", "tech.elektrik"), ("S03", "tech.elektrik")]:
        passed(db, bench, code, who)
    assert task(bench, "S04").status == P.READY and task(bench, "S05").status == P.READY
    passed(db, bench, "S04", "tech.messtechnik")
    assert task(bench, "S06").status == P.WAITING
    assert not [n for n in notes(db, N.TASK_READY, bench.id) if n.task_id == task(bench, "S06").id]
    passed(db, bench, "S05", "tech.software")
    assert task(bench, "S06").status == P.READY
    assert [db.get(User, n.user_id).username for n in notes(db, N.TASK_READY, bench.id) if n.task_id == task(bench, "S06").id] == ["tech.pruefung"]


def test_failure_is_urgent_for_lead_and_department_lead_not_for_reporter(db, bench):
    passed(db, bench, "S01", "tech.mechanik")
    t = task(bench, "S02")
    workflow.submit_result(db, u(db, "tech.elektrik"), t, P.FAIL, "Not-Halt reagiert nicht", "", [])
    failed = notes(db, N.STEP_FAILED, bench.id)
    assert sorted(db.get(User, n.user_id).username for n in failed) == ["leitung", "tl.elektrik"]
    assert all(n.priority == N.HIGH for n in failed)
    assert failed[0].params["blocked"] == ["S03", "S04", "S05", "S06", "S07"]
    delayed = recipients(db, N.DOWNSTREAM_DELAYED, bench.id)
    assert "tech.elektrik2" in delayed and "tech.elektrik" not in delayed  # S03 is ELEC; reporter excluded
    assert all(n.priority == N.LOW for n in notes(db, N.DOWNSTREAM_DELAYED, bench.id))


def test_fixing_a_failure_continues_the_flow_and_closes_the_alert(db, bench):
    passed(db, bench, "S01", "tech.mechanik")
    t = task(bench, "S02")
    workflow.submit_result(db, u(db, "tech.elektrik"), t, P.FAIL, "kaputt", "", [])
    passed(db, bench, "S02", "tech.elektrik")
    assert task(bench, "S03").status == P.READY
    assert all(n.resolved_at is not None for n in notes(db, N.STEP_FAILED, bench.id))


def test_pass_requires_full_checklist_and_failure_requires_comment(db, bench):
    t = task(bench, "S01")
    with pytest.raises(WorkflowError) as e:
        workflow.submit_result(db, u(db, "tech.mechanik"), t, P.PASS, "", "", [0])
    assert e.value.key == "err_checklist"
    with pytest.raises(WorkflowError) as e:
        workflow.submit_result(db, u(db, "tech.mechanik"), t, P.BLOCKED, "   ", "", [])
    assert e.value.key == "err_comment_required"


def test_other_discipline_and_colleagues_task_are_forbidden(db, bench):
    t = task(bench, "S01")
    with pytest.raises(WorkflowError):
        workflow.start_task(db, u(db, "tech.software"), t)
    passed(db, bench, "S01", "tech.mechanik")
    t2 = task(bench, "S02")
    workflow.start_task(db, u(db, "tech.elektrik"), t2)
    with pytest.raises(WorkflowError):
        workflow.submit_result(db, u(db, "tech.elektrik2"), t2, P.PASS, "", "", all_checks(t2))


def test_waiting_step_cannot_be_started(db, bench):
    with pytest.raises(WorkflowError) as e:
        workflow.start_task(db, u(db, "tech.elektrik"), task(bench, "S02"))
    assert e.value.key == "err_wrong_state"


def test_starting_closes_the_ready_notifications_for_everybody(db, bench):
    workflow.start_task(db, u(db, "tech.mechanik"), task(bench, "S01"))
    assert all(n.resolved_at is not None for n in notes(db, N.TASK_READY, bench.id))
    assert task(bench, "S01").assignee.username == "tech.mechanik"


def test_lead_assigns_within_own_team_only(db, bench):
    passed(db, bench, "S01", "tech.mechanik")
    t = task(bench, "S02")
    workflow.assign_task(db, u(db, "tl.elektrik"), t, u(db, "tech.elektrik2"))
    assert recipients(db, N.TASK_ASSIGNED, bench.id) == ["tech.elektrik2"]
    with pytest.raises(WorkflowError):
        workflow.assign_task(db, u(db, "tl.elektrik"), t, u(db, "tech.software"))
    with pytest.raises(WorkflowError):
        workflow.assign_task(db, u(db, "tl.software"), t, None)


def test_rule_switched_off_sends_nothing(db):
    db.get(NotificationRule, N.TASK_READY).priority = N.OFF
    db.commit()
    bench = workflow.create_bench(db, u(db, "leitung"), "PS-98", "x")
    assert notes(db, N.TASK_READY, bench.id) == []


def test_rule_priority_change_is_applied(db):
    db.get(NotificationRule, N.TASK_READY).priority = N.HIGH
    db.commit()
    bench = workflow.create_bench(db, u(db, "leitung"), "PS-97", "x")
    assert {n.priority for n in notes(db, N.TASK_READY, bench.id)} == {N.HIGH}


def test_overdue_escalates_once(db, bench):
    t = task(bench, "S01")
    t.ready_at = t.ready_at - timedelta(hours=5)
    db.commit()
    assert workflow.check_overdue(db) > 0
    assert recipients(db, N.TASK_OVERDUE, bench.id) == ["tech.mechanik", "tl.mechanik"]
    assert workflow.check_overdue(db) == 0


def test_release_notifies_department_lead(db, bench):
    owners = {"S01": "tech.mechanik", "S02": "tech.elektrik", "S03": "tech.elektrik", "S04": "tech.messtechnik",
              "S05": "tech.software", "S06": "tech.pruefung", "S07": "tech.projekt"}
    for code, who in owners.items():
        passed(db, bench, code, who)
    assert bench.released_at is not None
    assert recipients(db, N.BENCH_RELEASED, bench.id) == ["leitung"]


def test_reopen_resets_unstarted_following_steps(db, bench):
    passed(db, bench, "S01", "tech.mechanik")
    workflow.reopen_task(db, u(db, "tl.mechanik"), task(bench, "S01"))
    assert task(bench, "S01").status == P.IN_PROGRESS
    assert task(bench, "S02").status == P.WAITING
    with pytest.raises(WorkflowError):
        workflow.reopen_task(db, u(db, "tech.mechanik"), task(bench, "S01"))  # technicians cannot reopen


def test_duplicate_bench_code_and_bad_code(db, bench):
    for code in ("PS-99", "bad code!", ""):
        with pytest.raises(WorkflowError):
            workflow.create_bench(db, u(db, "leitung"), code, "x")
    with pytest.raises(WorkflowError):
        workflow.create_bench(db, u(db, "tl.elektrik"), "PS-50", "x")


def test_demo_seed_is_consistent(db):
    ps12 = db.scalar(select(Task).where(Task.step_code == "S03", Task.status == P.FAIL))
    assert ps12 is not None and ps12.bench.code == "PS-12"
