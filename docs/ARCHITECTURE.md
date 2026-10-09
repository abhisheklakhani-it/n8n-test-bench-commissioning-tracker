# Architecture and design decisions

## Overview

A server-rendered Python web application in four layers:

1. **Domain** (`app/domain`): pure rules without framework imports – process dependencies and readiness (`process.py`), notification events, default rules and inbox ordering (`notifications.py`), roles and the permission matrix (`roles.py`).
2. **Use cases** (`app/services`): `workflow.py` (create bench, start, submit result, assign, reopen, overdue check), `notify.py` (rules → recipients → notifications, auto-resolve, inbox), `auth.py`, `audit.py`. Each use case checks permissions first and commits once.
3. **Web** (`app/web`, `app/templates`, `app/static`): thin routes, sessions, CSRF, security headers, German/English texts.
4. **Data** (`app/models.py`, `app/db.py`): SQLAlchemy 2; PostgreSQL in production, SQLite for demo and tests.

## Data model

```mermaid
erDiagram
    USER ||--o{ SESSION : has
    USER ||--o{ NOTIFICATION : receives
    USER ||--o{ TASK : "assigned to"
    BENCH ||--|{ TASK : "one per step"
    STEP_TEMPLATE ||--o{ TASK : "defines"
    TASK ||--o{ NOTIFICATION : "about"
    NOTIFICATION_RULE ||..o{ NOTIFICATION : "decides priority and recipients"
    USER ||--o{ AUDIT_LOG : "did"
```

- `STEP_TEMPLATE`: code, discipline, dependencies, instructions and checklist (DE/EN).
- `TASK`: one per bench and step; status `WAITING → READY → IN_PROGRESS → PASS | FAIL | BLOCKED`.
- `NOTIFICATION_RULE`: per event type the priority (Urgent/Normal/Info/Off) and recipient roles.
- `NOTIFICATION`: per recipient; `read_at` (seen) and `resolved_at` (work done).

## Task states

```mermaid
stateDiagram-v2
    [*] --> WAITING: bench created
    WAITING --> READY: all dependencies PASS
    READY --> IN_PROGRESS: start
    READY --> PASS: result
    IN_PROGRESS --> PASS: checklist complete
    IN_PROGRESS --> FAIL: comment required
    IN_PROGRESS --> BLOCKED: comment required
    FAIL --> PASS: fixed
    BLOCKED --> PASS: unblocked
    PASS --> IN_PROGRESS: reopen (lead, only if no following step started)
```

## Decisions

### ADR 1 – Custom web app instead of only n8n / low-code

*Context:* The first prototype in n8n proved the notification logic, but role-based accounts, per-role dashboards and forms per step are hard to maintain in a workflow tool.
*Decision:* A small Python web app owns users, process state, dashboards and rules. n8n (or Power Automate) remains an optional integration layer for channels such as Microsoft Teams and for test bench networks.
*Consequences:* Full control over usability, security and tests; one more service to operate. The evaluation of low-code platforms (Power Platform, n8n) remains part of the thesis; this app is a reference implementation for comparing them.

### ADR 2 – Server-rendered HTML, minimal JavaScript

*Decision:* Jinja2 templates, one small script for polling and convenience. Every page works without JavaScript.
*Consequences:* Simple, fast on shop-floor tablets, strict CSP possible, easy to maintain for a small team.

### ADR 3 – Roles, not individuals, as notification recipients

*Decision:* Rules address *assignee / team / team lead / department lead / next team*. The concrete people come from the user directory.
*Consequences:* Team changes do not require rule changes; scales to many teams.

### ADR 4 – Priority from process state, configurable by the department lead

*Decision:* Urgent = something is broken and blocks others; Normal = it is your turn; Info = never interrupts. Inbox order: unread, priority, oldest first. Overdue tasks escalate.
*Consequences:* Predictable behaviour, no notification flood, fairness (FIFO within a priority).

### ADR 5 – Process as validated configuration

*Decision:* Steps, dependencies and checklists live in data (`StepTemplate`), validated for unknown references and cycles.
*Consequences:* New bench types without code changes (UI editor on the roadmap).

### ADR 6 – PostgreSQL in production, SQLite for demo/tests

*Decision:* SQLAlchemy abstracts both; Docker Compose runs PostgreSQL.
*Consequences:* Zero-setup demo and fast tests; production-grade database where it matters. Alembic migrations are on the roadmap.

### ADR 7 – Security by default

*Decision:* Argon2id, server-side sessions, CSRF on every form, strict CSP, permission checks in use cases, audit log, pinned and audited dependencies, non-root container.
*Consequences:* Suitable as a basis for an internal tool; SSO (Entra ID) is the next step for company use.

### ADR 8 – Alembic migrations, data is never dropped

*Context:* The process analysis and real commissioning data must survive every update.
*Decision:* The schema is versioned with Alembic (`app/migrations`); the app upgrades to `head` on start. A test compares the migrations with the models, so a model change without a migration fails CI.
*Consequences:* Safe updates on PostgreSQL; every schema change needs a migration file.

### ADR 9 – Shop-floor mode with PIN sign-in

*Context:* Technicians share tablets at the test bench, wear gloves and have no software training.
*Decision:* Name tiles + PIN pad, one task per screen, automatic tolerance check, short session timeout, optional network restriction, QR codes per bench, polling for new tasks with sound and vibration.
*Consequences:* Very low entry barrier; PIN security relies on lockout, short sessions and the factory network – single sign-on or badge readers can replace it later.

### ADR 10 – Measured values with tolerances as configuration

*Decision:* Each step defines its measured values (unit, min, max). *Done* is impossible outside the tolerance (Poka-Yoke); the value is stored with the task.
*Consequences:* Data quality at the source; tolerances must come from the real test specifications.

### ADR 11 – Process KPIs, not personal performance

*Decision:* Waiting and processing times are aggregated per process step and per bench. No person-level rankings.
*Consequences:* Supports the value stream analysis and is compatible with works-council and GDPR requirements.

### ADR 12 – Private analysis workbook with revision history

*Decision:* A separate `ANALYST` role; entries are stored as JSON with a revision row for every create/update/archive/restore; archive instead of delete; JSON export.
*Consequences:* The thesis author's analysis cannot be lost by editing and is not visible to other roles.

### ADR 13 – Step specifications are versioned; running tasks use a snapshot

*Context:* Team leads must be able to change instructions, checklists and required inputs without disturbing work in progress.
*Decision:* Every edit creates a new step version with a revision row. When a task starts, the current specification is copied into the task (`spec_snapshot`). Screens and the server always read `task.spec` – the snapshot if present, otherwise the current version.
*Consequences:* No checklist changes "under the hands" of a worker; results remain interpretable because the snapshot records which version was used.
