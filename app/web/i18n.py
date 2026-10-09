"""German / English texts. Every key must exist in both languages (checked by a test)."""

LANGS = ("de", "en")

TEXTS: dict[str, dict[str, str]] = {
    "de": {
        "app_name": "Prüfstand-Inbetriebnahme",
        "demo_banner": "Demo-Version mit erfundenen Daten – keine echten Personen oder Prüfstände.",
        "nav_overview": "Übersicht", "nav_teams": "Teams", "nav_rules": "Meldungs-Regeln", "nav_users": "Benutzer",
        "nav_audit": "Protokoll", "nav_my_team": "Mein Team", "nav_my_tasks": "Meine Aufgaben", "nav_inbox": "Meldungen",
        "logout": "Abmelden", "urgent_bar": "Sie haben eine dringende Meldung – jetzt ansehen",
        "login_title": "Anmelden", "login_intro": "Bitte melden Sie sich mit Ihrem Benutzernamen an.",
        "username": "Benutzername", "password": "Passwort", "login_button": "Anmelden",
        "demo_accounts": "Demo-Zugänge", "demo_accounts_hint": "Auf eine Rolle klicken – das Passwort ist für alle gleich:",
        "hello": "Hallo, {name}!",
        "group_problem": "Problem – bitte lösen", "group_doing": "Weitermachen", "group_ready": "Jetzt starten",
        "open_and_start": "Öffnen und starten", "report_result": "Ergebnis melden", "solve_problem": "Problem ansehen",
        "all_done": "Alles erledigt!", "all_done_hint": "Sie bekommen eine Meldung, sobald es für Sie weitergeht.",
        "upcoming": "{n} Aufgaben Ihres Teams warten noch auf vorherige Schritte.",
        "bench": "Prüfstand", "what_to_do": "Was ist zu tun?", "before": "Vorher:", "after": "Danach:", "none": "nichts",
        "release": "Freigabe", "assignee": "Zuständig", "nobody_yet": "noch niemand", "ready_since": "Bereit seit",
        "started": "Gestartet", "finished": "Fertig", "comment": "Kommentar", "measurement": "Messwert",
        "waiting_title": "Noch nicht startbar", "waiting_hint": "Dieser Schritt wartet auf die vorherigen Schritte. Sie bekommen automatisch eine Meldung.",
        "done_title": "Erledigt", "confirm_reopen": "Schritt wirklich wieder öffnen? Folgeschritte werden wieder auf „Wartet“ gesetzt.",
        "reopen": "Wieder öffnen", "start_now": "Jetzt starten", "checklist": "Checkliste",
        "measurement_optional": "Messwert (optional)", "comment_label": "Kommentar (Pflicht bei Fehler oder blockiert)",
        "pass_hint": "„Erledigt“ geht erst, wenn alle Punkte abgehakt sind.",
        "result_pass": "Erledigt – alles OK", "result_fail": "Fehler", "result_blocked": "Blockiert",
        "not_your_task": "Dieser Schritt gehört zu einem anderen Team oder einer anderen Person.",
        "assign_to": "Zuweisen an", "nobody_team": "– ganzes Team –", "assign": "Zuweisen",
        "mark_all_read": "Alle als gelesen markieren",
        "inbox_order": "Reihenfolge: Ungelesen zuerst, dann Dringend vor Normal vor Info. Bei gleicher Priorität steht die älteste Meldung oben, damit nichts liegen bleibt. Ein Klick öffnet direkt die passende Aufgabe.",
        "resolved": "erledigt", "inbox_empty": "Keine Meldungen. Alles ruhig.",
        "team": "Team", "kpi_problems": "Probleme", "kpi_ready": "Bereit", "kpi_overdue": "Überfällig", "kpi_doing": "In Arbeit",
        "group_problem_team": "Probleme im Team", "group_ready_team": "Bereit zum Start – bitte verteilen", "step": "Schritt",
        "overdue": "überfällig", "nothing_ready": "Gerade nichts zu verteilen.", "group_doing_team": "In Arbeit",
        "coming_next": "{n} Schritte warten noch auf vorherige Teams.", "team_members": "Team", "open_tasks": "{n} offen",
        "recently_done": "Zuletzt erledigt",
        "central_title": "Übersicht aller Prüfstände", "kpi_active": "In Inbetriebnahme", "kpi_released": "Freigegeben",
        "kpi_lead_days": "Ø Durchlaufzeit (Tage)", "problems_now": "Probleme jetzt", "all_benches": "Alle Prüfstände",
        "progress": "Fortschritt", "released": "Freigegeben", "by_team": "Nach Team", "new_bench": "Neuer Prüfstand",
        "bench_code": "Kennung", "bench_name": "Bezeichnung", "bench_location": "Ort", "create_bench": "Anlegen",
        "recent_activity": "Letzte Aktivitäten",
        "rules_title": "Meldungs-Regeln", "rules_how_title": "So funktionieren Meldungen",
        "rules_how_1": "Jedes Ereignis hat eine Priorität: Dringend (sofort, rotes Banner), Normal (heute erledigen), Info (nur im Dashboard, kein Zähler) oder Aus.",
        "rules_how_2": "Empfänger sind Rollen, keine Einzelpersonen: Bearbeiter, Team (wenn noch niemand zugewiesen ist), Teamleitung, Leitung oder das Team des nächsten Schritts.",
        "rules_how_3": "Wer etwas selbst auslöst, bekommt keine Meldung darüber. Erledigte Arbeit schließt die passenden Meldungen automatisch.",
        "rules_how_4": "Startet niemand eine bereite Aufgabe innerhalb der eingestellten Stunden, wird automatisch eskaliert.",
        "event": "Ereignis", "priority": "Priorität", "to_assignee": "Bearbeiter", "to_team": "Team", "to_team_lead": "Teamleitung",
        "to_admin": "Leitung", "to_next_team": "Nächstes Team", "overdue_hours": "Eskalation nach (Stunden):", "save": "Speichern",
        "confirm_defaults": "Alle Regeln auf die Standardwerte zurücksetzen?", "restore_defaults": "Standardwerte wiederherstellen",
        "temp_password_for": "Einmal-Passwort für {name}:", "temp_password_hint": "bitte persönlich übergeben; es muss bei der ersten Anmeldung geändert werden.",
        "name": "Name", "role": "Rolle", "confirm_toggle_user": "Status dieses Benutzers wirklich ändern?",
        "deactivate": "Deaktivieren", "activate": "Aktivieren", "confirm_reset_pw": "Passwort wirklich zurücksetzen?",
        "reset_password": "Passwort zurücksetzen", "new_user": "Neuer Benutzer", "initial_password": "Erstes Passwort",
        "pw_rules": "Mindestens 12 Zeichen, Buchstaben und Zahlen, nicht den Benutzernamen enthalten.", "create_user": "Benutzer anlegen",
        "audit_hint": "Wer hat wann was getan. Dieses Protokoll kann nicht geändert werden.", "time": "Zeit", "action": "Aktion", "system": "System",
        "change_password": "Passwort ändern", "must_change_hint": "Bitte vergeben Sie jetzt ein eigenes Passwort.",
        "current_password": "Aktuelles Passwort", "new_password": "Neues Passwort", "repeat_password": "Neues Passwort wiederholen",
        "error_403": "Dafür haben Sie keine Berechtigung.", "error_404": "Diese Seite gibt es nicht.",
        "error_500": "Etwas ist schiefgelaufen. Bitte versuchen Sie es erneut.", "error_generic": "Das hat nicht geklappt.",
        "back_home": "Zur Startseite",
        "ok_started": "Gestartet. Viel Erfolg!", "ok_saved": "Gespeichert. Die nächsten Personen wurden informiert.",
        "ok_assigned": "Zugewiesen.", "ok_reopened": "Wieder geöffnet.", "ok_password": "Passwort geändert.",
        "ok_rules": "Regeln gespeichert.", "ok_user_created": "Benutzer angelegt.", "ok_bench_created": "Prüfstand angelegt. Das erste Team wurde benachrichtigt.",
        "err_not_allowed": "Das dürfen Sie bei diesem Schritt nicht.", "err_wrong_state": "Das geht im aktuellen Status nicht.",
        "err_result": "Bitte ein Ergebnis wählen.", "err_checklist": "Bitte zuerst alle Punkte der Checkliste abhaken.",
        "err_comment_required": "Bitte kurz beschreiben, was nicht funktioniert.", "err_assignee": "Diese Person kann den Schritt nicht übernehmen.",
        "err_reopen": "Nicht möglich: Ein Folgeschritt wurde schon begonnen.", "err_bench_code": "Kennung: nur Buchstaben, Zahlen, - und _ (max. 20).",
        "err_bench_exists": "Diese Kennung gibt es schon.", "err_demo_protected": "In der Demo sind die Demo-Zugänge geschützt.",
        "err_pw_current": "Das aktuelle Passwort stimmt nicht.", "err_pw_repeat": "Die beiden neuen Passwörter sind verschieden.",
        "pw_rule_length": "Das Passwort braucht mindestens 12 Zeichen.", "pw_rule_mix": "Das Passwort braucht Buchstaben und Zahlen.",
        "pw_rule_username": "Das Passwort darf den Benutzernamen nicht enthalten.", "err_user_input": "Bitte Name und gültigen Benutzernamen angeben.",
        "err_user_role": "Teamleitung und Techniker brauchen ein Team.", "err_user_exists": "Diesen Benutzernamen gibt es schon.",
        "err_self": "Sie können sich nicht selbst deaktivieren.",
        "login_failed": "Benutzername oder Passwort ist falsch.", "login_locked": "Zu viele Versuche. Bitte in einigen Minuten erneut versuchen.",
    },
    "en": {
        "app_name": "Test Bench Commissioning",
        "demo_banner": "Demo version with made-up data – no real people or test benches.",
        "nav_overview": "Overview", "nav_teams": "Teams", "nav_rules": "Notification rules", "nav_users": "Users",
        "nav_audit": "Audit log", "nav_my_team": "My team", "nav_my_tasks": "My tasks", "nav_inbox": "Notifications",
        "logout": "Sign out", "urgent_bar": "You have an urgent notification – view it now",
        "login_title": "Sign in", "login_intro": "Please sign in with your username.",
        "username": "Username", "password": "Password", "login_button": "Sign in",
        "demo_accounts": "Demo accounts", "demo_accounts_hint": "Click a role – the password is the same for all:",
        "hello": "Hello, {name}!",
        "group_problem": "Problem – please solve", "group_doing": "Continue", "group_ready": "Start now",
        "open_and_start": "Open and start", "report_result": "Report result", "solve_problem": "View problem",
        "all_done": "All done!", "all_done_hint": "You will get a notification as soon as there is work for you.",
        "upcoming": "{n} tasks of your team are still waiting for earlier steps.",
        "bench": "Test bench", "what_to_do": "What to do?", "before": "Before:", "after": "After:", "none": "nothing",
        "release": "Release", "assignee": "Assigned to", "nobody_yet": "nobody yet", "ready_since": "Ready since",
        "started": "Started", "finished": "Finished", "comment": "Comment", "measurement": "Measured value",
        "waiting_title": "Not startable yet", "waiting_hint": "This step waits for the previous steps. You will be notified automatically.",
        "done_title": "Done", "confirm_reopen": "Really reopen this step? Following steps go back to “Waiting”.",
        "reopen": "Reopen", "start_now": "Start now", "checklist": "Checklist",
        "measurement_optional": "Measured value (optional)", "comment_label": "Comment (required for failure or blocked)",
        "pass_hint": "“Done” is possible once every checklist item is ticked.",
        "result_pass": "Done – all OK", "result_fail": "Failure", "result_blocked": "Blocked",
        "not_your_task": "This step belongs to another team or person.",
        "assign_to": "Assign to", "nobody_team": "– whole team –", "assign": "Assign",
        "mark_all_read": "Mark all as read",
        "inbox_order": "Order: unread first, then Urgent before Normal before Info. Within the same priority the oldest message is on top, so nothing is forgotten. One click opens the matching task.",
        "resolved": "done", "inbox_empty": "No notifications. All quiet.",
        "team": "Team", "kpi_problems": "Problems", "kpi_ready": "Ready", "kpi_overdue": "Overdue", "kpi_doing": "In progress",
        "group_problem_team": "Problems in the team", "group_ready_team": "Ready to start – please distribute", "step": "Step",
        "overdue": "overdue", "nothing_ready": "Nothing to distribute right now.", "group_doing_team": "In progress",
        "coming_next": "{n} steps are still waiting for earlier teams.", "team_members": "Team", "open_tasks": "{n} open",
        "recently_done": "Recently done",
        "central_title": "Overview of all test benches", "kpi_active": "In commissioning", "kpi_released": "Released",
        "kpi_lead_days": "Avg. lead time (days)", "problems_now": "Problems now", "all_benches": "All test benches",
        "progress": "Progress", "released": "Released", "by_team": "By team", "new_bench": "New test bench",
        "bench_code": "ID", "bench_name": "Name", "bench_location": "Location", "create_bench": "Create",
        "recent_activity": "Recent activity",
        "rules_title": "Notification rules", "rules_how_title": "How notifications work",
        "rules_how_1": "Every event has a priority: Urgent (immediately, red banner), Normal (do today), Info (dashboard only, no counter) or Off.",
        "rules_how_2": "Recipients are roles, not individuals: assignee, team (if nobody is assigned yet), team lead, department lead or the team of the next step.",
        "rules_how_3": "Whoever triggers something is not notified about it. Finished work closes the matching notifications automatically.",
        "rules_how_4": "If nobody starts a ready task within the configured hours, it is escalated automatically.",
        "event": "Event", "priority": "Priority", "to_assignee": "Assignee", "to_team": "Team", "to_team_lead": "Team lead",
        "to_admin": "Department lead", "to_next_team": "Next team", "overdue_hours": "Escalate after (hours):", "save": "Save",
        "confirm_defaults": "Reset all rules to the default values?", "restore_defaults": "Restore defaults",
        "temp_password_for": "One-time password for {name}:", "temp_password_hint": "hand it over in person; it must be changed at the first sign-in.",
        "name": "Name", "role": "Role", "confirm_toggle_user": "Really change the status of this user?",
        "deactivate": "Deactivate", "activate": "Activate", "confirm_reset_pw": "Really reset the password?",
        "reset_password": "Reset password", "new_user": "New user", "initial_password": "Initial password",
        "pw_rules": "At least 12 characters, letters and digits, must not contain the username.", "create_user": "Create user",
        "audit_hint": "Who did what and when. This log cannot be changed.", "time": "Time", "action": "Action", "system": "System",
        "change_password": "Change password", "must_change_hint": "Please choose your own password now.",
        "current_password": "Current password", "new_password": "New password", "repeat_password": "Repeat new password",
        "error_403": "You are not allowed to do this.", "error_404": "This page does not exist.",
        "error_500": "Something went wrong. Please try again.", "error_generic": "That did not work.",
        "back_home": "Back to start",
        "ok_started": "Started. Good luck!", "ok_saved": "Saved. The next people have been notified.",
        "ok_assigned": "Assigned.", "ok_reopened": "Reopened.", "ok_password": "Password changed.",
        "ok_rules": "Rules saved.", "ok_user_created": "User created.", "ok_bench_created": "Test bench created. The first team has been notified.",
        "err_not_allowed": "You are not allowed to do this for this step.", "err_wrong_state": "Not possible in the current status.",
        "err_result": "Please choose a result.", "err_checklist": "Please tick every checklist item first.",
        "err_comment_required": "Please describe briefly what does not work.", "err_assignee": "This person cannot take over the step.",
        "err_reopen": "Not possible: a following step has already started.", "err_bench_code": "ID: letters, digits, - and _ only (max. 20).",
        "err_bench_exists": "This ID already exists.", "err_demo_protected": "In the demo the demo accounts are protected.",
        "err_pw_current": "The current password is wrong.", "err_pw_repeat": "The two new passwords differ.",
        "pw_rule_length": "The password needs at least 12 characters.", "pw_rule_mix": "The password needs letters and digits.",
        "pw_rule_username": "The password must not contain the username.", "err_user_input": "Please enter a name and a valid username.",
        "err_user_role": "Team leads and technicians need a team.", "err_user_exists": "This username already exists.",
        "err_self": "You cannot deactivate yourself.",
        "login_failed": "Username or password is wrong.", "login_locked": "Too many attempts. Please try again in a few minutes.",
    },
}

ROLE = {"de": {"ADMIN": "Leitung", "LEAD": "Teamleitung", "TECH": "Techniker/in"}, "en": {"ADMIN": "Department lead", "LEAD": "Team lead", "TECH": "Technician"}}
DISCIPLINE = {
    "de": {"MECH": "Mechanik", "ELEC": "Elektrik", "MEAS": "Messtechnik", "SW": "Software", "TEST": "Prüfung", "PM": "Projektleitung"},
    "en": {"MECH": "Mechanics", "ELEC": "Electrics", "MEAS": "Measurement", "SW": "Software", "TEST": "Testing", "PM": "Project mgmt."},
}
STATUS = {
    "de": {"WAITING": "Wartet", "READY": "Bereit", "IN_PROGRESS": "In Arbeit", "PASS": "Erledigt", "FAIL": "Fehler", "BLOCKED": "Blockiert"},
    "en": {"WAITING": "Waiting", "READY": "Ready", "IN_PROGRESS": "In progress", "PASS": "Done", "FAIL": "Failure", "BLOCKED": "Blocked"},
}
STATUS_SHORT = {
    "de": {"WAITING": "·", "READY": "B", "IN_PROGRESS": "A", "PASS": "✓", "FAIL": "F", "BLOCKED": "X"},
    "en": {"WAITING": "·", "READY": "R", "IN_PROGRESS": "P", "PASS": "✓", "FAIL": "F", "BLOCKED": "X"},
}
PRIORITY = {"de": {1: "Dringend", 2: "Normal", 3: "Info", 0: "Aus"}, "en": {1: "Urgent", 2: "Normal", 3: "Info", 0: "Off"}}
EVENT = {
    "de": {
        "STEP_FAILED": ("Schritt fehlgeschlagen", "Ein Prüfschritt hat einen Fehler."),
        "STEP_BLOCKED": ("Schritt blockiert", "Es fehlt etwas, der Schritt kann nicht weiter."),
        "TASK_READY": ("Aufgabe ist startbar", "Alle vorherigen Schritte sind erledigt."),
        "TASK_ASSIGNED": ("Aufgabe zugewiesen", "Die Teamleitung hat jemandem einen Schritt gegeben."),
        "TASK_OVERDUE": ("Aufgabe überfällig", "Eine startbare Aufgabe wurde zu lange nicht begonnen."),
        "DOWNSTREAM_DELAYED": ("Nächster Schritt verzögert", "Info an das nächste Team, dass es später wird."),
        "STEP_PASSED": ("Schritt erledigt", "Ein Schritt wurde erfolgreich abgeschlossen."),
        "BENCH_RELEASED": ("Prüfstand fertig", "Alle Schritte eines Prüfstands sind erledigt."),
    },
    "en": {
        "STEP_FAILED": ("Step failed", "A test step has a failure."),
        "STEP_BLOCKED": ("Step blocked", "Something is missing, the step cannot continue."),
        "TASK_READY": ("Task can start", "All previous steps are done."),
        "TASK_ASSIGNED": ("Task assigned", "The team lead gave a step to someone."),
        "TASK_OVERDUE": ("Task overdue", "A startable task was not started for too long."),
        "DOWNSTREAM_DELAYED": ("Next step delayed", "Info for the next team that it will take longer."),
        "STEP_PASSED": ("Step done", "A step was completed successfully."),
        "BENCH_RELEASED": ("Test bench finished", "All steps of a test bench are done."),
    },
}
MESSAGE = {
    "de": {
        "STEP_FAILED": "{bench}: {step} „{name}“ ist fehlgeschlagen. Blockiert: {blocked}.",
        "STEP_BLOCKED": "{bench}: {step} „{name}“ ist blockiert. Blockiert: {blocked}.",
        "TASK_READY": "{bench}: Sie können jetzt mit {step} „{name}“ beginnen.",
        "TASK_ASSIGNED": "{bench}: Ihnen wurde {step} „{name}“ zugewiesen.",
        "TASK_OVERDUE": "{bench}: {step} „{name}“ wartet seit über {hours} Std. auf den Start.",
        "DOWNSTREAM_DELAYED": "{bench}: Ihr nächster Schritt verzögert sich – {step} „{name}“ hat ein Problem.",
        "STEP_PASSED": "{bench}: {step} „{name}“ ist erledigt.",
        "BENCH_RELEASED": "{bench}: Alle Schritte erledigt – bereit zur Übergabe.",
    },
    "en": {
        "STEP_FAILED": "{bench}: {step} “{name}” failed. Blocked: {blocked}.",
        "STEP_BLOCKED": "{bench}: {step} “{name}” is blocked. Blocked: {blocked}.",
        "TASK_READY": "{bench}: You can start {step} “{name}” now.",
        "TASK_ASSIGNED": "{bench}: {step} “{name}” was assigned to you.",
        "TASK_OVERDUE": "{bench}: {step} “{name}” has been waiting to start for more than {hours} h.",
        "DOWNSTREAM_DELAYED": "{bench}: Your next step is delayed – {step} “{name}” has a problem.",
        "STEP_PASSED": "{bench}: {step} “{name}” is done.",
        "BENCH_RELEASED": "{bench}: All steps done – ready for handover.",
    },
}
ACTION_HINT = {
    "de": {"STEP_FAILED": "Problem ansehen", "STEP_BLOCKED": "Problem ansehen", "TASK_READY": "Aufgabe öffnen", "TASK_ASSIGNED": "Aufgabe öffnen",
           "TASK_OVERDUE": "Aufgabe öffnen", "DOWNSTREAM_DELAYED": "Details", "STEP_PASSED": "Details", "BENCH_RELEASED": "Prüfstand ansehen"},
    "en": {"STEP_FAILED": "View problem", "STEP_BLOCKED": "View problem", "TASK_READY": "Open task", "TASK_ASSIGNED": "Open task",
           "TASK_OVERDUE": "Open task", "DOWNSTREAM_DELAYED": "Details", "STEP_PASSED": "Details", "BENCH_RELEASED": "View test bench"},
}
AUDIT = {
    "de": {"login": "hat sich angemeldet", "bench_created": "hat Prüfstand {bench} angelegt", "task_started": "hat {bench} {step} gestartet",
           "task_result": "hat {bench} {step} gemeldet: {result}", "task_assigned": "hat {bench} {step} zugewiesen", "task_reopened": "hat {bench} {step} wieder geöffnet",
           "rules_changed": "hat Meldungs-Regeln geändert", "rules_reset": "hat Meldungs-Regeln zurückgesetzt", "user_created": "hat Benutzer {username} angelegt",
           "user_activated": "hat {username} aktiviert", "user_deactivated": "hat {username} deaktiviert", "password_reset": "hat das Passwort von {username} zurückgesetzt",
           "password_changed": "hat das eigene Passwort geändert"},
    "en": {"login": "signed in", "bench_created": "created test bench {bench}", "task_started": "started {bench} {step}",
           "task_result": "reported {bench} {step}: {result}", "task_assigned": "assigned {bench} {step}", "task_reopened": "reopened {bench} {step}",
           "rules_changed": "changed notification rules", "rules_reset": "reset notification rules", "user_created": "created user {username}",
           "user_activated": "activated {username}", "user_deactivated": "deactivated {username}", "password_reset": "reset the password of {username}",
           "password_changed": "changed their own password"},
}


def _lang(lang: str) -> str:
    return lang if lang in LANGS else "de"


class _Safe(dict):
    def __missing__(self, key):
        return "–"


def translator(lang: str):
    texts = TEXTS[_lang(lang)]

    def t(key: str, **kw) -> str:
        value = texts.get(key)
        if value is None:
            return key
        return value.format_map(_Safe(kw)) if kw else value

    return t


def role(code: str, lang: str) -> str:
    return ROLE[_lang(lang)].get(code, code)


def discipline(code: str | None, lang: str) -> str:
    return DISCIPLINE[_lang(lang)].get(code or "", code or "–")


def status(code: str, lang: str) -> str:
    return STATUS[_lang(lang)].get(code, code)


def status_short(code: str, lang: str) -> str:
    return STATUS_SHORT[_lang(lang)].get(code, code)


def priority(value: int, lang: str) -> str:
    return PRIORITY[_lang(lang)].get(value, str(value))


def step_name(step, lang: str) -> str:
    return step.name_en if _lang(lang) == "en" else step.name_de


def step_instructions(step, lang: str) -> str:
    return step.instructions_en if _lang(lang) == "en" else step.instructions_de


def checklist(step, lang: str) -> list[str]:
    return step.checklist_en if _lang(lang) == "en" else step.checklist_de


def event_name(event_type: str, lang: str) -> str:
    return EVENT[_lang(lang)].get(event_type, (event_type, ""))[0]


def event_desc(event_type: str, lang: str) -> str:
    return EVENT[_lang(lang)].get(event_type, ("", ""))[1]


def notification_text(n, lang: str) -> str:
    p = dict(n.params or {})
    p["name"] = p.get("name_en" if _lang(lang) == "en" else "name_de", "")
    p["blocked"] = ", ".join(p.get("blocked") or []) or "–"
    return MESSAGE[_lang(lang)].get(n.event_type, n.event_type).format_map(_Safe(p))


def action_hint(n, lang: str) -> str:
    return ACTION_HINT[_lang(lang)].get(n.event_type, "")


def audit_text(a, lang: str) -> str:
    who = a.user.full_name if a.user else "System"
    details = dict(a.details or {})
    if "result" in details:
        details["result"] = status(details["result"], lang)
    return f"{who} " + AUDIT[_lang(lang)].get(a.action, a.action).format_map(_Safe(details))
