"""Structure of the process analysis workbook (value stream analysis, Lean) and its KPIs.
Pure configuration and calculations, no framework imports."""

from collections import Counter

TIMWOODS = ("Transport", "Inventory", "Motion", "Waiting", "Overproduction", "Overprocessing", "Defects", "Skills", "-")


def f(key, de, en, kind="text", choices=None, required=False):
    """kind: text | textarea | number | date | choice"""
    return {"key": key, "de": de, "en": en, "kind": kind, "choices": list(choices or []), "required": required}


SECTIONS: dict[str, dict] = {
    "project": {
        "de": "Projekt & Ziel", "en": "Project & goal", "single": True,
        "hint_de": "Problemstellung, Umfang und messbares Ziel – die Grundlage der Wertstromanalyse.",
        "hint_en": "Problem statement, scope and measurable goal – the basis of the value stream analysis.",
        "fields": [
            f("problem", "Problemstellung", "Problem statement", "textarea", required=True),
            f("scope", "Umfang (Start und Ende des Prozesses, Prüfstandstyp)", "Scope (process start and end, bench type)", "textarea"),
            f("goal", "Ziel und Erfolgskriterien", "Goal and success criteria", "textarea"),
            f("stakeholders", "Beteiligte und Rollen", "Stakeholders and roles", "textarea"),
        ],
    },
    "step": {
        "de": "Prozessaufnahme (Ist)", "en": "Process mapping (current state)", "single": False,
        "hint_de": "Ein Eintrag pro Prozessschritt. Zeiten in Minuten. Daraus werden Durchlaufzeit und Flussgrad berechnet.",
        "hint_en": "One entry per process step. Times in minutes. Lead time and flow ratio are calculated from them.",
        "fields": [
            f("name", "Prozessschritt", "Process step", required=True),
            f("role", "Verantwortliche Rolle", "Responsible role"),
            f("persons", "Anzahl Personen", "Number of people", "number"),
            f("input", "Input (Information, Dokument)", "Input (information, document)"),
            f("output", "Output", "Output"),
            f("medium", "Medium", "Medium", "choice", ["Papier", "Excel", "E-Mail", "Telefon/mündlich", "Tool/System", "-"]),
            f("media_break", "Medienbruch?", "Media break?", "choice", ["Ja", "Nein"]),
            f("processing_min", "Bearbeitungszeit (min)", "Processing time (min)", "number"),
            f("waiting_min", "Wartezeit davor (min)", "Waiting time before (min)", "number"),
            f("parallel", "Parallel möglich?", "Can run in parallel?", "choice", ["Ja", "Nein"]),
            f("waste", "Verschwendung (TIMWOODS)", "Waste (TIMWOODS)", "choice", TIMWOODS),
            f("next_needs", "Was braucht der nächste Schritt?", "What does the next step need?", "textarea"),
            f("note", "Bemerkung", "Note", "textarea"),
        ],
    },
    "interview": {
        "de": "Gemba & Interviews", "en": "Gemba & interviews", "single": False,
        "hint_de": "Beobachtungen vor Ort und kurze Gespräche. Rolle statt Name – anonym.",
        "hint_en": "Observations on site and short conversations. Role instead of name – anonymous.",
        "fields": [
            f("date", "Datum", "Date", "date"),
            f("role", "Rolle / Team", "Role / team", required=True),
            f("place", "Ort (Arbeitsplatz, Pause, Termin)", "Place (workplace, break, meeting)"),
            f("pain_point", "Größter Schmerzpunkt", "Biggest pain point", "textarea"),
            f("quote", "Zitat", "Quote", "textarea"),
            f("idea", "Idee / Wunsch", "Idea / wish", "textarea"),
        ],
    },
    "action": {
        "de": "Maßnahmen (PDCA)", "en": "Actions (PDCA)", "single": False,
        "hint_de": "Verbesserungen aus der Analyse, mit Verantwortlichem, Termin und Wirkung.",
        "hint_en": "Improvements from the analysis, with owner, due date and effect.",
        "fields": [
            f("title", "Maßnahme", "Action", required=True),
            f("waste", "Gegen welche Verschwendung?", "Which waste does it address?", "choice", TIMWOODS),
            f("owner", "Verantwortlich", "Owner"),
            f("due", "Termin", "Due date", "date"),
            f("status", "Status (PDCA)", "Status (PDCA)", "choice", ["Plan", "Do", "Check", "Act", "Erledigt"]),
            f("effect", "Erwartete / gemessene Wirkung", "Expected / measured effect", "textarea"),
        ],
    },
    "kpi": {
        "de": "Kennzahlen vorher / nachher", "en": "KPIs before / after", "single": False,
        "hint_de": "Messgrößen für die Validierung im Labor (z. B. Durchlaufzeit, Medienbrüche, Zeit bis Fehlererkennung).",
        "hint_en": "Metrics for validation in the lab (e.g. lead time, media breaks, time to detect failures).",
        "fields": [
            f("name", "Kennzahl", "Metric", required=True),
            f("unit", "Einheit", "Unit"),
            f("before", "Vorher", "Before", "number"),
            f("after", "Nachher", "After", "number"),
            f("source", "Quelle / Messmethode", "Source / method", "textarea"),
        ],
    },
    "target": {
        "de": "Soll-Zustand", "en": "Target state", "single": True,
        "hint_de": "Wie soll der Prozess nach der Verbesserung laufen? Erst vereinfachen, dann automatisieren.",
        "hint_en": "How should the process run after the improvement? Simplify first, then automate.",
        "fields": [
            f("flow", "Fluss und Übergaben", "Flow and handovers", "textarea"),
            f("standards", "Standardisierung (Checklisten, Vorlagen)", "Standardisation (checklists, templates)", "textarea"),
            f("automation", "Digitalisierung / Automatisierung", "Digitalisation / automation", "textarea"),
            f("tools", "Werkzeugbewertung (Power Platform, n8n, eigene App …)", "Tool evaluation (Power Platform, n8n, own app …)", "textarea"),
            f("open_questions", "Offene Fragen", "Open questions", "textarea"),
        ],
    },
}


def clean(section: str, form: dict) -> tuple[dict, list[str]]:
    """Validates a submitted form. Returns (data, missing_required_keys)."""
    data, missing = {}, []
    for fld in SECTIONS[section]["fields"]:
        value = str(form.get(fld["key"], "")).strip()[:4000]
        if fld["kind"] == "number" and value:
            try:
                value = str(float(value.replace(",", ".")))
            except ValueError:
                value = ""
        if fld["kind"] == "choice" and value and value not in fld["choices"]:
            value = ""
        if fld["required"] and not value:
            missing.append(fld["key"])
        data[fld["key"]] = value
    return data, missing


def _num(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def step_kpis(rows: list[dict]) -> dict:
    """KPIs of the current-state value stream from the recorded steps."""
    processing = sum(_num(r.get("processing_min")) for r in rows)
    waiting = sum(_num(r.get("waiting_min")) for r in rows)
    lead = processing + waiting
    wastes = Counter(r.get("waste") for r in rows if r.get("waste") and r.get("waste") != "-")
    return {
        "steps": len(rows),
        "processing_min": round(processing, 1),
        "waiting_min": round(waiting, 1),
        "lead_min": round(lead, 1),
        "flow_pct": round(100 * processing / lead, 1) if lead else None,
        "media_breaks": sum(1 for r in rows if r.get("media_break") == "Ja"),
        "parallel": sum(1 for r in rows if r.get("parallel") == "Ja"),
        "wastes": wastes.most_common(),
    }
