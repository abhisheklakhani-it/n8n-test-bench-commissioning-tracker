# Security

## Reporting a vulnerability

Please do not open a public issue. Contact the maintainer, Abhishek Lakhani, via GitHub (@abhisheklakhani-it).

## Measures

| Area | Measure | Where |
|---|---|---|
| Passwords | Argon2id hashing; minimum 12 characters with letters and digits, must not contain the username; new and reset accounts must change the password at the first sign-in | `app/services/auth.py` |
| Sessions | Random 256-bit token; only its SHA-256 hash is stored; HttpOnly, SameSite=Lax, Secure (with `COOKIE_SECURE=1`); idle timeout and absolute lifetime; password change ends all sessions; deactivating a user ends their sessions | `app/services/auth.py`, `app/web/routes_auth.py` |
| Shop-floor PIN | 4–6 digits, trivial PINs rejected, Argon2id hash; lockout per worker and per IP; PIN sessions expire after `SHOPFLOOR_IDLE_MINUTES` (15) without activity; optional restriction to factory networks (`SHOPFLOOR_NETWORKS`); PIN sign-in only for technicians | `app/services/auth.py`, `app/web/routes_shopfloor.py` |
| Private analysis | Only the `ANALYST` role can read or change it; account created from environment variables; in demo mode hidden from and protected against the public admin; never hard-deleted, full revision history, JSON export | `app/services/analysis.py` |
| Data durability | Alembic migrations (a test asserts that the migrations match the models); PostgreSQL recommended; warning in the UI when running without permanent storage | `app/migrations/`, `app/db.py` |
| Brute force | Throttling per username and per IP (`LOGIN_MAX_FAILURES` in `LOGIN_LOCK_MINUTES`); constant-time dummy hash for unknown users; same error message for unknown user and wrong password | `app/services/auth.py` |
| CSRF | Per-session token in every form, compared in constant time; login form uses a double-submit cookie | `app/web/deps.py` |
| Authorisation | Central permission matrix plus object-level checks (own discipline, own task) inside every use case; IDs of other users' notifications return 404 | `app/domain/roles.py`, `app/services/workflow.py` |
| Input validation | Allow-lists for results, roles, disciplines, priorities; length limits; username and bench-ID patterns; dependency graph validated (no cycles) | services and routes |
| Output | Jinja2 autoescaping; no user input in redirects except validated local paths | templates, `safe_next` |
| HTTP headers | Strict CSP (`default-src 'self'`, no inline script/style), `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy`, `Permissions-Policy`, COOP, HSTS behind HTTPS, `Cache-Control: no-store` for pages | `app/web/security.py` |
| Errors | Friendly error pages; details only in the server log; OpenAPI/docs endpoints disabled | `app/main.py` |
| Audit | Append-only log of sign-ins, results, assignments, rule and user changes | `app/services/audit.py` |
| Dependencies | Pinned versions, `pip-audit` and `ruff` security rules in CI, Dependabot | `.github/` |
| Container | `python:3.12-slim`, unprivileged user (uid 10001), only `/srv/data` writable, health check, database not published to the host | `Dockerfile`, `docker-compose.yml` |
| Demo | Fictional data only; demo accounts cannot be changed or locked out by visitors | `app/seed.py`, routes |

## Recommendations for production

- Run behind the company reverse proxy with HTTPS, set `COOKIE_SECURE=1` and `FORWARDED_ALLOW_IPS` to the proxy address.
- Use PostgreSQL with a secret password from the secret store; never commit `.env`.
- Set `DEMO_MODE=0`; create the first department-lead account and hand over one-time passwords in person.
- Restrict the PIN sign-in to the factory network with `SHOPFLOOR_NETWORKS` and use managed tablets.
- Prefer single sign-on (Microsoft Entra ID / OIDC); keep local passwords as fallback only.
- Agree on KPIs with the works council: the app measures processes, not individuals.
- Back up the database and test the restore regularly.
