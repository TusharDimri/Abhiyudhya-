# Vocational Education Management Application — Full Structure (v1)

Multi-tenant (multi-organisation) RBAC application for organisations that run NSQF vocational-education labs in government schools. Built from your structure + the ITI/USSP 544-school (548-lab) OPEX MoU, updated with your decisions.

**Legend**
- ➕ = Addition (from the MoU or best practice).
- ✅ = Decided this round.
- Roles: **SA** Super Admin · **OA** Organisation Admin · **DM** District Manager · **PR** Principal/Headmaster ✅ (new) · **VT** Vocational Trainer (students do **not** log in)

---

## PART 0 — FOUNDATIONS

### 0.1 Multi-tenancy (Organisation)
Everything is scoped to an Organisation (tenant). SA sees all; every other role is locked to one org.
- **Fields:** Org name, legal name, org code, logo, primary contact (name/email/phone), registered address, NSDC/SSC/NCVET affiliation cert number + validity date, status, created date.
- **Add/Edit:** SA. **View:** SA (all), OA (own, read-only).

### 0.2 Roles & access model (RBAC) ✅
1. **Super Admin** — creates orgs + Org Admins; full cross-org access.
2. **Organisation Admin** — full access inside one org.
3. **District Manager** — scoped to **one or more districts** ✅ (default one; higher roles can assign more later).
4. **Principal / Headmaster** ✅ — scoped to **their school**; views their school's data and **approves/endorses** VT attendance and monthly reports (MoU endorsing authority). Gets a login.
5. **Vocational Trainer** — scoped to their lab(s) + job role(s); daily operational entry, including their internship students' daily diaries.

**Students** — no login. Students are records registered and maintained by staff.

**Block** ✅ — no block-level login. Add **Block** as a field on schools purely for **filtering + reporting** (State → District → Block → School rollups).

### 0.3 Geographic + academic hierarchy
`Organisation → State → District → Block (field) → School (UDISE) → Lab → Class (9/10/11/12) → Section → Student`, with **Academic Year** on every operational record.
- **Academic Year master:** label, start, end, is-current. Drives promotion (9→10, 11→12) and year-scoped reporting.

### 0.4 Master / reference lists (admin-managed, fully editable) ✅
- **Sectors/Trades:** editable master list (not hardcoded) ✅ — seed with IT/ITeS, Automotive, Beauty & Wellness, Electronics & Hardware, Food Industry, Agriculture, Tourism & Hospitality, Aerospace & Aviation, Plumbing, etc.; admins add/edit freely.
- **Job Role master:** Job Role name, Sector, **QP Code**, **NSQF Level (1–4)**, class band (9–10 / 11–12).
- **Social category:** General, SC, ST, OBC, VJ, SBC, NT-B, NT-C, NT-D (editable list).
- **CWSN status:** Yes/No. Other fixed lists defined per module below (all editable master data).
- **NSQF ↔ grade mapping:** Level 1 = grade 9, Level 2 = grade 10, Level 3 = grade 11, Level 4 = grade 12.

### 0.5 Global enterprise standards (every list screen)
Server-side search, filters, sorting, pagination; URL-driven state; field-level RBAC (row scope + column/action per role); audit trail on every write; soft-delete + status; bulk CSV/Excel import (schools/students/job-roles); skeleton loaders on all lists/details; responsive + adaptive (mobile-first for VTs).

---

## PART 1 — CORE / MASTER DATA

### 1. School
- **Fields:** School name, **UDISE code** (unique), District, **Block** (field), labs in school, principal (link), full address, email, phone, status, enrolment count (derived).
- **Add/Edit:** SA, OA, DM (their district). **View:** SA, OA, DM (district), PR (own), VT (own, read-only).

### 2. Principal / Headmaster ✅ (also a user role)
- **Fields:** Full name, mobile, email, gender, years in school, date of joining, date of resignation, linked school, status, **login/user account** ✅.
- **Add/Edit:** SA, OA, DM (their district). **View:** SA, OA, DM (district), PR (self), VT (own school).
- **Role:** approves/endorses VT daily attendance + monthly reports for their school (Part 5).

### 3. Lab
- **Fields:** Lab name, Trade/Sector, School, **Job Role (Class 9–10)**, **Job Role (Class 11–12)**, Curriculum (Level 1–4), Sections per class, status, academic year of setup.
- **Add/Edit:** SA, OA, DM (district). **View:** SA, OA, DM (district), PR (own school), VT (own lab).
- **⚠️ Job-role correction:** keep **two** job-role slots. The MoU school list ("Job Role 1 / Job Role 2") and your own original spec show the 9–10 and 11–12 job roles can be **different** (e.g., IT/ITeS: *Domestic Data Entry Operator* for 9–10, *Junior Software Developer* for 11–12). Sometimes they're the **same** (Job Role 2 blank in the MoU list). So: model two slots; if a school uses the same role for both bands, fill both identically. This supports both cases with zero rework — safer than assuming one role for all four grades.

### 4. Curriculum & 9. Syllabus (merged into ONE canonical content tree) ✅
Canonical tree confirmed: **Sector → Job Role → NSQF Level (≈Grade) → Module (Employability / Vocational) → Unit → Session**.
- The 9–10 job role carries Levels 1–2; the 11–12 job role carries Levels 3–4 (if both bands use the same role, that one role spans Levels 1–4).
- "Curriculum" and "Syllabus" become two views of this same tree; Daily Attendance / Field Visit / Guest Lecture pick Module → Unit → Session from it.
- **Add/Edit:** SA, OA, DM, VT. **View:** all roles.

### 5. Vocational Trainer
- **Fields:** Name, School, Lab, Job role (1 per job role band), email, phone, date of joining, gender, date of exit, status (active/substitute/exited), qualification, login link.
- **Add/Edit:** SA, OA, DM (district). **View:** SA, OA, DM (district), PR (own school), VT (self).
- ➕ Substitute-teacher tracking (MoU allows a competent substitute to avoid penalty).

---

## PART 2 — STUDENT LIFECYCLE

### 6. Student Registration (Class 9 & 11 only)
- **Fields:** School, class, section, lab, job role, academic year, gender, first/middle/last name, email, DOB, father's/mother's/guardian's name, stream, first mobile, second mobile, WhatsApp number, CWSN (Yes/No), social category, date of enrolment, "had vocational stream in 9/10?" (Yes/No — Class 11 only), "continuing same trade?" (Yes/No — Class 11 only).
- ➕ Roll number; **student photo (optional)** ✅. **No Aadhaar** ✅ (not collected).
- **Add/Edit:** SA, OA, DM, VT (mostly VT). **View:** all (scoped); PR (own school).

### 7. Student Verification (9→10 and 11→12)
- **Fields:** same as registration, re-verified; verification status (pending/verified/rejected), verified-by (VT), verified-on, remarks.
- **Add/Edit (verify):** SA, OA, DM, VT (9/10 VT verifies 9→10; 11/12 VT verifies 11→12).
- **View:** all (scoped); PR (own school).
- ➕ Promotion/rollover on academic-year change (batch "promote" tied to Academic Year master).

### 8. All Students (directory)
- List by job role/lab/class/section/school/block/district/academic year. Role-scoped columns + rows. Full search/filter/pagination + shareable URL state.
- **View:** all (scoped). **Edit:** via scope, routes to registration record.

### 10. Assessment / Marks / Certification ✅ (kept)
- **Fields:** Student, academic year, class, job role, NSQF level, assessment type (internal/continuous/year-end board), name, date, max marks, marks obtained, result (pass/fail), level-certification status (L1–4), certificate number, remarks, evidence upload.
- **Add/Edit:** VT (internal/continuous), OA/DM (board/level), SA. **View:** all (scoped); PR (own school).

---

## PART 3 — DAILY OPERATIONS (Vocational Trainer)

### 11. Daily Attendance
- **Common:** Date; day type = Working day / On leave (→ reason) / Holiday-Off. For a Working day: school, lab, job role, class, section(s), **Activity type**:
  - **a. Teaching Vocational Education:** class taught, section taught, theory/practical, class type (regular/revision/online/community), duration (mins), module (Employability/Vocational), unit, session, class picture, lesson-plan picture, **student attendance** (marks the class+section list).
  - **b. Visit to Industry:** industry name, contact person, phone, details.
  - **c. Visit to Educational Institution:** institute name, contact person, phone, details.
  - **d. On-Job Training Coordination:** activity type (Exploration Industry Visit / Industry Visit For Supporting Students Placed / Orientation of Students / Other Coordination Work), details.
  - **e. Parent Teachers Meeting:** parents count, details.
  - **f. Community Home Visit:** parents count, details.
  - **g. School / Event Celebration:** details.
  - **h. Teaching Non-Vocational Subject:** other class details, duration (mins).
  - **i. Work Assigned by Headmaster:** details.
  - **j. Assignment from Vocational Department:** assignment number, details, photo.
  - **k. School Exam Duty:** details.
  - **l. Assessor in Other School for Exam:** school name, UDISE, class, boys present, girls present, exam details.
  - **m. Training of Teacher/Trainer:** type (VTP / Samagra Shiksha / Other Training Programme), details.
  - **n. Other Work:** details.
  - ➕ **o. Guidance & Counselling** (MoU: min. 1/year) — session details, students count.
- **Add/Edit:** VT. **View:** VT (own), PR (own school, + **approve**), DM (district), OA, SA.
- ➕ Derived: VT monthly attendance % + classes-conducted count (for dashboards).

### 12. VT Issue Reporting
- **Fields:** Trainer, lab, job role, academic year, reporting date, **Main issue** (Guest Lecture/Field Visit · Lab–Room/Infrastructure · Payment-Expense-Reimbursement · Syllabus/Text Book & Lesson Plan · Other) with dependent **Sub-issue** lists (as in your original spec), Students affected (all/some/not applicable), number affected, details.
- ➕ Workflow: status (open/in-progress/resolved), assigned-to, resolution note, resolved-on.
- **Add:** VT. **View:** VT (own), PR (own school), DM (action), OA, SA.

### 13. Field / Industry Visit Conducted
- **Fields:** School, lab, job role, class, section(s), academic year, reporting date, purpose, activities, module, units covered, sessions covered, organisation, address, distance (km), picture, contact person/mobile/email/designation, "more Field Visits?" (Y/N), "OJT/Internship interest?" (Y/N), organisation feedback, remarks/student feedback, **students present** (mark attendance).
- **Add:** VT. **View:** VT (own), PR (own school), DM (district), OA, SA.

### 14. Guest Lecture Conducted
- **Fields:** School, lab, job role, class, section(s), academic year, reporting date, type (paid/unpaid), topic, duration (mins), module, units, sessions, methodology (Presentation/Interactive/Role-play/Demonstration/Video screening & discussion/Online/Other), photo, lecturer name/qualification/phone/email/work experience/address, work status (job/self-employed), lecturer photo, remarks/student feedback.
- **Add:** VT. **View:** VT (own), PR (own school), DM (district), OA, SA.

### 15. Lab Equipment Details (+ maintenance log ➕)
- **Fields:** School, academic year, lab, receiving status (Y/N), receipt date, equipment status (working/partially/not working), raw material availability, raw material fund status (Y/N), details.
- ➕ Maintenance log: date, issue, action, **cost incurred**, downtime/uptime, resolved-by (MoU requires logged repairs with cost).
- **Add/Edit:** SA, OA, DM (district), VT (own lab). **View:** + PR (own school).

---

## PART 4 — INTERNSHIP / OJT / PLACEMENT

### 16. Employer Details
- **Fields:** First/last name, gender, org name, business description, employee count (0-1/2-5/6-10/11-20/20+), year of foundation, lab/sector (from org's list), is active (Y/N); **office address:** branch name, branch address, POC mobile, POC email, state, district, pincode.
- **Add/Edit:** SA, OA, DM (district), VT. **View:** + PR (own school).

### 17. Employer–Student Mapping
- **Fields:** Student, employer, job role, academic year, start date, end date, status (ongoing/completed), OJT hours target/logged.
- **Add/Edit:** VT (their students), DM (district). **View:** SA, OA, DM (district), PR (own school), VT (their students).

### 18. Daily Diaries
- **Fields:** Date, student, school, lab, class, section, employer, learning, hours spent, photo.
- **Add/Edit:** VT (their students). **View:** SA, OA, DM (district), PR (own school), VT (their students).

### 19. OJT / Apprenticeship / Placement ✅ (kept as module)
- **Fields:** Student, academic year, job role, OJT hours logged vs 50 required, OJT establishment, dates; apprenticeship interested/placed (Y/N) + employer; placement interested/placed (Y/N), placement letter date, employer, letter upload.
- **Add/Edit:** VT (their students), DM (district). **View:** all (scoped); PR (own school).

---

## PART 5 — CROSS-CUTTING / ENTERPRISE

### 20. Dashboards & Reports ➕
Role-scoped dashboards with school → block → district → state rollups, filterable by academic year/sector/job role; SLA target-vs-actual (VT attendance, classes conducted, guest lectures, industry visits, OJT, pass rate, apprenticeship/placement %); export weekly/monthly (PDF/Excel).

### 21. Endorsement / Approval Workflow ✅
Principal (PR) logs in and **endorses** VT daily attendance + monthly reports for their school (submitted → endorsed / returned). DM/OA can see endorsement status.

### 22. Feedback Module ➕
Feedback from students, teachers, inspection teams: source, subject, rating, comments, date, linked school/lab. **Add:** relevant role + PR. **View:** DM/OA/SA/PR.

### 23. VT Training & Leave (consolidated view) ➕
Aggregate VT attendance %, leaves, trainings (induction + 5-day/40-hr annual), lectures delivered (from attendance data) into a VT profile.

### 24. Payments / Billing / Penalties ❌ OUT OF SCOPE ✅
Not built in this app. Attendance and activity data are still captured (you report them onward), but no billing/penalty module here.

### 25. Notifications & Audit ➕
Notifications (issue raised, verification pending, endorsement pending, SLA warnings). Global audit log (who/when/before-after) — MoU allows inspection anytime.

---

## RBAC QUICK MATRIX  (A = Add/Edit · V = View · Ap = Approve · — = none; scope in parentheses)

| # | Feature | SA | OA | DM | PR | VT |
|---|---------|----|----|----|----|----|
| 1 | School | A/V | A/V | A/V (dist) | V (own) | V (own) |
| 2 | Principal | A/V | A/V | A/V (dist) | V (self) | V (school) |
| 3 | Lab | A/V | A/V | A/V (dist) | V (school) | V (own) |
| 4 | Curriculum/Syllabus | A/V | A/V | A/V | V | A/V |
| 5 | Vocational Trainer | A/V | A/V | A/V (dist) | V (school) | V (self) |
| 6 | Student Registration | A/V | A/V | A/V | V (school) | A/V (labs) |
| 7 | Student Verification | A/V | A/V | A/V | V (school) | A/V (labs) |
| 8 | All Students | V/A | V/A | V/A (dist) | V (school) | V/A (labs) |
| 10 | Assessment/Marks | A/V | A/V | A/V | V (school) | A/V |
| 11 | Daily Attendance | V | V | V (dist) | V+**Ap** (school) | A/V (own) |
| 12 | Issue Reporting | V | V | V/act (dist) | V (school) | A/V (own) |
| 13 | Field/Industry Visit | V | V | V (dist) | V (school) | A/V (own) |
| 14 | Guest Lecture | V | V | V (dist) | V (school) | A/V (own) |
| 15 | Lab Equipment | A/V | A/V | A/V (dist) | V (school) | A/V (lab) |
| 16 | Employer | A/V | A/V | A/V (dist) | V (school) | A/V |
| 17 | Employer–Student Map | A/V | A/V | A/V (dist) | V (school) | A/V (students) |
| 18 | Daily Diaries | V | V | V (dist) | V (school) | A/V (students) |
| 19 | OJT/Apprenticeship/Placement | A/V | A/V | A/V (dist) | V (school) | A/V (students) |
| 20 | Dashboards & Reports | V (all) | V (org) | V (dist/block) | V (school) | V (lab) |
| 21 | Endorsement | V | A/V | A/V | **Ap** (school) | submit |
| 22 | Feedback | V | V | V/A | A/V (school) | A |

---

## PART 6 — TECHNICAL ARCHITECTURE (confirmed stack)

Stack: React SPA · Flask REST API · PostgreSQL · S3 · AWS. All four fit a multi-tenant RBAC system with heavy list/filter/pagination.

**6.1 Multi-tenancy** — shared database + shared schema, `organisation_id` on every tenant-scoped table (cheapest; scales to many orgs on one DB). Central query layer enforces tenant + role scope; optional Postgres RLS as defense-in-depth. Composite indexes on the columns you filter/sort (organisation_id, district_id, block, school_id, lab_id, academic_year, date).

**6.2 Backend (Flask)** — app factory + blueprints per module; SQLAlchemy + Alembic; Marshmallow/Pydantic validation. Auth: JWT (short-lived access + refresh); RBAC via policy decorators. Run under Gunicorn (multiple workers) behind Nginx. Flask is synchronous, so concurrency comes from worker/thread count + DB connection pooling, sized for your actual load (Part 7.9). RDS Proxy/PgBouncer is a documented future addition (Part 7.12) if connection counts ever become a bottleneck — not needed at today's scale.

**6.3 Pagination & list performance** — cursor/keyset pagination on big tables (attendance, students, diaries) to stay fast as data grows; OFFSET fine for smaller admin lists. All filters/sort/page in URL query params.

**6.4 Frontend (React)** — TanStack Query for server state (caching, background refetch, skeleton/loading states); TanStack Table for server-side sort/filter/paginate; React Router search params for URL state; component library (shadcn/ui or MUI); skeleton loaders everywhere; responsive/adaptive, mobile-first for VTs. Build static → served from the EC2 instance's Nginx, or S3 + CloudFront (optional, cheap, faster) — see Part 7.9.

**6.5 Media / storage (S3)** — images/uploads to S3 via **pre-signed URLs** (upload/download direct to S3, not through Flask — saves bandwidth/CPU on the single instance); lifecycle rules to cheaper storage tiers for old media.

**6.6 Async jobs** — Celery + Redis (both co-located on the production EC2 instance for now — confirmed, see Part 7.9) for bulk imports, report generation, notifications, and outbound webhooks with retries; scheduled jobs (nightly rollups, promotion reminders, SLA alerts) via Celery beat.

**6.7 Caching** — Redis (self-hosted in Docker on the same EC2 instance for now) for hot reads (dashboards, reference lists) and as the Celery broker. Moving to a managed ElastiCache instance is a documented future step (Part 7.12), only needed once you run more than one app instance.

**6.8 Deployment — CONFIRMED ✅** — Single EC2 instance running Docker Compose, RDS PostgreSQL (Single-AZ), S3 for files, no ALB, no NAT Gateway, no ECS/Fargate. Full detail, reasoning, and cost table in **Part 7.9/7.10**. The earlier ECS Fargate / Multi-AZ / load-balanced design is kept in this document only as a **documented future scaling reference** (Part 7.12) — it is not part of the current build.

**6.9 Observability & safety** — CloudWatch logs/metrics/alarms + health checks; structured logging with org/user context; full audit trail; automated RDS backups; EC2 auto-recovery (Part 7.11).

---

## PART 7 — DEVELOPMENT & DEPLOYMENT PLAN
**Confirmed for this build: one Local development environment + one Production environment (single EC2 + RDS + S3). No staging environment for now.**

### 7.0 "Can Flask do this properly?" — Yes, with the right shape around it
Flask is a micro-framework — it doesn't hand you RBAC, multi-tenancy, or scaling for free, but nothing about this application needs a bigger framework. This is a CRUD-heavy, moderately-trafficked, mostly business-hours government-education workload (hundreds of VTs/DMs entering data, not a real-time/high-concurrency consumer app). What actually determines whether it's "done properly" is architecture, not framework: correct multi-tenant data isolation, connection handling, pagination on big tables, a real CI/CD pipeline, and tests around RBAC. Flask + SQLAlchemy + Alembic + Gunicorn, run as described below, comfortably serves this load. The one Flask-specific thing to respect: Flask is synchronous, so concurrency comes from **process/thread count**, not async code — a sizing decision (7.10), not a rewrite decision.

### 7.1 Repository structure (monorepo)
One repo, two top-level apps, one CI/CD pipeline — simplest to keep in sync for a small-team build.
```
repo/
├── backend/
│   ├── app/
│   │   ├── __init__.py            # app factory
│   │   ├── extensions.py          # db, jwt, limiter, etc.
│   │   ├── models/                # SQLAlchemy models, one file per domain
│   │   ├── schemas/                # Marshmallow/Pydantic validation + serialization
│   │   ├── api/                   # blueprints: schools, labs, students, attendance...
│   │   ├── services/               # business logic (promotion, scoping, SLA calcs)
│   │   ├── rbac/                   # role + scope decorators, policy helpers
│   │   ├── tasks/                  # Celery tasks (reports, notifications, webhooks)
│   │   └── utils/
│   ├── migrations/                 # Alembic
│   ├── tests/                      # pytest, mirrors app/ structure
│   ├── Dockerfile                  # multi-stage: dev target + production target
│   ├── requirements.txt
│   └── .env.example                # committed template; real .env is gitignored
├── frontend/
│   ├── src/
│   │   ├── features/               # one folder per module (schools, students, attendance...)
│   │   ├── components/             # shared UI incl. the list/filter/pagination pattern
│   │   ├── lib/                    # api client, query client, auth
│   │   ├── routes/
│   │   └── hooks/
│   ├── Dockerfile                  # optional, for containerized dev parity
│   └── package.json
├── docker-compose.local.yml         # local dev stack: postgres, redis, minio, backend, worker
├── docker-compose.prod.yml          # production stack: nginx, backend, redis, worker (RDS/S3 are external AWS services, not containers)
└── .github/workflows/               # CI/CD
```

### 7.2 Development approach: build in vertical slices, not "all backend then all frontend"
For each module, build backend model → API → tests, then the matching frontend list/detail/form together, before moving to the next module. This keeps the list/filter/pagination pattern consistent everywhere and surfaces RBAC bugs immediately (you're using the UI, not just Postman). Build the pattern once on an easy module (e.g., School), then repeat it for every other module.

### 7.3 Phased roadmap
| Phase | Scope | Why this order |
|---|---|---|
| **0. Foundations** | Repo scaffold; `docker-compose.local.yml` (Postgres, Redis, MinIO, backend, worker); CI skeleton; base AWS infra (EC2, RDS, S3 — single production environment, no staging); Organisation model; auth (JWT); RBAC + tenant-scope decorators; React app shell + routing + auth; the reusable **list/filter/pagination** component pattern | Everything else depends on auth + scoping + the list pattern existing correctly |
| **1. Master data** | Organisation, State/District/Block, School (+UDISE), Principal, Lab, Sector/Job Role/NSQF master lists, Curriculum/Syllabus tree, Academic Year | No operational data can exist without these |
| **2. People & student lifecycle** | Vocational Trainer, Principal accounts, Student Registration, Verification + promotion/rollover, All-Students directory | Needed before any daily-operations module (they all reference students/VTs) |
| **3. Daily operations** | Daily Attendance (all activity-type branches), VT Issue Reporting, Field/Industry Visit, Guest Lecture, Lab Equipment + maintenance log | The bulk of day-to-day VT usage; biggest module, build attendance first since others reuse its patterns |
| **4. Internship** | Employer Details, Employer–Student Mapping, Daily Diaries, OJT/Apprenticeship/Placement | Depends on students + VT existing |
| **5. Assessment/Certification** | Marks, results, NSQF level certification | Depends on students + curriculum |
| **6. Cross-cutting** | Dashboards/reports with rollups, Endorsement workflow (Principal approves), Feedback module, Notifications, Audit log UI | Needs all operational data to exist first to be meaningful |
| **7. Hardening** | Manual/exploratory testing, security review (esp. tenant-isolation tests), accessibility pass, UAT with real VTs/DMs, bug fixing, apply Part 7.11 reliability hardening | Before real users touch it |
| **8. Go-live** | Production deploy (Part 7.9), monitoring/alerting live, runbooks, handover/training | — |

### 7.4 Environments — CONFIRMED ✅: Local + Production only
- **Local:** Docker Compose on your own machine — Postgres, Redis, MinIO (S3-compatible, so you don't need real AWS credentials to test file uploads), backend, Celery worker. Full detail in 7.5.
- **Production:** the single EC2 + RDS + S3 setup, detailed in 7.9. No separate staging environment for now — see 7.6 for how CI/CD compensates for that.

### 7.5 Local development setup (detailed)
**Prerequisites:** Docker Desktop (or Docker Engine + Compose plugin on Linux), Git, Node.js LTS, Python 3.11+ (only needed if you ever run the backend outside Docker), a code editor.

**What runs locally, via `docker-compose.local.yml`:**
- `postgres` — Postgres 16 container, local-only credentials, volume-mounted so data survives restarts, exposed on `localhost:5432`.
- `redis` — Redis container for the Celery broker + cache, `localhost:6379`.
- `minio` — an S3-compatible storage container, so file-upload features work locally without touching real AWS or costing anything; swapped for the real S3 bucket via an environment variable when deploying.
- `backend` — built from `backend/Dockerfile`'s **dev target**, runs Flask in debug/reload mode, the `backend/` folder is mounted as a volume so code edits reload instantly, config comes from `backend/.env` (copied from the committed `.env.example` and filled with local values — the real `.env` is gitignored, never committed).
- `celery-worker` — same image as backend, runs the Celery worker process against the local Redis.

**Frontend:** runs via `npm run dev` (Vite dev server) directly on your machine for the fastest hot-reload, proxying `/api` requests to the backend container's exposed port. It can also be containerized later for full environment parity if you prefer.

**First-time setup steps** (this becomes your `README.md`):
1. `git clone` the repo.
2. `cp backend/.env.example backend/.env` and fill in local values (DB URL, Redis URL, JWT secret, MinIO config).
3. `docker compose -f docker-compose.local.yml up -d postgres redis minio`
4. `docker compose -f docker-compose.local.yml run --rm backend alembic upgrade head` — applies all database migrations.
5. `docker compose -f docker-compose.local.yml run --rm backend python -m app.seed` — a seed script that creates a demo Organisation with a couple of Schools/Labs and one login per role, so you have real data to click through from day one instead of empty screens.
6. `docker compose -f docker-compose.local.yml up backend celery-worker`
7. `cd frontend && npm install && npm run dev`
8. App now runs at `http://localhost:5173` (frontend) talking to `http://localhost:5000` (backend API).

**Local/production parity:** the same backend Dockerfile builds both the dev target (used locally) and the production target (used on EC2) via Docker's multi-stage builds, so what you test locally is structurally the same code path that runs in production — only the surrounding services differ (MinIO ↔ real S3, no Nginx/TLS locally, `localhost` ↔ your real domain).

**Running tests locally:** `docker compose -f docker-compose.local.yml run --rm backend pytest` runs the full backend test suite (including the RBAC/tenant-isolation suite, Part 7.7) against a throwaway test database.

### 7.6 CI/CD pipeline — CONFIRMED ✅: no staging, so tests + a deliberate manual production deploy do the safety work
Since there's no staging environment, the pipeline relies more heavily on automated tests at the PR stage and a deliberate (not automatic) production deploy step, rather than a staging soak period:
- **On every pull request:** GitHub Actions runs lint (ruff/black for Python, eslint/prettier for the frontend) → backend unit + integration tests via pytest, run against a throwaway Postgres service container spun up inside the CI job → the **tenant-isolation RBAC test suite** specifically (7.7) → frontend build check. A PR cannot merge if any step fails.
- **On merge to `main`:** build the backend production Docker image and the frontend static bundle → push the backend image to Amazon ECR (small free tier, negligible cost at this scale) → **stop — do not auto-deploy to production.**
- **Deploying to production is a deliberate, separate step** — a manual `workflow_dispatch` trigger (a button you click in GitHub Actions) or a git tag (e.g., `v1.2.0`) — run only when you're confident in what merged. This manual gate is what replaces a staging environment's safety net at this scale.
- **The deploy workflow itself:** runs Alembic migrations against the production database first, as a one-off step (so schema and code are never mismatched mid-deploy) → connects to the EC2 instance (via a deploy-only SSH key, or AWS SSM Run Command — no broad SSH access) → runs `docker compose pull && docker compose up -d`, which restarts only the changed containers → hits a `/health` endpoint as a smoke test → if that fails, you're alerted immediately and can redeploy the previous image tag by hand as a rollback.
- **Frontend deploy:** static bundle synced to S3 and the CloudFront cache invalidated (if CloudFront is in use), or simply copied into the directory Nginx serves on the EC2 instance (if not).
- If you ever want a staging environment back, it's a config addition, not a rebuild — repeat the same production setup on a second, smaller/cheaper EC2 instance.

### 7.7 Testing strategy (RBAC is the highest-risk area — test it hardest)
- **Backend:** pytest + factory_boy for test data. Unit tests per service function; integration tests per API endpoint. A dedicated **tenant-isolation test suite**: for every list/detail/write endpoint, assert a user from Org A / District X / Lab Y can never read or write Org B / District Z / Lab W data, even by guessing IDs. This one suite is what substitutes for a staging soak period given there's no staging environment (7.6) — keep it strict.
- **Frontend:** component tests for the shared list/filter/pagination component (built once, reused everywhere) + Playwright/Cypress end-to-end tests for a handful of critical flows (login, register a student, mark attendance, raise an issue, principal endorsement).
- **Migrations:** every Alembic migration reviewed for reversibility; test migrations locally first against a restored copy of the production database before applying to production.

### 7.8 Security & RBAC implementation pattern
- Central `@require_role(...)` decorator + a `scoped_query()` helper that **derives** organisation/district/school/lab scope from the authenticated user's JWT — never trusts an org/school/lab ID sent by the client. Every query for tenant-scoped data goes through this helper, so scoping logic lives in one place, not copy-pasted per endpoint.
- JWT short-lived access token + refresh token; refresh rotation; rate-limit auth endpoints (Flask-Limiter) against brute force.
- Secrets (DB credentials, JWT signing key) in **AWS Secrets Manager**, pulled onto the EC2 instance at deploy time into environment variables — never committed to the repo, never hardcoded.
- All input validated against Marshmallow/Pydantic schemas server-side (never trust client-side validation alone).
- Audit middleware logs actor, action, entity, before/after diff, timestamp on every write — satisfies the MoU's "may inspect records anytime" clause.
- HTTPS everywhere — Let's Encrypt/Certbot on Nginx for the app domain (free, auto-renewing); ACM certificate on CloudFront if/when you use it for the frontend. S3 buckets private, access only via pre-signed URLs.
- EC2 access via AWS Systems Manager Session Manager rather than an open SSH port where possible; if SSH is used, restrict it to your IP and a deploy-only key for CI/CD.

### 7.9 Production deployment architecture — CONFIRMED ✅: single EC2 + RDS + S3
**Load reality check:** ~1,000 total users, ~30% (≈300) concurrent at peak, active only minutes-to-hours per day — light, bursty traffic, not sustained high concurrency. A single well-sized instance handles this comfortably, and every service below is chosen to avoid AWS's biggest *fixed* costs (Application Load Balancer, NAT Gateway, Multi-AZ, ElastiCache) that aren't needed at this scale.

**What runs where:**
- **One EC2 instance** (start: `t3.medium`, 2 vCPU / 4GB — burstable, cheap, easy to resize) in a **public subnet** with a **security group** (AWS's firewall) allowing only ports 80/443 in, and no open SSH port (AWS Systems Manager Session Manager instead). Runs **Docker Compose** (`docker-compose.prod.yml`) with:
  - **Nginx** — reverse proxy; terminates HTTPS via a free Let's Encrypt certificate (Certbot); serves the built React app's static files directly.
  - **Flask app, run by Gunicorn** — the API itself.
  - **Redis** — Celery broker + cache, co-located on this same instance for now.
  - **Celery worker** — background jobs (bulk imports, report generation, notifications).
- **RDS PostgreSQL, Single-AZ** (start: `db.t4g.small`, 2 vCPU / 2GB) — managed database (AWS handles patching, automated backups, point-in-time recovery), in its own security group that only accepts connections from the EC2 instance's security group.
- **S3 bucket** — stores uploaded photos/documents; browser uploads/downloads go **directly** to/from S3 via short-lived pre-signed URLs generated by Flask, so files never pass through (and slow down) the EC2 instance.
- **CloudFront (optional)** in front of S3 for the frontend's static assets — faster loads, less load on the EC2 box; skippable at first, addable later with zero app changes.
- **Route53 (optional, ~$0.50/mo)** for DNS, or point your existing domain registrar at the instance's **Elastic IP** (a static IP that survives restarts).
- **IAM Role** attached to the EC2 instance so Flask can talk to S3 without any AWS keys stored in code or config.
- **CloudWatch** for logs/metrics/alarms (mostly within the free tier at this scale).

**Deploy flow:** see 7.6 — GitHub Actions builds and pushes the image on merge, then a deliberate manual step deploys it to this instance via `docker compose pull && docker compose up -d`.

### 7.10 Realistic cost ballpark (current AWS on-demand rates, us-east-1)
Estimates from current AWS rates; actual cost shifts with real traffic — check the AWS Pricing Calculator before committing, and re-check after your first month's actual bill.

| Component | What it is | Starter size | Est. monthly |
|---|---|---|---|
| EC2 instance | app server | `t3.medium` (2 vCPU/4GB) | ~$30 |
| RDS PostgreSQL | managed database | `db.t4g.small` Single-AZ, 2 vCPU/2GB | ~$25 |
| RDS storage + backups | DB disk + automated snapshots | 20–30GB gp3 | ~$3 |
| EC2 root volume | app server disk | 20–30GB gp3 | ~$2–3 |
| S3 | file storage (photos/docs) | light usage | ~$2–5 |
| CloudFront (optional) | CDN for the frontend | light usage | ~$1–3 |
| Data transfer out | traffic leaving AWS | first ~100GB often free-tier | ~$3–10 |
| Route53 (optional) | DNS | 1 hosted zone | ~$0.50 |
| CloudWatch | logs/metrics/alarms | light usage, mostly free tier | ~$0–5 |
| **Total** | | | **≈ $70–95/month** |

This leaves most of your $100–500 budget as headroom — for a domain name, error tracking (Sentry), or simply margin as usage grows.

### 7.11 Reliability & self-healing (build this in from day one — cheap, high value)
Two different things get called "reliability" — worth keeping separate:
- **Application robustness** (won't break from bugs/bad input) comes from code quality: the RBAC/tenant-isolation test suite (7.7), input validation, structured error handling and logging. This matters regardless of infrastructure.
- **Infrastructure resilience** (recovers from a crashed process, a rebooted instance, or an AWS hardware hiccup without a human noticing) — close this gap on the single instance with:
  1. `restart: unless-stopped` on every container in `docker-compose.prod.yml` — a crashed container restarts itself within seconds.
  2. **EC2 auto-recovery** — a CloudWatch alarm (`StatusCheckFailed_System` → "Recover this instance") that automatically reboots/migrates the instance if AWS detects underlying hardware failure. Free beyond a negligible CloudWatch cost; zero manual action required.
  3. Docker service enabled on boot, so a reboot brings the whole stack back without needing SSH/SSM access.
  4. A free external uptime monitor (e.g., UptimeRobot) pinging the site every few minutes, alerting by email/SMS on downtime — turns "check it yourself" into "get notified when something's actually wrong."
  5. CloudWatch alarms on CPU / disk / (via the CloudWatch agent) memory, notifying via SNS → email before resource exhaustion becomes an outage.
- **What this doesn't give you:** if the instance genuinely fails, there can be a few minutes of downtime while auto-recovery runs — not zero-downtime. That level of protection is the future scaling path below, not part of the current build.

### 7.12 Future scaling path (documented for later — NOT part of the current build)
None of today's choices lock you in — application code doesn't change, only infrastructure configuration, if you ever outgrow one instance:
1. **Vertical first (easiest):** resize the EC2 instance (`t3.medium` → `t3.large`) or the RDS instance — a few minutes of downtime, no code change.
2. **Add RDS Proxy / PgBouncer** if DB connection counts ever become the bottleneck before compute does.
3. **Add a second EC2 instance + a basic Application Load Balancer + an Auto Scaling Group** once real redundancy matters (near-instant recovery from an instance failure, instead of the few-minutes auto-recovery window in 7.11). At that point, Redis also needs to move off the single box to a small shared instance or ElastiCache, since two app instances can't share one co-located Redis container. Rough added cost at that point: **~$80–90/month more** (second EC2 ~$30, ALB ~$20–25, RDS Multi-AZ ~$25 more, shared Redis ~$12–15) — i.e., roughly **$150–175/month total**, still well inside your budget ceiling if/when this becomes worth it.
4. **Move to ECS Fargate** once you're running enough instances that managing them by hand becomes the actual bottleneck — a deploy-pipeline change, not an app rewrite.
5. **Move to RDS Multi-AZ** for automatic ~60–120s database failover, once downtime during a DB issue genuinely matters more than the added cost.

---

## APPENDIX — PLAIN-ENGLISH GLOSSARY (for reference while building)
- **EC2** — a virtual server ("a computer in the cloud") that you rent by the hour. Your Flask app and its containers run on this.
- **RDS** — AWS's managed database service. You get Postgres without having to manually install/patch/back it up yourself.
- **S3** — object storage for files (photos, documents, certificates) — not a database, just a place to store and fetch files by URL.
- **Docker / Docker Compose** — packages your app (and its dependencies) into portable "containers" that run the same way everywhere; Compose lets you define and start several containers (app, Nginx, Redis, Celery) together with one command.
- **Nginx** — a web server that sits in front of your app; here it does two jobs: handles HTTPS (encryption) and forwards requests to Gunicorn/Flask.
- **Gunicorn** — a production-grade server that runs your Flask app (Flask's own built-in server is for local development only).
- **Let's Encrypt / Certbot** — a free service (Certbot is the tool) that issues and auto-renews the HTTPS certificate your site needs.
- **Redis** — an in-memory data store; used here as (a) a fast cache and (b) the message queue that Celery reads jobs from.
- **Celery** — runs background jobs (e.g., "generate this report," "send this notification") outside the request/response cycle so users aren't stuck waiting.
- **MinIO** — a free, S3-compatible storage server you can run locally, so file-upload code can be developed and tested without touching real AWS.
- **VPC / Security Group** — VPC is your private network inside AWS; a Security Group is a firewall rule set controlling what traffic can reach a resource (e.g., "only port 443 from the internet").
- **IAM Role** — a set of permissions you attach to an AWS resource (like your EC2 instance) so it can access other AWS services (like S3) securely, without embedding secret keys in your code.
- **Elastic IP** — a static public IP address you attach to your EC2 instance, so your domain always points to the right place even after a restart.
- **Route53** — AWS's DNS service (translates your domain name to your server's IP address).
- **CloudFront** — a CDN (content delivery network) — caches and serves your static frontend files from locations close to each user, so pages load faster.
- **CloudWatch** — AWS's logging/monitoring/alerting service.
- **ALB (Application Load Balancer)** — distributes traffic across multiple servers; only useful once you have more than one server. Not used in the current build.
- **NAT Gateway** — lets resources in a private subnet (no public IP) reach the internet; only needed once you move things into private subnets for extra isolation. Not used in the current build.
- **Multi-AZ** — running a redundant standby copy of your database in a second physical AWS location, so a hardware failure doesn't take you down; costs roughly double a single-instance database. Not used in the current build.
- **ECS Fargate** — a way to run Docker containers without managing the underlying servers yourself; the natural next step up from a single EC2 instance once you have several instances' worth of load. Not used in the current build.
- **Staging environment** — a production-like environment used to test changes before they reach real users. Not used in the current build (see 7.6 for how testing compensates).

---

## CHANGES LOG

### Round 1
1. Added **Principal/Headmaster** as a 6th role (login + endorsement authority).
2. **Block** = filter/report field only (no block login).
3. DM can hold **one or more districts** (assignable by higher roles).
4. Content tree locked: Sector → Job Role → NSQF Level → Module → Unit → Session; Curriculum + Syllabus merged.
5. Corrected the job-role assumption: labs keep **two** job-role slots (9–10 and 11–12) — same or different per school.
6. **No Aadhaar**; student photo optional.
7. Sectors (and other lists) are **editable master data**, not hardcoded.
8. VT creates login accounts for their **internship students**.
9. **Payments/Billing/Penalties dropped** (out of scope).
10. Kept Assessment/Marks/Certification and OJT/Apprenticeship/Placement modules.
11. Tech stack confirmed (Flask/PostgreSQL/S3/React/AWS) + initial enterprise-scale AWS architecture sketched (ECS Fargate/ALB/Multi-AZ).

### Round 2 (this round) — deployment finalized for actual scale and budget
12. Replaced the ECS Fargate/ALB/Multi-AZ architecture as the **active build plan** with a **single EC2 instance + RDS (Single-AZ) + S3** setup, sized correctly for ~1,000 users / ~30% bursty concurrency and a $100–500/month budget (Part 7.9) — landing at **≈$70–95/month**. The Fargate/ALB/Multi-AZ design is retained only as a documented **future scaling reference** (Part 7.12), not part of the current build.
13. **Confirmed: Local + Production environments only — no staging.** CI/CD (7.6) compensates with strict automated testing at the PR stage plus a deliberate, manual production-deploy step.
14. Added a fully detailed **Local Development Setup** (Part 7.5): Docker Compose services, MinIO for local S3 emulation, seed data, first-time setup steps, and local/production parity approach.
15. Added **reliability & self-healing hardening** (Part 7.11) appropriate to a single instance: container auto-restart, EC2 auto-recovery, boot-time service start, external uptime monitoring, resource alarms.
16. Updated Parts 6.2, 6.6, 6.7, 7.8 wording to reflect Redis/Celery **co-located** on the single EC2 instance (not ElastiCache/SQS) and secrets/HTTPS handled without an ALB.
17. **No feature, field, or role from Parts 0–5 was changed in this round** — only Parts 6–7 (technical architecture and development/deployment plan) were revised, per instruction.
