# Test Bench Commissioning

A web application that digitalizes the **commissioning process of test benches** (Prüfstand-Inbetriebnahme). Every role gets its own simple screen: the **department lead** sees one central dashboard, **team leads** see their discipline, and **technicians** see only what they have to do next. When a step is finished, the **next responsible role is notified by priority**. A click on the notification opens the right task with instructions, a checklist and the result form. Submitting it updates every dashboard.

The repository also contains the earlier **n8n prototype** of the same idea ([`n8n/`](n8n/README.md)), which can serve as an integration layer (e.g. Teams messages, connections to test bench networks).

![CI](https://github.com/abhisheklakhani-it/n8n-test-bench-commissioning-tracker/actions/workflows/ci.yml/badge.svg)

![Demo on the tablet: tap your name, enter the PIN, start the task, tick the checklist, a value out of range locks "Done", the correct value turns green, the next worker immediately has the next step, the team lead edits what workers see](docs/images/shopfloor-demo.gif)

> **Live demo:** https://test-bench-commissioning.onrender.com (click a role on the login page). All names, test benches and results in the demo are **fictional**.

---

## Contents

- [Problem statement](#problem-statement)
- [Solution](#solution)
- [Roles and screens](#roles-and-screens)
- [How notifications work](#how-notifications-work)
- [Shop-floor mode for technicians](#shop-floor-mode-for-technicians)
- [Team leads define what workers see and answer](#team-leads-define-what-workers-see-and-answer)
- [Time tracking and process KPIs](#time-tracking-and-process-kpis)
- [Private process analysis (value stream analysis)](#private-process-analysis-value-stream-analysis)
- [Screenshots](#screenshots)
- [Architecture](#architecture)
- [Security](#security)
- [Quality](#quality)
- [Getting started](#getting-started)
- [Live demo and deployment](#live-demo-and-deployment)
- [Running inside a company and integration](#running-inside-a-company-and-integration)
- [Roadmap](#roadmap)
- [Author](#author)

---

## Problem statement

Commissioning a test bench is a chain of steps done by different teams: mechanics, electrics, measurement, software, testing and project management. In many teams this chain is coordinated with **Excel checklists, paper, e-mail and phone calls**:

| Pain point | Effect |
|---|---|
| **Media breaks**: results are written on paper, typed into Excel and sent by e-mail | Double work, typing errors, no single source of truth |
| **Invisible dependencies**: the next person does not know that their step can start | Waiting time between steps |
| **No transparency**: leads have to ask for the status of each bench | Status meetings and manual follow-ups |
| **Late failure detection**: nobody is actively alerted when a step fails | Delays spread to all following steps |
| **Notification overload** when everyone is informed about everything | Important messages are overlooked |

**Goal:** capture every result once, at the source; hand work over automatically to the right role; escalate only what is really urgent; and give every level the overview it needs.

## Solution

| Need | How the app solves it |
|---|---|
| Capture results without media breaks | The technician opens the task on a tablet or PC, ticks the checklist, enters a measured value and chooses **Done / Failure / Blocked** |
| Data quality at the source | "Done" is only possible when every checklist item is ticked; failures need a comment (Poka-Yoke) |
| Automatic handover | The process knows the dependencies (incl. **parallel steps**). When a step passes, only the role of the step that can now start is notified |
| Prioritised notifications | Urgent / Normal / Info, configurable by the department lead; inbox sorted by priority, oldest first |
| Act directly from a notification | A click opens the task with *What to do*, checklist and form |
| Transparency for every level | Central dashboard (all benches, KPIs, problems), team dashboard (per discipline, assign work), my tasks (technician) |
| Escalation | Ready tasks nobody starts within N hours are escalated automatically |
| Traceability | Every decision is written to an audit log |

## Roles and screens

| Role | Lands on | Can |
|---|---|---|
| **Department lead** (Leitung) | **Central dashboard** | See all test benches as a matrix with progress and release status, KPIs (in commissioning, released, problems, overdue, average lead time), problems, workload per team; create test benches; **set the notification rules**; manage users; read the audit log |
| **Team lead** (Teamleitung, per discipline) | **Team dashboard** | See problems, ready, running and upcoming steps of the own discipline; **assign** steps to team members (workload is shown); reopen a step; **edit what workers see and answer** for the own team's steps |
| **Technician** (Techniker/in) | **Shop-floor screen** (tablet: tap name + PIN) or *My tasks* | See only the one task that is next, follow the instructions, tick the checklist, enter measured values (checked automatically), report the result, pause, call for help |
| **Process analysis** (Prozessanalyse) | **Analysis workbook** | Private account of the thesis author: value stream mapping, Gemba notes, PDCA actions, KPIs before/after, target state – with full version history |

Every role has the **notification inbox** with a bell counter. Urgent messages also show a red banner on every page. The interface is available in **German and English** and works on phones, tablets and desktops.

### Commissioning process (demo configuration – an example for a brake / hydraulics test bench)

```mermaid
flowchart LR
    S01["S01 Mechanical set-up & hydraulics<br/>Mechanics"] --> S02["S02 Power supply & E-Stop<br/>Electrics"] --> S03["S03 CAN to brake ECU<br/>Electrics"]
    S03 --> S04["S04 Pressure sensor calibration<br/>Measurement"]
    S03 --> S05["S05 Software & ESP configuration<br/>Software"]
    S04 --> S06["S06 Leak test & reference run<br/>Testing"]
    S05 --> S06 --> S07["S07 Documentation & release<br/>Project mgmt."]
```

S04 and S05 run **in parallel**; S06 starts only when **both** are done. Steps, disciplines, instructions, checklists and **measured values with tolerances** (e.g. fitting torque 18–22 Nm, pressure drop 0–2 bar in 60 s) are configuration (`app/seed.py`), validated against unknown references and cycles. **The steps and tolerances in the demo are assumptions** and must be replaced with the real process from the value stream analysis.

## How notifications work

### Events and default rules

| Event | Default priority | Who is notified |
|---|---|---|
| Step **failed** | **Urgent** | Assignee, team lead of the step, department lead |
| Step **blocked** | **Urgent** | Assignee, team lead of the step, department lead |
| Task **can start** (all previous steps done) | Normal | The assignee – or the whole team of that step if nobody is assigned yet |
| Task **assigned** | Normal | The new assignee |
| Task **overdue** (ready, not started within N hours) | Normal | Assignee/team and team lead |
| **Next step delayed** (a previous step has a problem) | Info | The team of the next step |
| Step **done** | Info | Team lead |
| Test bench **finished** | Info | Department lead |
| **Help requested** (technician presses *Call for help*) | **Urgent** | Team lead of the step |

The department lead can change **priority (Urgent / Normal / Info / Off) and recipients for every event** on the *Notification rules* page, and set the escalation time. Changes are audit-logged.

### Ordering rule (what comes first)

1. **Unread before read.**
2. **Urgent before Normal before Info.**
3. **Within the same priority, the oldest message first (FIFO)**, so nothing waits forever behind newer messages.
4. **Info never interrupts:** it is not counted in the bell badge and stays visible in the dashboards.
5. **No self-notification:** whoever triggers an event is not notified about it.
6. **Auto-resolve:** when the work is done (task started, result reported, failure fixed), the matching notifications are closed for everybody.
7. **Escalation instead of noise:** only if a ready task is not started in time, the team lead is involved.

```mermaid
sequenceDiagram
    actor T1 as Technician Electrics
    participant App as Web app
    actor T2 as Technician Measurement
    actor T3 as Technician Software
    actor L as Team lead Electrics
    T1->>App: S03 Network & CAN → Done (checklist complete)
    App->>App: dependencies: S04 and S05 are now startable
    App-->>T2: Normal: "PS-21: you can start S04"
    App-->>T3: Normal: "PS-21: you can start S05"
    App-->>L: Info: "S03 done" (no badge)
    T2->>App: click notification → task form → Done
    App->>App: S06 still waits for S05 → no message
```

## Shop-floor mode for technicians

Built for people who have never used such software, on a shared tablet at the test bench:

1. **Sign in without typing:** tap your name tile, enter a 4–6 digit PIN on a large keypad. (Or scan the **QR code on the test bench** – it opens the sign-in and then directly the task for that bench.)
2. **One task, full screen:** bench, step, one sentence *what to do*, a big checklist – nothing else. Only the worker's own discipline and only tasks assigned to them or still unassigned.
3. **Measured values are checked automatically:** each value shows the allowed range and turns **green ✓** or **red ✗** while typing. *Done* is only possible when every checklist item is ticked and every value is inside its tolerance (Poka-Yoke) – the server enforces the same rule. Out-of-range values must be reported as a problem with a short comment.
4. **Pause / Continue** stops the clock (lunch, waiting for parts); the working time is shown live.
5. **Call for help** sends an Urgent message to the team lead (once per 10 minutes, no spam).
6. **New task? The tablet beeps, vibrates and shows it immediately** (checked every 10 s).
7. **Safety on a shared device:** automatic sign-out after 15 minutes without activity, *Done – sign out* button, PIN lockout after 5 wrong attempts, optional restriction to the factory network (`SHOPFLOOR_NETWORKS`).

| Tap your name | PIN | Value out of range → *Done* locked | All OK |
|---|---|---|---|
| ![Tiles](docs/images/shop-tiles.png) | ![PIN](docs/images/shop-pin.png) | ![Out of range](docs/images/shop-task-out-of-range.png) | ![OK](docs/images/shop-task-ok.png) |

Printable QR codes for every test bench (and for the tablet sign-in) are on the *QR codes* page.

## Team leads define what workers see and answer

On the page *Work steps* each team lead maintains the steps of their own team (the department lead can edit all):

- **What to do** – one short instruction (German, optional English).
- **Checklist** – up to 12 items; the worker ticks each one.
- **Worker inputs** – the answers the worker must give:
  - **Number** with unit and allowed range (e.g. *fitting torque 18–22 Nm*) – green/red while typing, *Done* locked outside the range,
  - **Text**, e.g. *software version* or *serial number* – required before *Done*.
- A **live preview** shows exactly what the worker will see on the tablet.
- Every save creates a **new version** with history (who, when). **Running work keeps the version it started with**; only tasks that have not started yet get the new version – a worker's checklist never changes in the middle of the work.

![Step editor with preview](docs/images/step-editor.png)

## Time tracking and process KPIs

For every task the app records **when it became ready, when it was started, paused and finished**. From this it calculates:

- **Waiting time** (ready → started) and **processing time** (started → done, minus pauses) per step,
- **lead time** per released test bench and the **flow ratio** (Flussgrad = processing ÷ lead time) – the core metrics of a value stream analysis.

The *KPIs* page (department lead, team leads, analyst) shows averages **per process step, not per person**; steps where people wait longer than they work are highlighted. Personal performance rankings are deliberately not part of the app (works council / GDPR).

![KPIs](docs/images/kpi.png)

## Private process analysis (value stream analysis)

A separate account with the role **Prozessanalyse** opens a workbook for the thesis author:

| Section | Content |
|---|---|
| Project & goal | Problem statement, scope (start/end of the process), goal and success criteria, stakeholders |
| Process mapping (current state) | One entry per step: role, people, input/output, medium, media break, processing and waiting time, parallel?, waste (TIMWOODS), what the next step needs |
| Gemba & interviews | Date, role (anonymous), place, pain point, quote, idea |
| Actions (PDCA) | Action, waste addressed, owner, due date, PDCA status, effect |
| KPIs before / after | Metric, unit, before, after, measurement method |
| Target state | Flow and handovers, standardisation, digitalisation, tool evaluation, open questions |

- **KPIs are calculated automatically** from the mapping (lead time, processing/waiting time, flow ratio, media breaks, most frequent waste) and shown next to the **times measured live in the app**.
- **Nothing is ever lost:** every save creates a new version (history per entry), *archive* instead of delete (restorable), and a **complete JSON export** including all versions.
- **Private:** only the analyst role can open it; in the public demo the account is hidden from the user list and cannot be reset or taken over. The account is created from environment variables (`ANALYST_USERNAME`, `ANALYST_PASSWORD`) – never stored in the repository.
- **Permanent storage:** use PostgreSQL (`DATABASE_URL`). Schema changes are applied with **Alembic migrations**, so updates never drop data. If the server runs without a permanent database, the analysis page shows a warning.

![Analysis](docs/images/analysis-overview.png)

## Screenshots

| Central dashboard (department lead) | Notification rules |
|---|---|
| ![Central dashboard](docs/images/app-central-dashboard.png) | ![Notification rules](docs/images/app-notification-rules.png) |

| Team dashboard (team lead) | My tasks · task form · inbox (phone) |
|---|---|
| ![Team dashboard](docs/images/app-team-dashboard.png) | ![Mobile](docs/images/app-mobile.png) |

## Architecture

```mermaid
flowchart LR
    B[Browser<br/>phone · tablet · PC] -->|HTTPS| W["Web layer<br/>app/web: routes, templates,<br/>CSRF, sessions, i18n"]
    W --> S["Use cases<br/>app/services: workflow,<br/>notify, auth, audit"]
    S --> D["Domain rules<br/>app/domain: process,<br/>notifications, roles<br/>(pure Python)"]
    S --> M["Data access<br/>SQLAlchemy models"]
    M --> DB[(PostgreSQL<br/>SQLite for demo)]
```

| Layer | Folder | Rule |
|---|---|---|
| Domain | `app/domain` | Pure business rules (dependencies, readiness, priorities, permission matrix). No framework imports, fully unit-tested |
| Use cases | `app/services` | One function per use case. **Checks permissions first**, changes state, emits notifications and writes the audit log in **one transaction** |
| Web | `app/web`, `app/templates`, `app/static` | Thin: parses input, calls a use case, renders HTML. Server-rendered pages, works without JavaScript |
| Data | `app/models.py`, `app/db.py` | SQLAlchemy 2. PostgreSQL in production, SQLite for the demo and tests |

**Tech stack:** Python 3.12 · FastAPI · SQLAlchemy 2 · Jinja2 · Argon2 · PostgreSQL · Docker · GitHub Actions. Design decisions are recorded in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md); a short user guide (DE/EN) is in [docs/USER_GUIDE.md](docs/USER_GUIDE.md).

```
app/
  domain/          pure rules: process.py, notifications.py, roles.py
  services/        use cases: workflow.py, notify.py, auth.py, audit.py
  web/             routes_*.py, deps.py (session, CSRF, render), security.py, i18n.py
  templates/       server-rendered pages (one per screen)
  static/          app.css, app.js (small progressive enhancements)
  seed.py          process configuration + fictional demo data
tests/             domain, workflow and web/security tests (pytest)
n8n/               earlier n8n prototype of the same process
docs/              architecture, user guide, screenshots
```

## Security

Summary (details in [SECURITY.md](SECURITY.md)):

- **Authentication:** Argon2id password hashing, server-side sessions (only a SHA-256 hash of the session token is stored), HttpOnly + SameSite cookies (Secure behind HTTPS), idle and absolute session timeout, forced password change for new users.
- **Brute-force protection:** login throttling per user and per IP; the same error for unknown user and wrong password (no user enumeration).
- **Authorisation:** one permission matrix (`app/domain/roles.py`) plus object-level checks in every use case (own discipline, own task). Hidden buttons are never the only protection.
- **Web security:** CSRF token on every form, strict Content-Security-Policy (no inline scripts or styles), `X-Frame-Options: DENY`, `nosniff`, HSTS behind HTTPS, no open redirects, autoescaped templates, no stack traces to the user, API docs disabled.
- **Supply chain:** pinned dependencies, `pip-audit` in CI (currently no known vulnerabilities), Dependabot, `ruff` security rules.
- **Container:** slim image, unprivileged user, health check, database not exposed to the host.
- **Privacy:** process KPIs, not personal surveillance; only fictional data in the demo.

## Quality

```bash
ruff check app tests        # lint incl. security rules
pytest -q                   # 137 tests: domain, workflow, shop floor, step editor, analysis, web/security, migrations, translations
pip-audit -r requirements.txt
```

The tests cover upgrading a database that already contains data, step versions and snapshots, text answers, measured-value tolerances, pause handling, PIN login with lockout and network restriction, the shop-floor flow, the QR redirect, help requests, the analysis history and its privacy, that the database migrations match the models, parallel steps and joins, who receives which notification (and who does not), priority ordering, rule changes, escalation, the full permission matrix, CSRF, login throttling, access to other people's data, security headers, open redirects and that every text exists in German and English. CI runs lint, tests, the dependency audit and the Docker build on every push.

## Getting started

### Docker (web app + PostgreSQL)

```bash
git clone https://github.com/abhisheklakhani-it/n8n-test-bench-commissioning-tracker.git
cd n8n-test-bench-commissioning-tracker
docker compose up --build            # http://localhost:8000  (other port: APP_PORT=8080 docker compose up)
# optional: also start the n8n automation layer on :5678
docker compose --profile n8n up --build
```

### Python

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.asgi:app --reload        # http://localhost:8000, SQLite in ./data
pytest -q
```

### Demo accounts

All demo accounts use the password `Demo-Pruefstand-2026!` (shown on the login page in demo mode; click a role to sign in). **Shop floor:** open `/werker` (or the big *Worker sign-in* button), tap a technician and enter the demo PIN `2468`.

| Role | Username |
|---|---|
| Department lead | `leitung` |
| Team lead Electrics | `tl.elektrik` (also `tl.mechanik`, `tl.messtechnik`, `tl.software`, `tl.pruefung`, `tl.projekt`) |
| Technician Electrics | `tech.elektrik`, `tech.elektrik2` |
| Technicians of other teams | `tech.mechanik`, `tech.messtechnik`, `tech.software`, `tech.pruefung`, `tech.projekt` |

### Configuration

| Variable | Default | Meaning |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./data/app.db` | PostgreSQL in production: `postgresql://user:pass@host:5432/db` |
| `DEMO_MODE` | `1` | Fictional seed data, demo banner, demo accounts on the login page, demo accounts protected |
| `DEMO_PASSWORD` | `Demo-Pruefstand-2026!` | Password of the fictional demo accounts |
| `COOKIE_SECURE` | `0` | Set `1` behind HTTPS |
| `SESSION_IDLE_MINUTES` / `SESSION_MAX_HOURS` | `480` / `12` | Session timeouts |
| `LOGIN_MAX_FAILURES` / `LOGIN_LOCK_MINUTES` | `5` / `10` | Login throttling |
| `FORWARDED_ALLOW_IPS` | `127.0.0.1` | Trusted reverse proxy addresses (Docker image) |
| `SHOPFLOOR_IDLE_MINUTES` | `15` | Automatic sign-out of tablet (PIN) sessions |
| `SHOPFLOOR_NETWORKS` | *(empty = any)* | Comma-separated CIDR ranges that may use the PIN sign-in, e.g. `10.0.0.0/8` |
| `ANALYST_USERNAME` / `ANALYST_PASSWORD` / `ANALYST_FULL_NAME` | *(empty)* | Creates the private process-analysis account once at start-up (never reset afterwards) |

## Live demo and deployment

**Permanent data:** set `DATABASE_URL` to a PostgreSQL database (e.g. a free Neon or Supabase database in the EU) in the Render dashboard; migrations run automatically on start. Without it the free instance uses SQLite on an ephemeral disk.

**Public demo:** **https://test-bench-commissioning.onrender.com** – sign in by clicking a role on the login page (fictional data; the demo resets when the free instance restarts, and the first request after a pause can take about a minute).

**One-click deployment** of your own demo on Render (free plan, Docker, Frankfurt region) with [`render.yaml`](render.yaml):

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/abhisheklakhani-it/n8n-test-bench-commissioning-tracker)

**For real use inside a company** the same container runs on internal infrastructure with PostgreSQL, HTTPS via the company reverse proxy, `DEMO_MODE=0`, and ideally single sign-on (Microsoft Entra ID) instead of local passwords. The process steps and notification channels (e.g. Microsoft Teams via the n8n layer or Power Automate) are configuration.

## Running inside a company and integration

The app is a standard container with PostgreSQL and no lock-in to a cloud, so it can run on **Microsoft Azure** (Container Apps / App Service + Azure Database for PostgreSQL + Key Vault), on an **internal Kubernetes/OpenShift** platform or on a **single lab server** behind the company reverse proxy – configuration only, no code change. Planned integrations: **Microsoft Entra ID** single sign-on, **Teams/Outlook** notifications (via the n8n layer or Power Automate), **SharePoint/Microsoft Lists** sync, a **Power BI** reporting view, and a **REST endpoint for test bench software** so measured values arrive without typing. Details, recommended order and what is needed from IT: [docs/INTEGRATION.md](docs/INTEGRATION.md).

## Roadmap

- [ ] Single sign-on with Microsoft Entra ID (OIDC); local passwords only as fallback
- [x] Step editor for team leads (instructions, checklist, inputs with tolerances, versions)
- [ ] Process structure editor (add steps, dependencies, templates per test bench type)
- [ ] Push channels: Microsoft Teams / e-mail for Urgent messages, daily digest for Info
- [ ] Attachments (photos, measurement files) per step
- [ ] Read measured values directly from the test bench (no typing) via the n8n layer or an API
- [ ] Offline mode for tablets with poor Wi-Fi
- [ ] KPI history: lead time per bench, waiting time at handovers, time to detect failures
- [ ] Integration with test bench networks and analysis tools via the n8n layer or REST API

## Author

**Abhishek Lakhani** · M.Sc. Automotive Software Engineering, TU Chemnitz · [GitHub](https://github.com/abhisheklakhani-it)

## License

[MIT](LICENSE) © 2026 Abhishek Lakhani
