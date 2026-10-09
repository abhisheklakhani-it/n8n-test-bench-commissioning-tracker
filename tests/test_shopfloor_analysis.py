import dataclasses
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.domain import analysis as A
from app.domain import notifications as N
from app.domain import process as P
from app.models import AnalysisEntry, AnalysisRevision, Notification, StepTemplate, Task, User
from app.seed import DEMO_PIN, ensure_analyst, good_values, reset_demo_work
from app.services import auth as auth_service
from app.services import workflow
from app.services.workflow import WorkflowError
from tests.conftest import csrf_of, login

# ---------- pure rules ----------

DEFS = [{"key": "p", "label_de": "Druck", "label_en": "Pressure", "unit": "bar", "min": 160, "max": 200}]


def test_check_values_accepts_comma_and_flags_out_of_range():
    assert P.check_values(DEFS, {"p": "180,5"}) == ({"p": 180.5}, [], [])
    assert P.check_values(DEFS, {"p": "210"}) == ({"p": 210.0}, ["p"], [])
    assert P.check_values(DEFS, {"p": "abc"}) == ({}, [], ["p"])
    assert P.check_values(DEFS, {"p": "nan"}) == ({}, [], ["p"])
    assert P.check_values(DEFS, {}) == ({}, [], ["p"])


def test_working_time_excludes_pauses():
    t0 = datetime(2026, 1, 1, 8)
    assert P.working_seconds(t0, t0 + timedelta(minutes=60), 600, None, t0 + timedelta(hours=5)) == 3000
    # currently paused: the running pause is not counted
    assert P.working_seconds(t0, None, 0, t0 + timedelta(minutes=30), t0 + timedelta(minutes=50)) == 1800
    assert P.waiting_seconds(t0, t0 + timedelta(minutes=5), t0 + timedelta(hours=1)) == 300
    assert P.flow_ratio(30, 90) == 0.25 and P.flow_ratio(0, 0) is None


def test_analysis_clean_and_kpis():
    data, missing = A.clean("step", {"name": "", "processing_min": "12,5", "medium": "Fax"})
    assert missing == ["name"] and data["processing_min"] == "12.5" and data["medium"] == ""
    kpi = A.step_kpis([
        {"processing_min": "30", "waiting_min": "90", "media_break": "Ja", "waste": "Waiting"},
        {"processing_min": "20", "waiting_min": "60", "media_break": "Nein", "waste": "Waiting", "parallel": "Ja"},
    ])
    assert kpi["lead_min"] == 200 and kpi["flow_pct"] == 25.0 and kpi["media_breaks"] == 1 and kpi["parallel"] == 1
    assert kpi["wastes"] == [("Waiting", 2)]


def test_pin_rules():
    assert auth_service.pin_problems("12") == ["pin_rule_format"]
    assert auth_service.pin_problems("12a4") == ["pin_rule_format"]
    assert auth_service.pin_problems("1111") == ["pin_rule_trivial"]
    assert auth_service.pin_problems("1234") == ["pin_rule_trivial"]
    assert auth_service.pin_problems(DEMO_PIN) == []


def test_ip_allowed():
    assert auth_service.ip_allowed("8.8.8.8", "")
    assert auth_service.ip_allowed("10.20.30.40", "10.0.0.0/8, 192.168.1.0/24")
    assert not auth_service.ip_allowed("8.8.8.8", "10.0.0.0/8")
    assert not auth_service.ip_allowed("not-an-ip", "10.0.0.0/8")


# ---------- workflow ----------

def u(db, username):
    return db.scalar(select(User).where(User.username == username))


def ready_task(db, step="S01"):
    return db.scalar(select(Task).where(Task.step_code == step, Task.status == P.READY))


def test_values_outside_tolerance_can_never_be_done(db):
    t = ready_task(db)  # PS-15 S01, torque 18..22 Nm
    tech = u(db, "tech.mechanik")
    checks = list(range(len(t.step.checklist_de)))
    with pytest.raises(WorkflowError) as e:
        workflow.submit_result(db, tech, t, P.PASS, "", "", checks, {"torque": "30"})
    assert e.value.key == "err_out_of_range"
    with pytest.raises(WorkflowError) as e:
        workflow.submit_result(db, tech, t, P.PASS, "", "", checks, {})
    assert e.value.key == "err_values_missing"
    workflow.submit_result(db, tech, t, P.FAIL, "Moment zu hoch", "", [], {"torque": "30"})
    assert t.status == P.FAIL and t.values == {"torque": 30.0}


def test_pause_and_resume_track_time(db):
    t = ready_task(db)
    tech = u(db, "tech.mechanik")
    workflow.start_task(db, tech, t)
    workflow.pause_task(db, tech, t)
    with pytest.raises(WorkflowError):
        workflow.pause_task(db, tech, t)
    t.paused_at = t.paused_at - timedelta(minutes=10)
    workflow.resume_task(db, tech, t)
    assert t.paused_at is None and t.paused_seconds >= 600


def test_help_request_is_urgent_for_team_lead_once(db):
    t = ready_task(db)
    tech = u(db, "tech.mechanik")
    assert workflow.request_help(db, tech, t) == 1
    assert workflow.request_help(db, tech, t) == 0  # no duplicate within 10 minutes
    help_notes = list(db.scalars(select(Notification).where(Notification.event_type == N.HELP_REQUESTED)))
    assert [db.get(User, n.user_id).username for n in help_notes] == ["tl.mechanik"]
    assert help_notes[0].priority == N.HIGH and help_notes[0].params["worker"] == "Felix Schraube"
    with pytest.raises(WorkflowError):
        workflow.request_help(db, u(db, "tech.software"), t)


def test_open_tasks_for_worker_only_own_discipline(db):
    tasks = workflow.open_tasks_for(db, u(db, "tech.mechanik"))
    assert tasks and all(t.discipline == "MECH" for t in tasks)
    assert workflow.open_tasks_for(db, u(db, "tech.software"))[0].status == P.IN_PROGRESS  # own running task first


def test_demo_steps_have_valid_tolerances(db):
    for step in db.scalars(select(StepTemplate)):
        for d in step.measurements:
            assert d["min"] < d["max"] and d["unit"]
        _, out, invalid = P.check_values(step.measurements, good_values(step))
        assert out == [] and invalid == []


# ---------- shop-floor web flow ----------

def pin_login(client, db, username, pin=DEMO_PIN, follow=False):
    worker = u(db, username)
    page = client.get(f"/werker/pin/{worker.id}")
    return client.post(f"/werker/pin/{worker.id}", data={"csrf": csrf_of(page.text), "pin": pin}, follow_redirects=follow)


def test_worker_tiles_pin_login_and_one_task_screen(client, db):
    tiles = client.get("/werker")
    assert "Felix Schraube" in tiles.text and "Dr. Lena Beispiel" not in tiles.text  # only technicians
    r = pin_login(client, db, "tech.mechanik")
    assert r.status_code == 303 and r.headers["location"] == "/werker/aufgabe"
    screen = client.get("/werker/aufgabe")
    assert "PS-15" in screen.text and "Jetzt starten" in screen.text
    assert "PS-12" not in screen.text  # nothing that does not concern this worker


def test_wrong_pin_locks_and_pin_only_for_technicians(client, db):
    for _ in range(5):
        r = pin_login(client, db, "tech.elektrik", pin="9999")
        assert "e=pin_failed" in r.headers["location"]
    assert "e=login_locked" in pin_login(client, db, "tech.elektrik").headers["location"]
    boss = u(db, "leitung")
    assert client.get(f"/werker/pin/{boss.id}").status_code == 404


def test_pin_login_respects_factory_network(client, db, monkeypatch):
    monkeypatch.setattr(auth_service, "settings", dataclasses.replace(auth_service.settings, shopfloor_networks="10.0.0.0/8"))
    assert "e=pin_network" in pin_login(client, db, "tech.mechanik").headers["location"]


def test_pin_session_has_short_idle_timeout(client, db, app):
    pin_login(client, db, "tech.mechanik")
    from app.models import SessionToken

    with app.state.db.SessionLocal() as s:
        sess = s.scalar(select(SessionToken).where(SessionToken.kind == "pin"))
        sess.last_seen = sess.last_seen - timedelta(minutes=20)
        s.commit()
    assert client.get("/werker/aufgabe", follow_redirects=False).headers["location"] == "/login"


def test_worker_finishes_task_and_next_team_is_notified(client, db, app):
    pin_login(client, db, "tech.mechanik")
    t = ready_task(db)
    page = client.get(f"/werker/aufgabe?id={t.id}")
    client.post(f"/werker/aufgabe/{t.id}/start", data={"csrf": csrf_of(page.text)})
    page = client.get(f"/werker/aufgabe?id={t.id}")
    assert "Arbeitszeit" in page.text and 'name="v_torque"' in page.text
    r = client.post(f"/werker/aufgabe/{t.id}/ergebnis", data={"csrf": csrf_of(page.text), "result": "PASS", "check": ["0", "1", "2"], "v_torque": "19,5"},
                    follow_redirects=False)
    assert r.headers["location"] == "/werker/aufgabe?ok=ok_saved"
    with app.state.db.SessionLocal() as s:
        assert s.get(Task, t.id).status == P.PASS
        nxt = s.scalar(select(Task).where(Task.bench_id == t.bench_id, Task.step_code == "S02"))
        assert nxt.status == P.READY
        assert s.scalar(select(Notification).where(Notification.task_id == nxt.id, Notification.event_type == N.TASK_READY))
    other = TestClient(app)
    pin_login(other, db, "tech.elektrik")
    assert other.get("/api/status").json()["open"] >= 1


def test_qr_code_opens_the_right_task(client, db):
    r = client.get("/werker/pruefstand/PS-15", follow_redirects=False)
    assert r.headers["location"] == "/werker?next=/werker/pruefstand/PS-15"
    nxt = "/werker/pruefstand/PS-15"
    worker = u(db, "tech.mechanik")
    page = client.get(f"/werker/pin/{worker.id}?next={nxt}")
    r = client.post(f"/werker/pin/{worker.id}", data={"csrf": csrf_of(page.text), "pin": DEMO_PIN, "next": nxt}, follow_redirects=False)
    assert r.headers["location"] == nxt
    assert client.get(nxt, follow_redirects=False).headers["location"].startswith("/werker/aufgabe?id=")
    # no open redirect via next
    r = client.post(f"/werker/pin/{worker.id}", data={"csrf": csrf_of(client.get(f"/werker/pin/{worker.id}").text), "pin": DEMO_PIN, "next": "//evil.example"},
                    follow_redirects=False)
    assert r.headers["location"] == "/werker/aufgabe"


def test_qr_and_kpi_pages(as_user):
    boss = as_user("leitung")
    qr = boss.get("/qr")
    assert qr.status_code == 200 and "/werker/pruefstand/PS-12" in qr.text and "<svg" in qr.text
    kpi = boss.get("/kennzahlen")
    assert kpi.status_code == 200 and "Flussgrad" in kpi.text
    assert as_user("tech.mechanik").get("/qr").status_code == 403


# ---------- private process analysis ----------

@pytest.fixture()
def analyst(app, monkeypatch):
    import app.seed as seed

    monkeypatch.setattr(seed, "settings", dataclasses.replace(seed.settings, analyst_username="abhishek", analyst_password="Analyse-Passwort-2026"))
    with app.state.db.SessionLocal() as s:
        ensure_analyst(s)
        ensure_analyst(s)  # idempotent: never resets an existing account
        assert s.scalar(select(User).where(User.username == "abhishek")).role == "ANALYST"
    c = TestClient(app)
    assert login(c, "abhishek", "Analyse-Passwort-2026").headers["location"] == "/analyse"
    return c


def test_only_the_analyst_can_open_the_analysis(as_user, analyst):
    for username in ("leitung", "tl.elektrik", "tech.mechanik"):
        assert as_user(username).get("/analyse").status_code == 403, username
    assert analyst.get("/analyse").status_code == 200
    assert analyst.get("/leitung").status_code == 403


def test_analysis_entries_keep_history_and_are_never_lost(analyst, app):
    page = analyst.get("/analyse/step")
    data = {"csrf": csrf_of(page.text), "name": "Ergebnis abtippen", "processing_min": "15", "waiting_min": "45", "media_break": "Ja", "waste": "Transport"}
    assert "ok_saved" in analyst.post("/analyse/step", data=data, follow_redirects=False).headers["location"]
    with app.state.db.SessionLocal() as s:
        entry = s.scalar(select(AnalysisEntry).where(AnalysisEntry.section == "step"))
    data.update({"entry_id": str(entry.id), "processing_min": "10"})
    analyst.post("/analyse/step", data=data)
    analyst.post(f"/analyse/eintrag/{entry.id}/archivieren", data={"csrf": data["csrf"]})
    analyst.post(f"/analyse/eintrag/{entry.id}/wiederherstellen", data={"csrf": data["csrf"]})
    with app.state.db.SessionLocal() as s:
        revs = [r.action for r in s.scalars(select(AnalysisRevision).where(AnalysisRevision.entry_id == entry.id).order_by(AnalysisRevision.id))]
        assert revs == ["created", "updated", "archived", "restored"]
        assert s.get(AnalysisEntry, entry.id).data["processing_min"] == "10.0"
    assert "Ergebnis abtippen" in analyst.get(f"/analyse/eintrag/{entry.id}/verlauf").text
    export = analyst.get("/analyse/export.json")
    assert export.headers["content-disposition"].startswith("attachment") and len(export.json()["entries"][0]["revisions"]) == 4
    overview = analyst.get("/analyse")
    assert "18.2 %" in overview.text  # flow ratio = 10 / (10 + 45)


def test_required_fields_and_single_sections(analyst, app):
    page = analyst.get("/analyse/project")
    token = csrf_of(page.text)
    assert "err_required" in analyst.post("/analyse/project", data={"csrf": token, "problem": ""}, follow_redirects=False).headers["location"]
    analyst.post("/analyse/project", data={"csrf": token, "problem": "Medienbrüche"})
    analyst.post("/analyse/project", data={"csrf": token, "problem": "Medienbrüche und Wartezeiten"})
    with app.state.db.SessionLocal() as s:
        rows = list(s.scalars(select(AnalysisEntry).where(AnalysisEntry.section == "project")))
        assert len(rows) == 1 and rows[0].data["problem"] == "Medienbrüche und Wartezeiten" and len(rows[0].revisions) == 2


def test_public_demo_admin_cannot_see_or_take_over_the_analyst(as_user, analyst, app):
    boss = as_user("leitung")
    users_page = boss.get("/benutzer")
    assert "abhishek" not in users_page.text and 'value="ANALYST"' not in users_page.text
    with app.state.db.SessionLocal() as s:
        uid = s.scalar(select(User).where(User.username == "abhishek")).id
    token = csrf_of(users_page.text)
    assert "err_demo_protected" in boss.post(f"/benutzer/{uid}/passwort", data={"csrf": token}, follow_redirects=False).headers["location"]
    assert "err_demo_protected" in boss.post(f"/benutzer/{uid}/aktiv", data={"csrf": token}, follow_redirects=False).headers["location"]
    r = boss.post("/benutzer", data={"csrf": token, "username": "spion", "full_name": "x", "role": "ANALYST", "password": "Langes-Passwort-99"},
                  follow_redirects=False)
    assert "err_user_role" in r.headers["location"]


def test_demo_reset_keeps_users_rules_and_analysis(analyst, as_user, app):
    page = analyst.get("/analyse/kpi")
    analyst.post("/analyse/kpi", data={"csrf": csrf_of(page.text), "name": "Durchlaufzeit", "before": "9"})
    boss = as_user("leitung")
    r = boss.post("/demo/zuruecksetzen", data={"csrf": csrf_of(boss.get("/leitung").text)}, follow_redirects=False)
    assert "ok_demo_reset" in r.headers["location"]
    with app.state.db.SessionLocal() as s:
        assert s.scalar(select(AnalysisEntry).where(AnalysisEntry.section == "kpi")) is not None
        assert s.scalar(select(User).where(User.username == "abhishek")) is not None
        assert s.scalar(select(Task).where(Task.status == P.FAIL)) is not None  # scenario is back


def test_reset_demo_work_function(db):
    reset_demo_work(db)
    reset_demo_work(db)
    assert len(list(db.scalars(select(Task)))) == 28


# ---------- schema ----------

def test_migrations_match_the_models(app):
    """Guards against model changes without a migration (data must survive updates)."""
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext

    from app.db import Base

    with app.state.db.engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    assert diff == []
