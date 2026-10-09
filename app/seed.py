"""Process configuration and FICTIONAL demo data (no real persons, benches or results)."""

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.domain import process as P
from app.domain.roles import ADMIN, LEAD, TECH
from app.models import AppSetting, Bench, StepTemplate, User
from app.services import notify, workflow
from app.services.auth import hash_password

STEPS = [
    # code, discipline, depends_on, name_de, name_en, instructions_de, instructions_en, checklist_de, checklist_en
    ("S01", "MECH", [], "Mechanischer Aufbau & Verkabelung", "Mechanical installation & wiring",
     "Prüfstand aufbauen und Verkabelung nach Plan prüfen.", "Install the test bench and check the wiring against the plan.",
     ["Prüfstand fest verschraubt", "Verkabelung nach Plan geprüft", "Erdung gemessen"],
     ["Test bench firmly bolted", "Wiring checked against plan", "Earthing measured"]),
    ("S02", "ELEC", ["S01"], "Einschalten & Not-Halt-Test", "Power-up & emergency stop test",
     "Spannung zuschalten und alle Sicherheitsfunktionen prüfen.", "Switch on power and test all safety functions.",
     ["Spannung zugeschaltet", "Not-Halt ausgelöst und geprüft", "Schutzeinrichtungen aktiv"],
     ["Power switched on", "Emergency stop triggered and checked", "Safety guards active"]),
    ("S03", "ELEC", ["S02"], "Netzwerk- & CAN-Kommunikation", "Network & CAN communication",
     "Kommunikation zwischen Steuergerät, Prüfstand und Leitrechner prüfen.", "Check communication between ECU, test bench and host PC.",
     ["CAN-Botschaften werden empfangen", "Buslast im Normalbereich", "Verbindung zum Leitrechner steht"],
     ["CAN messages are received", "Bus load in normal range", "Connection to host PC works"]),
    ("S04", "MEAS", ["S03"], "Sensoren & Aktoren kalibrieren", "Sensor & actuator calibration",
     "Alle Sensoren kalibrieren und Werte auf Plausibilität prüfen.", "Calibrate all sensors and check the values for plausibility.",
     ["Sensoren kalibriert", "Kalibrierprotokoll abgelegt", "Werte plausibel"],
     ["Sensors calibrated", "Calibration report filed", "Values plausible"]),
    ("S05", "SW", ["S03"], "Software flashen & HIL konfigurieren", "Software flashing & HIL setup",
     "Freigegebene Software-Version flashen und HIL-Konfiguration laden.", "Flash the released software version and load the HIL configuration.",
     ["Software-Version geflasht", "HIL-Konfiguration geladen", "Versionsnummer dokumentiert"],
     ["Software version flashed", "HIL configuration loaded", "Version number documented"]),
    ("S06", "TEST", ["S04", "S05"], "Referenzlauf", "Reference test run",
     "Referenzlauf fahren und Ergebnisse mit den Toleranzen vergleichen.", "Run the reference test and compare the results with the tolerances.",
     ["Referenzlauf durchgeführt", "Ergebnisse innerhalb der Toleranz", "Messdaten gespeichert"],
     ["Reference run completed", "Results within tolerance", "Measurement data saved"]),
    ("S07", "PM", ["S06"], "Dokumentation & Freigabe", "Documentation & release",
     "Dokumentation prüfen und den Prüfstand an die Nutzer übergeben.", "Check the documentation and hand the test bench over to its users.",
     ["Dokumentation vollständig", "Abnahme durchgeführt", "Übergabe an Nutzer erfolgt"],
     ["Documentation complete", "Acceptance done", "Handed over to users"]),
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


def ensure_process(db: Session) -> None:
    deps = {code: d for code, _, d, *_ in STEPS}
    P.validate_dependencies(deps)
    for i, (code, disc, d, nde, nen, ide, ien, cde, cen) in enumerate(STEPS, 1):
        if db.get(StepTemplate, code) is None:
            db.add(StepTemplate(code=code, position=i, discipline=disc, depends_on=d, name_de=nde, name_en=nen,
                                instructions_de=ide, instructions_en=ien, checklist_de=cde, checklist_en=cen))
    if db.get(AppSetting, "overdue_hours") is None:
        db.add(AppSetting(key="overdue_hours", value="4"))
    db.commit()
    notify.ensure_default_rules(db)


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
        workflow.submit_result(db, actor, task, result, comment, "", list(range(len(task.step.checklist_de))))


def seed_demo(db: Session) -> None:
    """Creates fictional users and a realistic scenario, only into an empty database."""
    ensure_process(db)
    if db.scalar(select(User.id).limit(1)):
        return
    pw = hash_password(settings.demo_password)
    for username, name, role, disc in DEMO_USERS:
        db.add(User(username=username, full_name=name, role=role, discipline=disc, password_hash=pw))
    db.commit()
    boss = _user(db, "leitung")
    all_steps = ["S01", "S02", "S03", "S04", "S05", "S06", "S07"]
    owners = {"S01": "tech.mechanik", "S02": "tech.elektrik", "S03": "tech.elektrik", "S04": "tech.messtechnik",
              "S05": "tech.software", "S06": "tech.pruefung", "S07": "tech.projekt"}

    ps07 = workflow.create_bench(db, boss, "PS-07", "E-Achse Dauerlauf", "Halle 3")
    _run(db, ps07, [(s, owners[s], P.PASS, "") for s in all_steps])
    ps07.created_at = ps07.created_at - timedelta(days=9, hours=5)  # realistic lead time for the demo KPI
    db.commit()

    ps12 = workflow.create_bench(db, boss, "PS-12", "Hydraulik-Prüfstand", "Halle 1")
    _run(db, ps12, [("S01", "tech.mechanik", P.PASS, ""), ("S02", "tech.elektrik", P.PASS, ""),
                    ("S03", "tech.elektrik2", P.FAIL, "Keine CAN-Botschaften vom Steuergerät / No CAN messages from ECU")])

    ps21 = workflow.create_bench(db, boss, "PS-21", "Inverter HIL", "Labor 2")
    _run(db, ps21, [("S01", "tech.mechanik", P.PASS, ""), ("S02", "tech.elektrik", P.PASS, ""),
                    ("S03", "tech.elektrik", P.PASS, ""), ("S04", "tech.messtechnik", P.PASS, ""),
                    ("S05", "tech.software", P.IN_PROGRESS, "")])

    ps15 = workflow.create_bench(db, boss, "PS-15", "Bremsen-Prüfstand", "Halle 3")
    # make the first step of PS-15 look old enough to show the automatic escalation
    first = next(t for t in ps15.tasks if t.step_code == "S01")
    first.ready_at = first.ready_at - timedelta(hours=6)
    db.commit()
    workflow.check_overdue(db)
