import re
from pathlib import Path

from sqlalchemy import select

from app.models import Notification, Task, User
from app.web import i18n
from tests.conftest import csrf_of, login


def test_pages_require_login(client):
    for path in ("/", "/aufgaben", "/leitung", "/team", "/meldungen", "/regeln", "/benutzer", "/protokoll"):
        r = client.get(path, follow_redirects=False)
        assert r.status_code == 303 and r.headers["location"] == "/login", path
    assert client.get("/api/status").status_code == 401


def test_wrong_password_gives_generic_error_and_lockout(client):
    r = login(client, "leitung", "wrong-password-1")
    assert r.status_code == 401 and "falsch" in r.text
    r = login(client, "no.such.user", "wrong-password-1")
    assert r.status_code == 401 and "falsch" in r.text  # same message: no user enumeration
    for _ in range(5):
        login(client, "tech.software", "wrong-password-1")
    r = login(client, "tech.software")  # even the correct password is refused while locked
    assert r.status_code == 401 and "Zu viele Versuche" in r.text


def test_login_and_post_need_csrf(client, as_user):
    r = client.post("/login", data={"username": "leitung", "password": "x"})
    assert r.status_code == 403
    boss = as_user("leitung")
    assert boss.post("/pruefstaende", data={"code": "PS-77", "name": "x"}).status_code == 403


def test_roles_land_on_their_dashboard_and_cannot_see_others(as_user):
    tech = as_user("tech.elektrik")
    assert tech.get("/", follow_redirects=False).headers["location"] == "/aufgaben"
    for path in ("/leitung", "/regeln", "/benutzer", "/protokoll", "/team"):
        assert tech.get(path).status_code == 403, path
    lead = as_user("tl.elektrik")
    assert lead.get("/", follow_redirects=False).headers["location"] == "/team"
    assert lead.get("/team").status_code == 200
    assert lead.get("/leitung").status_code == 403
    boss = as_user("leitung")
    assert boss.get("/", follow_redirects=False).headers["location"] == "/leitung"


def test_notification_click_opens_the_task_form_and_submit_updates_everything(app, as_user):
    with app.state.db.SessionLocal() as db:
        tech = db.scalar(select(User).where(User.username == "tech.mechanik"))
        n = db.scalar(select(Notification).where(Notification.user_id == tech.id, Notification.resolved_at.is_(None), Notification.task_id.is_not(None)))
        task_id = n.task_id
    c = as_user("tech.mechanik")
    r = c.get(f"/meldung/{n.id}", follow_redirects=False)
    assert r.headers["location"] == f"/aufgabe/{task_id}"
    page = c.get(f"/aufgabe/{task_id}")
    assert "Checkliste" in page.text and 'value="PASS"' in page.text
    token = csrf_of(page.text)
    data = {"csrf": token, "result": "PASS", "check": ["0", "1", "2"], "v_torque": "20"}
    r = c.post(f"/aufgabe/{task_id}/ergebnis", data=data, follow_redirects=False)
    assert r.headers["location"] == "/aufgaben?ok=ok_saved"
    with app.state.db.SessionLocal() as db:
        assert db.get(Task, task_id).status == "PASS"
        assert db.get(Notification, n.id).read_at is not None
    # the next team sees it immediately
    elec = as_user("tech.elektrik")
    assert "PS-15" in elec.get("/aufgaben").text


def test_cannot_open_someone_elses_notification(app, as_user):
    with app.state.db.SessionLocal() as db:
        boss = db.scalar(select(User).where(User.username == "leitung"))
        foreign = db.scalar(select(Notification).where(Notification.user_id == boss.id))
    assert as_user("tech.software").get(f"/meldung/{foreign.id}").status_code == 404


def test_technician_cannot_submit_other_teams_task(app, as_user):
    with app.state.db.SessionLocal() as db:
        t = db.scalar(select(Task).where(Task.step_code == "S01", Task.status == "READY"))
    c = as_user("tech.software")
    token = csrf_of(c.get("/aufgaben").text)
    r = c.post(f"/aufgabe/{t.id}/ergebnis", data={"csrf": token, "result": "PASS", "check": ["0", "1", "2"]}, follow_redirects=False)
    assert "err_not_allowed" in r.headers["location"]


def test_rules_page_saves_priorities(app, as_user):
    boss = as_user("leitung")
    page = boss.get("/regeln")
    data = {"csrf": csrf_of(page.text), "overdue_hours": "6", "TASK_READY.priority": "1", "TASK_READY.to_assignee": "on", "TASK_READY.to_team": "on"}
    assert boss.post("/regeln", data=data, follow_redirects=False).status_code == 303
    from app.models import AppSetting, NotificationRule

    with app.state.db.SessionLocal() as db:
        assert db.get(NotificationRule, "TASK_READY").priority == 1
        assert db.get(AppSetting, "overdue_hours").value == "6"


def test_security_headers(client):
    h = client.get("/login").headers
    assert "default-src 'self'" in h["content-security-policy"]
    assert h["x-frame-options"] == "DENY" and h["x-content-type-options"] == "nosniff"
    cookie = login(client, "leitung").headers["set-cookie"]
    assert "HttpOnly" in cookie and "SameSite=lax" in cookie.replace("Lax", "lax")


def test_language_switch_has_no_open_redirect(as_user):
    c = as_user("tech.software")
    token = csrf_of(c.get("/aufgaben").text)
    r = c.post("/sprache", data={"csrf": token, "next": "//evil.example"}, follow_redirects=False)
    assert r.headers["location"] == "/"
    assert "My tasks" in c.get("/aufgaben").text


def test_demo_accounts_are_protected(as_user):
    c = as_user("tech.software")
    page = c.get("/passwort")
    r = c.post("/passwort", data={"csrf": csrf_of(page.text), "current": "x", "new": "y", "repeat": "y"}, follow_redirects=False)
    assert "err_demo_protected" in r.headers["location"]


def test_admin_creates_user_who_must_change_password(app, as_user):
    boss = as_user("leitung")
    token = csrf_of(boss.get("/benutzer").text)
    data = {"csrf": token, "username": "neu.tech", "full_name": "Neu Tech", "role": "TECH", "discipline": "SW", "password": "Start-Passwort-123"}
    r = boss.post("/benutzer", data=data, follow_redirects=False)
    assert "ok_user_created" in r.headers["location"]
    from fastapi.testclient import TestClient

    c = TestClient(app)
    r = login(c, "neu.tech", "Start-Passwort-123")
    assert r.headers["location"] == "/passwort"
    assert c.get("/aufgaben", follow_redirects=False).headers["location"] == "/passwort"


def test_every_used_text_key_exists_in_both_languages():
    assert set(i18n.TEXTS["de"]) == set(i18n.TEXTS["en"])
    root = Path(__file__).resolve().parent.parent / "app"
    used = set()
    for f in (root / "templates").glob("*.html"):
        used |= set(re.findall(r"""\bt\(\s*'([a-z0-9_]+)'""", f.read_text()))
    for f in root.rglob("*.py"):
        used |= set(re.findall(r"""["'](err_[a-z_]+|ok_[a-z_]+|pw_rule_[a-z_]+|login_(?:failed|locked))["']""", f.read_text()))
    missing = sorted(k for k in used if not k.endswith("_") and k not in i18n.TEXTS["de"])
    assert not missing, missing


def test_healthz(client):
    assert client.get("/healthz").json() == {"status": "ok"}
