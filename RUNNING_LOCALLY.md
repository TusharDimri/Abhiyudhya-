# Running RNAF on Your Computer (Local Setup)

This guide is written for someone who has **never used Docker or Flask before**.
Follow it top to bottom and you'll have the whole app running on your laptop.

You will end up with:
- The **backend** (the "brain" / API) running at `http://localhost:5001`
- The **frontend** (the website you click around in) at `http://localhost:5173`
- A **database**, a **cache**, and a **local file store** — all running automatically in Docker

---

## 1. Install the tools you need (one time)

Install these three programs:

| Tool | What it is | Download |
|------|------------|----------|
| **Docker Desktop** | Runs the database, cache, and backend in neat little boxes called *containers* so you don't have to install them by hand | https://www.docker.com/products/docker-desktop/ |
| **Node.js (LTS)** | Needed to run the frontend website | https://nodejs.org (pick the **LTS** button) |
| **Git** | Downloads the code | https://git-scm.com/downloads |

After installing **Docker Desktop, open it once** and wait until it says *"Docker Desktop is running"* (green whale icon). Docker must be **running** every time you work on the app.

To check everything installed, open a terminal (Mac: *Terminal* app · Windows: *PowerShell*) and run:

```bash
docker --version
node --version
git --version
```

Each should print a version number. If any says "command not found", re-install that tool.

---

## 2. Get the code

```bash
git clone <your-repo-url> rnaf
cd rnaf
```

(If you already have the folder, just `cd` into it.)

The project has two main folders:
- `backend/` — the Flask API (Python)
- `frontend/` — the React website (JavaScript)

---

## 3. Create the backend settings file

The backend reads its settings (passwords, database address, etc.) from a file
called `.env`. We ship an example you just copy:

**Mac / Linux:**
```bash
cp backend/.env.example backend/.env
```

**Windows (PowerShell):**
```powershell
Copy-Item backend\.env.example backend\.env
```

You do **not** need to change anything inside it for local use — the defaults
already match the Docker setup. (The real `.env` is never uploaded to Git.)

---

## 4. Start the backend + database (Docker)

From the project's top folder, run:

```bash
docker compose -f docker-compose.local.yml up -d
```

The first time, this downloads and starts 5 things: PostgreSQL (database),
Redis (cache), MinIO (local file storage), the Flask API, and a background worker.
It can take a few minutes the first time. When it's done, check they're running:

```bash
docker compose -f docker-compose.local.yml ps
```

You should see the services listed as `running`.

> 💡 `-d` means "detached" (runs in the background). To watch the logs live instead,
> run the same command without `-d`, or later run
> `docker compose -f docker-compose.local.yml logs -f backend`.

---

## 5. Create the database tables and demo data

The database starts **empty**. Run these two commands once to create the tables
and fill in a demo organisation with sample schools, labs, students, and **one login
for every role**:

```bash
# build the schema (runs every migration in order)
docker compose -f docker-compose.local.yml exec backend flask db upgrade

# add the demo organisation + demo users
docker compose -f docker-compose.local.yml exec backend flask seed

# optional: fill it with a school's worth of fictional records (students,
# attendance, lectures, visits, equipment, profiles ...) to click through
docker compose -f docker-compose.local.yml exec backend flask demo-data
```

**Already had the app running from before migrations existed?** Tell the
database which migration its current schema matches, then upgrade:

```bash
# one time only - records "my schema is the baseline", changes nothing
docker compose -f docker-compose.local.yml exec backend flask db stamp 0001_baseline

# now apply everything since
docker compose -f docker-compose.local.yml exec backend flask db upgrade
```

If your database is scratch data you don't mind losing, it is simpler to delete
the volume (`docker compose -f docker-compose.local.yml down -v`) and start from
`db upgrade` + `seed`.

The seed command prints the demo logins. They are:

| Role | Email | Password |
|------|-------|----------|
| Super Admin | `sa@rnaf.demo` | `Password@123` |
| Organisation Admin | `oa@rnaf.demo` | `Password@123` |
| District Manager | `dm@rnaf.demo` | `Password@123` |
| Principal | `pr@rnaf.demo` | `Password@123` |
| Vocational Trainer | `vt@rnaf.demo` | `Password@123` |

---

## 6. Start the frontend website

Open a **second terminal window** (leave Docker running in the first). Then:

```bash
cd frontend
npm install      # first time only – downloads website dependencies
npm run dev
```

When it finishes it will print a line like:

```
  ➜  Local:   http://localhost:5173/
```

Open **http://localhost:5173** in your browser.

---

## 7. Log in and explore

On the login screen you'll see **"Demo logins"** buttons — click any role (e.g.
*Trainer*) and it fills the email/password for you, then press **Sign in**.

Try logging in as different roles to see how the menu and data change:
- **Super Admin** sees everything across all organisations.
- **Trainer** only sees their own lab, students, and daily-entry screens.

That role-based filtering is the core of the app and it's enforced on the
**server**, not just hidden in the UI.

---

## 8. Everyday commands (after the first setup)

| I want to… | Command |
|------------|---------|
| Start the backend stack | `docker compose -f docker-compose.local.yml up -d` |
| Stop the backend stack | `docker compose -f docker-compose.local.yml down` |
| Start the website | `cd frontend && npm run dev` |
| See backend logs | `docker compose -f docker-compose.local.yml logs -f backend` |
| Run the tests | `docker compose -f docker-compose.local.yml exec backend pytest` |

The tests run against **PostgreSQL** — the same database engine you deploy on —
in a separate `rnaf_test` database that is created for you on the first run.
Your development data in `rnaf` is never touched. The Postgres container has to
be up (it is, if you followed the steps above).

> Why this matters: the suite used to run on SQLite because it was quicker to
> set up. SQLite is more forgiving than PostgreSQL — it does not check foreign
> keys when creating tables, for one — so a schema change could pass every test
> and still fail the moment it hit the real database. Testing on the engine you
> ship on is the only version of "the tests pass" that means anything.
| Reset the database completely | `docker compose -f docker-compose.local.yml down -v` then repeat **Step 4–5** |

> `down -v` deletes the database volume (all data). Use it when you want a clean slate.

---

## Handy extras

- **MinIO console** (see uploaded files locally): http://localhost:9001
  — login `minioadmin` / `minioadmin`.
- **API health check:** open http://localhost:5001/health — should show `{"status":"ok"}`.

---

## Troubleshooting

**"port is already allocated" / "address already in use"**
Something else is using port 5001, 5173, 5433, 6379, 9000, etc. Close the other program, or
stop the stack with `docker compose -f docker-compose.local.yml down` and retry.

**The website loads but says "Unauthorized" or nothing appears**
Make sure the backend is running (Step 4) and that you ran the `db upgrade` and
`seed` commands (Step 5).

**"docker: command not found" or Docker errors**
Docker Desktop isn't running. Open the Docker Desktop app and wait for the green
"running" status, then retry.

**Pulled new code and the app errors about missing columns/tables**
Someone added a database change. Apply it:
`docker compose -f docker-compose.local.yml exec backend flask db upgrade`.
If `docker compose ... up -d --build` was not run since `requirements.txt`
changed (e.g. PostGIS support), rebuild first.

**A trainer can't mark attendance: "school's location hasn't been set up"**
Attendance is only accepted within 1 km of the school. Log in as an admin,
open **Schools**, edit the school and set its **Location** (the
*Use my current location* button works if you are at the school).

**Changed backend code but don't see the change**
The backend auto-reloads. If it seems stuck, restart it:
`docker compose -f docker-compose.local.yml restart backend`.

**Frontend won't start / weird npm errors**
Delete `frontend/node_modules` and run `npm install` again.

---

When you're ready to put this on the internet for real users, see
**[DEPLOYING_TO_AWS.md](DEPLOYING_TO_AWS.md)**.
