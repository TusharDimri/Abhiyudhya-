# RNAF — Vocational Education Management Platform

A multi-tenant, role-based platform for organisations running NSQF vocational
labs in government schools. Built with **Flask + PostgreSQL + S3** on the backend
and **React (JavaScript) + Vite** on the frontend, deployable to AWS.

> **New here? Start with [RUNNING_LOCALLY.md](RUNNING_LOCALLY.md)** to get it
> running on your machine in about 15 minutes, then
> **[DEPLOYING_TO_AWS.md](DEPLOYING_TO_AWS.md)** when you're ready to go live.

---

## What it does

Six roles, each seeing only their slice of the data:

| Role | Sees / does |
|------|-------------|
| **Super Admin** | Everything, across all organisations |
| **Organisation Admin** | Everything inside one organisation |
| **District Manager** | Their assigned district(s) |
| **Principal** | Their school; **endorses** trainer attendance & reports |
| **Vocational Trainer** | Their lab(s): daily attendance, visits, lectures, students |
| **Student** | Their own internship diary |

It covers the full lifecycle: master data (schools, labs, sectors, job roles,
curriculum) → students (registration, verification, assessment) → daily
operations (attendance with 15 activity types, issues, field/industry visits,
guest lectures, equipment) → internship (employers, mappings, diaries, OJT/
placement) → dashboards, endorsement workflow, feedback, notifications, and a
full audit trail.

---

## Architecture at a glance

```
frontend/   React SPA (Vite). Config-driven: one DataTable + one form engine
            render every module from src/lib/modules.js.

backend/    Flask API (app factory + blueprints).
  app/models/     SQLAlchemy models for every module
  app/rbac/       the security core: roles, JWT auth, and the tenant/row
                  scoping engine (scope.py) that every query passes through
  app/api/        registry.py describes each module; resource.py turns each
                  entry into a scoped, audited, paginated REST resource
  app/services/   audit log + S3 pre-signed uploads
  app/seed.py     demo org + one login per role
```

### Why it's built this way (enterprise patterns)

- **Multi-tenancy:** every table carries `organisation_id`; the scoping engine
  derives scope from the logged-in user's JWT and **never trusts IDs from the
  client**. One place (`app/rbac/scope.py`) enforces isolation for all modules.
- **Config-driven CRUD:** modules are declared once (backend `registry.py`,
  frontend `modules.js`) instead of hand-coding 25 near-identical screens — so
  list/filter/sort/pagination + RBAC + audit behave identically everywhere.
- **Audited writes:** every create/update/delete records actor + before/after.
- **Soft deletes + status** on every record.
- **Tested where it matters most:** `backend/tests/test_rbac_isolation.py`
  proves one org/scope can't read another's data even by guessing IDs.

---

## Theme

Colours are taken from the RNAF logo — deep **navy** (`#12294B`) with a **gold**
(`#C39A4D`) accent on a white background — defined as CSS variables in
`frontend/src/theme/theme.css`. The UI is mobile-first and fully responsive
(the sidebar collapses to a drawer on small screens).

---

## Quick reference

| | Local | Production |
|-|-------|-----------|
| Start | `docker compose -f docker-compose.local.yml up -d` | `docker compose -f docker-compose.prod.yml up -d --build` |
| Frontend | `cd frontend && npm run dev` (port 5173) | served by Nginx in the `web` container |
| DB setup | `flask db upgrade` then `flask seed` | `flask db upgrade`, once |
| DB change | `flask db migrate -m "…"` then review + `flask db upgrade` | `flask db upgrade` on deploy |
| Tests | `docker compose -f docker-compose.local.yml exec backend pytest` | — |

Tests run against **PostgreSQL**, not SQLite — the same engine production uses.
They use a separate `rnaf_test` database, created automatically on first run,
so your development data is never touched.

Demo logins (local): `sa@rnaf.demo` … `student@rnaf.demo`, password `Password@123`.

### Database changes

The schema lives in `backend/migrations/versions/`, applied with
`flask db upgrade`. `0001_baseline` is the schema as it stood before migrations
were introduced — a database from that era is brought into the fold with a
one-off `flask db stamp 0001_baseline`. `tests/test_migrations.py` fails if a
model is changed without a migration to match, so the two cannot drift.

---

## Tech stack

**Backend:** Flask 3, SQLAlchemy 2, Flask-JWT-Extended, Flask-Migrate (Alembic),
Marshmallow, Celery + Redis, Gunicorn, boto3.
**Frontend:** React 18, Vite, React Router, TanStack Query, Axios.
**Infra:** Docker Compose, PostgreSQL, Redis, MinIO (local S3), Nginx; AWS EC2 +
RDS + S3 in production.
