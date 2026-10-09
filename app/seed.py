"""Process configuration and FICTIONAL demo data (no real persons, benches or results).

The commissioning steps below are an EXAMPLE for a brake / hydraulics test bench. Names,
checklists and tolerances are assumptions for demonstration and must be replaced by the
real process from the value stream analysis."""

from datetime import timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import settings
from app.domain import process as P
from app.domain.roles import ADMIN, ANALYST, LEAD, TECH
from app.models import AppSetting, AuditLog, Bench, LoginAttempt, Notification, StepTemplate, Task, User
from app.services import notify, workflow
from app.services.auth import hash_password


def m(key, de, en, unit, lo, hi):
    return {"key": key, "label_de": de, "label_en": en, "kind": "number", "unit": unit, "min": lo, "max": hi}


STEPS = [
    # code, discipline, depends_on, name_de, name_en, instructions_de, instructions_en, checklist_de, checklist_en, measurements
    ("S01", "MECH", [], "Mechanischer Aufbau & Hydraulikanschlüsse", "Mechanical set-up & hydraulic connections",
     "Prüfling einbauen, Hydraulikleitungen anschließen und alle Verschraubungen anziehen.",
     "Mount the unit under test, connect the hydraulic lines and tighten all fittings.",
     ["Prüfling fest eingebaut", "Hydraulikleitungen angeschlossen", "Sichtprüfung: keine Leckage"],
     ["Unit under test firmly mounted", "Hydraulic lines connected", "Visual check: no leakage"],
     [m("torque", "Anzugsmoment Verschraubung", "Fitting torque", "Nm", 18, 22)]),
    ("S02", "ELEC", ["S01"], "Stromversorgung & Not-Halt", "Power supply & emergency stop",
     "Spannung zuschalten und den Not-Halt auslösen. Der Prüfstand muss sicher stoppen.",
     "Switch on the power and trigger the emergency stop. The bench must stop safely.",
     ["Spannung zugeschaltet", "Not-Halt ausgelöst und geprüft", "Schutzhaube schließt"],
     ["Power switched on", "Emergency stop triggered and checked", "Safety cover closes"],
     [m("voltage", "Versorgungsspannung", "Supply voltage", "V", 11.5, 14.5)]),
    ("S03", "ELEC", ["S02"], "CAN-Kommunikation zum Bremsen-Steuergerät", "CAN communication to the brake ECU",
     "Verbindung zwischen Steuergerät, Prüfstand und Leitrechner prüfen.", "Check the connection between ECU, test bench and host PC.",
     ["Steuergerät antwortet", "Keine Fehlerspeicher-Einträge", "Leitrechner empfängt Daten"],
     ["ECU responds", "No fault memory entries", "Host PC receives data"],
     [m("busload", "CAN-Buslast", "CAN bus load", "%", 0, 60)]),
    ("S04", "MEAS", ["S03"], "Drucksensoren kalibrieren", "Pressure sensor calibration",
     "Drucksensoren mit dem Referenzmanometer vergleichen und kalibrieren.", "Compare the pressure sensors with the reference gauge and calibrate them.",
     ["Referenzmanometer angeschlossen", "Kalibrierung durchgeführt", "Protokoll abgelegt"],
     ["Reference gauge connected", "Calibration done", "Report filed"],
     [m("sensor_dev", "Abweichung zum Referenzwert", "Deviation from reference", "bar", -0.5, 0.5)]),
    ("S05", "SW", ["S03"], "Software & ESP-Konfiguration", "Software & ESP configuration",
     "Freigegebene Software flashen und die ESP-Parameter für den Prüfling laden.", "Flash the released software and load the ESP parameters for the unit under test.",
     ["Software-Version geflasht", "ESP-Parameter geladen", "Versionsnummer dokumentiert"],
     ["Software version flashed", "ESP parameters loaded", "Version number documented"],
     [{"key": "sw_version", "label_de": "Software-Version", "label_en": "Software version", "kind": "text", "unit": ""}]),
    ("S06", "TEST", ["S04", "S05"], "Dichtheitsprüfung & Referenzlauf", "Leak test & reference run",
     "System auf Prüfdruck bringen, Druckabfall messen und den Referenzlauf fahren.",
     "Bring the system to test pressure, measure the pressure drop and run the reference test.",
     ["Prüfdruck erreicht", "Referenzlauf durchgeführt", "Messdaten gespeichert"],
     ["Test pressure reached", "Reference run completed", "Measurement data saved"],
     [m("max_pressure", "Maximaler Systemdruck", "Maximum system pressure", "bar", 160, 200),
      m("pressure_drop", "Druckabfall in 60 s", "Pressure drop in 60 s", "bar", 0, 2)]),
    ("S07", "PM", ["S06"], "Dokumentation & Freigabe", "Documentation & release",
     "Unterlagen prüfen und den Prüfstand an die Nutzer übergeben.", "Check the documents and hand the test bench over to its users.",
     ["Dokumentation vollständig", "Abnahme durchgeführt", "Übergabe an Nutzer erfolgt"],
     ["Documentation complete", "Acceptance done", "Handed over to users"],
     []),
]

# username, full name (fictional), role, discipline
DEMO_USERS = [
    ("leitung", "Dr. Lena Beispiel", ADMIN, None),
    ("tl.mechanik", "Paul Muster", LEAD, "MECH"),
    ("tl.elektrik", "Jonas Muster", LEAD, "ELEC"),
    ("tl.messtechnik", "Clara Demo", LEAD, "MEAS"),
    ("tl.software", "Omar Beispiel", LEAD, "SW"),
    ("tl.pruefung", "Greta Test", LEAD, "TEST"),
    ("tl.projekt", "Henrik Plan", LEAD, "PM"),
    ("tech.mechanik", "Felix Schraube", TECH, "MECH"),
    ("tech.elektrik", "Mara Strom", TECH, "ELEC"),
    ("tech.elektrik2", "Tim Kabel", TECH, "ELEC"),
    ("tech.messtechnik", "Lukas Sensor", TECH, "MEAS"),
    ("tech.software", "Sara Code", TECH, "SW"),
    ("tech.pruefung", "Elias Lauf", TECH, "TEST"),
    ("tech.projekt", "Nina Akte", TECH, "PM"),
]
DEMO_PIN = "2468"


def ensure_process(db: Session) -> None:
    deps = {code: d for code, _, d, *_ in STEPS}
    P.validate_dependencies(deps)
    for i, (code, disc, d, nde, nen, ide, ien, cde, cen, meas) in enumerate(STEPS, 1):
        step = db.get(StepTemplate, code)
        if step is None:
            db.add(StepTemplate(code=code, position=i, discipline=disc, depends_on=d, name_de=nde, name_en=nen,
                                instructions_de=ide, instructions_en=ien, checklist_de=cde, checklist_en=cen, measurements=meas))
    if db.get(AppSetting, "overdue_hours") is None:
        db.add(AppSetting(key="overdue_hours", value="4"))
    db.commit()
    notify.ensure_default_rules(db)


def ensure_analyst(db: Session) -> None:
    """Creates the private analysis account from environment variables, once. Never resets it."""
    username = settings.analyst_username.strip().lower()
    if not username or not settings.analyst_password:
        return
    if db.scalar(select(User).where(User.username == username)):
        return
    db.add(User(username=username, full_name=settings.analyst_full_name, role=ANALYST, discipline=None,
                password_hash=hash_password(settings.analyst_password)))
    db.commit()


def good_values(step: StepTemplate) -> dict[str, str]:
    """Values in the middle of every tolerance (used for the demo scenario and tests)."""
    return {d["key"]: ("OK" if d.get("kind") == "text" else str(round((d["min"] + d["max"]) / 2, 2))) for d in step.measurements or []}


def _user(db: Session, username: str) -> User:
    return db.scalar(select(User).where(User.username == username))


def _run(db: Session, bench: Bench, steps: list[tuple[str, str, str, str]]) -> None:
    """steps: (step_code, username, result, comment)."""
    for code, username, result, comment in steps:
        task = next(t for t in bench.tasks if t.step_code == code)
        actor = _user(db, username)
        if result == P.IN_PROGRESS:
            workflow.start_task(db, actor, task)
            continue
        workflow.start_task(db, actor, task)
        workflow.submit_result(db, actor, task, result, comment, "", list(range(len(task.step.checklist_de))), good_values(task.step))


def _backdate(db: Session, bench: Bench, minutes_per_step: list[tuple[int, int]]) -> None:
    """Gives the demo scenario realistic times: (waiting, working) minutes per finished step."""
    for task, (wait, work) in zip([t for t in bench.tasks if t.started_at], minutes_per_step, strict=False):
        end = task.finished_at or task.started_at
        task.started_at = end - timedelta(minutes=work) if task.finished_at else task.started_at
        task.ready_at = task.started_at - timedelta(minutes=wait)
    db.commit()


def seed_scenario(db: Session) -> None:
    boss = _user(db, "leitung")
    owners = {"S01": "tech.mechanik", "S02": "tech.elektrik", "S03": "tech.elektrik", "S04": "tech.messtechnik",
              "S05": "tech.software", "S06": "tech.pruefung", "S07": "tech.projekt"}
    ps07 = workflow.create_bench(db, boss, "PS-07", "ESP-Hydraulik Dauerlauf", "Halle 3")
    _run(db, ps07, [(s, owners[s], P.PASS, "") for s in owners])
    _backdate(db, ps07, [(30, 95), (240, 40), (35, 60), (90, 120), (20, 75), (180, 150), (60, 45)])
    ps07.created_at = ps07.created_at - timedelta(days=9, hours=5)

    ps12 = workflow.create_bench(db, boss, "PS-12", "Bremsdruck-Prüfstand", "Halle 1")
    _run(db, ps12, [("S01", "tech.mechanik", P.PASS, ""), ("S02", "tech.elektrik", P.PASS, ""),
                    ("S03", "tech.elektrik2", P.FAIL, "Keine CAN-Botschaften vom Bremsen-Steuergerät / No CAN messages from brake ECU")])
    _backdate(db, ps12, [(45, 110), (300, 35), (25, 50)])

    ps21 = workflow.create_bench(db, boss, "PS-21", "iBooster HIL", "Labor 2")
    _run(db, ps21, [("S01", "tech.mechanik", P.PASS, ""), ("S02", "tech.elektrik", P.PASS, ""),
                    ("S03", "tech.elektrik", P.PASS, ""), ("S04", "tech.messtechnik", P.PASS, ""),
                    ("S05", "tech.software", P.IN_PROGRESS, "")])
    _backdate(db, ps21, [(20, 80), (150, 45), (30, 55), (60, 100), (15, 0)])

    ps15 = workflow.create_bench(db, boss, "PS-15", "ABS-Ventilblock", "Halle 3")
    first = next(t for t in ps15.tasks if t.step_code == "S01")
    first.ready_at = first.ready_at - timedelta(hours=6)  # shows the automatic escalation
    db.commit()
    workflow.check_overdue(db)


def seed_demo(db: Session) -> None:
    """Creates fictional users and the scenario, only into an empty database."""
    ensure_process(db)
    if not db.scalar(select(User.id).where(User.username == "leitung")):
        pw, pin = hash_password(settings.demo_password), hash_password(DEMO_PIN)
        for username, name, role, disc in DEMO_USERS:
            db.add(User(username=username, full_name=name, role=role, discipline=disc, password_hash=pw, pin_hash=pin if role == TECH else None))
        db.commit()
        seed_scenario(db)
    ensure_analyst(db)


def reset_demo_work(db: Session) -> None:
    """Demo only: restores the work scenario. Users, rules and the process analysis are kept."""
    db.execute(delete(Notification))
    db.execute(delete(Task))
    db.execute(delete(Bench))
    db.execute(delete(AuditLog))
    db.execute(delete(LoginAttempt))
    db.commit()
    seed_scenario(db)
