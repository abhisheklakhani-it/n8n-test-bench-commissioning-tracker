import pytest
from sqlalchemy import select

from app.domain import process as P
from app.models import StepRevision, StepTemplate, Task, User
from app.services import steps, workflow
from app.services.workflow import WorkflowError
from tests.conftest import csrf_of


def u(db, username):
    return db.scalar(select(User).where(User.username == username))


def form_for(step, **changes):
    f = {"instructions_de": step.instructions_de, "instructions_en": step.instructions_en,
         "checklist_de": "\n".join(step.checklist_de), "checklist_en": "\n".join(step.checklist_en)}
    for i, m in enumerate(step.measurements):
        f.update({f"a{i}_key": m["key"], f"a{i}_label_de": m["label_de"], f"a{i}_label_en": m["label_en"], f"a{i}_kind": m.get("kind", "number"),
                  f"a{i}_unit": m.get("unit", ""), f"a{i}_min": str(m.get("min", "")), f"a{i}_max": str(m.get("max", ""))})
    f.update(changes)
    return f


def test_parse_step_spec_validates():
    spec, errors = P.parse_step_spec({"instructions_de": "Tun", "checklist_de": "a\nb", "a0_label_de": "Druck", "a0_min": "5", "a0_max": "1"}, [])
    assert errors == ["err_step_range"]
    spec, errors = P.parse_step_spec({"instructions_de": "", "checklist_de": ""}, [])
    assert errors == ["err_step_checklist", "err_step_instructions"]
    spec, errors = P.parse_step_spec({"instructions_de": "Tun", "checklist_de": "a\nb", "checklist_en": "a",
                                      "a0_label_de": "Version", "a0_kind": "text"}, [])
    assert errors == ["err_step_checklist_en"]
    spec, errors = P.parse_step_spec({"instructions_de": "Tun", "checklist_de": "a", "a0_label_de": "Druck", "a0_min": "1,5", "a0_max": "3",
                                      "a1_label_de": "Druck", "a1_kind": "text"}, [])
    assert not errors and [m["key"] for m in spec["measurements"]] == ["druck", "druck_2"] and spec["measurements"][0]["min"] == 1.5
    assert spec["checklist_en"] == ["a"] and spec["instructions_en"] == "Tun"


def test_lead_edits_only_own_team(db):
    s01 = db.get(StepTemplate, "S01")
    assert steps.can_edit(u(db, "tl.mechanik"), s01)
    assert steps.can_edit(u(db, "leitung"), s01)
    assert not steps.can_edit(u(db, "tl.elektrik"), s01)
    assert not steps.can_edit(u(db, "tech.mechanik"), s01)
    with pytest.raises(WorkflowError):
        steps.update_step(db, u(db, "tl.elektrik"), s01, form_for(s01, instructions_de="x"))


def test_new_version_with_history_and_running_work_keeps_its_version(db):
    s01 = db.get(StepTemplate, "S01")
    running = db.scalar(select(Task).where(Task.step_code == "S01", Task.status == "READY"))
    workflow.start_task(db, u(db, "tech.mechanik"), running)  # snapshot of version 1
    changed = steps.update_step(db, u(db, "tl.mechanik"), s01, form_for(s01, checklist_de="Neuer Punkt A\nNeuer Punkt B", checklist_en=""))
    assert changed and s01.version == 2
    assert [r.version for r in db.scalars(select(StepRevision).where(StepRevision.step_code == "S01").order_by(StepRevision.version))] == [1, 2]
    assert running.spec.checklist_de == ["Prüfling fest eingebaut", "Hydraulikleitungen angeschlossen", "Sichtprüfung: keine Leckage"]
    # finishing the running task still needs the 3 items of its own version
    workflow.submit_result(db, u(db, "tech.mechanik"), running, P.PASS, "", "", [0, 1, 2], {"torque": "20"})
    assert running.status == P.PASS
    # a new bench gets the new version
    bench = workflow.create_bench(db, u(db, "leitung"), "PS-55", "Neu")
    new_task = next(t for t in bench.tasks if t.step_code == "S01")
    assert new_task.spec.checklist_de == ["Neuer Punkt A", "Neuer Punkt B"]
    assert steps.update_step(db, u(db, "tl.mechanik"), s01, form_for(s01)) is False  # unchanged -> no new version


def test_text_answer_is_required_for_done(db):
    s01 = db.get(StepTemplate, "S01")
    f = form_for(s01, a1_label_de="Seriennummer Prüfling", a1_kind="text")
    steps.update_step(db, u(db, "tl.mechanik"), s01, f)
    task = db.scalar(select(Task).where(Task.step_code == "S01", Task.status == "READY"))
    tech = u(db, "tech.mechanik")
    with pytest.raises(WorkflowError) as e:
        workflow.submit_result(db, tech, task, P.PASS, "", "", [0, 1, 2], {"torque": "20"})
    assert e.value.key == "err_values_missing"
    workflow.submit_result(db, tech, task, P.PASS, "", "", [0, 1, 2], {"torque": "20", "seriennummer_pruefling": "SN-4711"})
    assert task.values["seriennummer_pruefling"] == "SN-4711"


def test_step_editor_pages(as_user, app):
    lead = as_user("tl.mechanik")
    assert "S01" in lead.get("/schritte").text
    page = lead.get("/schritte/S01")
    assert page.status_code == 200 and "So sieht es der Werker" in page.text and 'name="checklist_de"' in page.text
    other = lead.get("/schritte/S03")
    assert 'name="checklist_de"' not in other.text  # read only for another team
    with app.state.db.SessionLocal() as s:
        data = form_for(s.get(StepTemplate, "S01"), instructions_de="Neu: Prüfling einbauen.")
    data["csrf"] = csrf_of(page.text)
    r = lead.post("/schritte/S01", data=data, follow_redirects=False)
    assert "ok_step_saved" in r.headers["location"]
    r = lead.post("/schritte/S03", data=data, follow_redirects=False)
    assert "err_not_allowed" in r.headers["location"]
    assert as_user("tech.mechanik").get("/schritte").status_code == 403
