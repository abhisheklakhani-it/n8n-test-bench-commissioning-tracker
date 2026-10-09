# Running the app inside a company and connecting it to existing systems

The application is a standard Docker container with a PostgreSQL database and no dependency on a specific cloud. It can therefore run wherever the company's IT allows containers, and it can be connected to existing systems step by step. **None of this has been tested against real Bosch systems** – the options below are the usual paths and must be agreed with the responsible IT, information security, data protection and the works council.

## 1. Where it can run

| Option | What is used | When it fits |
|---|---|---|
| **Microsoft Azure** (company subscription) | *Azure Container Apps* or *Azure App Service for Containers* for the app, *Azure Database for PostgreSQL – Flexible Server* for the data, *Azure Key Vault* for secrets, *Azure Container Registry* for the image | The company already runs internal web apps on Azure |
| **Internal Kubernetes / OpenShift** in the company data center | The same container image, a PostgreSQL service of the platform team, secrets from the platform vault | Test bench networks are isolated and must not talk to the internet |
| **A single internal server** (e.g. in the lab) | `docker compose up` (app + PostgreSQL) behind the company reverse proxy | Pilot in one lab with a few benches |

What changes for company operation (configuration only, no code change):

- `DEMO_MODE=0`, `COOKIE_SECURE=1`, `FORWARDED_ALLOW_IPS=<reverse proxy>`, `DATABASE_URL=<company PostgreSQL>`.
- `SHOPFLOOR_NETWORKS=<factory network ranges>` so the tablet PIN sign-in only works inside the plant.
- HTTPS certificate and DNS name from the company (e.g. `pruefstand.<internal domain>`).
- Backups of the database by the platform (point-in-time restore on Azure PostgreSQL).

Database: the data access uses SQLAlchemy and is tested with PostgreSQL and SQLite. Other databases that SQLAlchemy supports (e.g. Microsoft SQL Server / Azure SQL) are possible in principle but would need a test run of the migrations first.

## 2. Sign-in with company accounts (single sign-on)

Planned next step: **Microsoft Entra ID (Azure AD) via OpenID Connect**. Office users sign in with their company account; roles come from Entra groups (e.g. *Pruefstand-Leitung*, *Pruefstand-Teamleitung-Elektrik*). Local passwords remain only as a fallback. The tablet PIN sign-in can stay for the shop floor or be replaced by the company badge (RFID reader) if that is available.

## 3. Connecting to systems that already exist

| Goal | How |
|---|---|
| **Notifications in Microsoft Teams / Outlook** | Urgent and Normal messages forwarded by the n8n layer (`n8n/`) or Power Automate to a Teams channel or chat via Microsoft Graph |
| **Existing lists in SharePoint / Microsoft Lists** | One-way sync of benches and step results (Microsoft Graph API) so people who work with Lists today keep their view |
| **Reporting in Power BI** | Power BI reads a read-only reporting view in PostgreSQL (tasks, times, KPIs) – no data copy needed |
| **Test bench automation and measurement systems** | A small REST endpoint (planned) receives measured values or "step finished" events from the test bench software, so values are not typed at all; alternatively the n8n layer polls files or databases of the bench |
| **Engineering / project systems** (e.g. issue trackers) | Webhook on *Step failed / blocked* that creates a ticket with bench, step and comment |
| **Personnel and team structure** | Users and teams from Entra ID groups instead of local user management |

Recommended order: (1) pilot in one lab on an internal server or Azure with PostgreSQL, (2) Entra ID sign-in, (3) Teams notifications, (4) Power BI view, (5) direct connection of measured values from the benches.

## 4. What is needed from the company

- A target platform (Azure subscription or internal Kubernetes/server) and a PostgreSQL database.
- An Entra ID app registration for sign-in and – if Teams/SharePoint are used – Microsoft Graph permissions.
- Approval by information security (the app already follows: CSP, CSRF, Argon2, audit log, dependency audit in CI) and data protection; agreement with the works council on the KPIs (process times, no personal ranking).
- Access to the interfaces of the test bench / measurement systems for the direct value transfer.
