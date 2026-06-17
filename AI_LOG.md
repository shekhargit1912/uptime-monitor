# 🤖 AI Collaboration Log

A peek behind the curtain at how this MVP was built. My background is in
**DevOps / core infrastructure**, so I built the parts I know best — the Docker
setup, the Compose orchestration, the nginx layer, and the database
configuration — **by hand**. For the layers that aren't part of my day-to-day —
the **FastAPI backend logic** and the **React frontend** — I leaned on AI to move
fast and stretch across the stack.

---

## The AI Tech Stack

- **Assistant:** Claude Code (Anthropic's CLI coding agent).
- **Underlying model:** Claude Opus 4.8.
- **How I used it:** I set up the infrastructure and database wiring first, then
  used AI to generate the application code that slots into it, reviewing and
  correcting its output as I went.

---

## What I Wrote vs What AI Generated

| Layer | Authored by **me** (hand-written) | Generated with **AI** (Claude) |
| ----- | --------------------------------- | ------------------------------ |
| **Containerization** | `docker-compose.yml` (2 services, named volume for the SQLite file) | — |
| | `backend/Dockerfile`, `frontend/Dockerfile` (multi-stage), `.dockerignore` | — |
| **Web / proxy** | `frontend/nginx.conf` (static serve + `/api` reverse proxy) | — |
| **Database config** | DB wiring in `backend/app/database.py` (engine, session, `DATABASE_URL`), SQLite file on a persisted `sqlitedata` volume, `.env.example`, `CHECK_INTERVAL` env | — |
| **Backend app logic** | — | `backend/app/models.py`, `schemas.py`, `pinger.py`, `scheduler.py`, `main.py` |
| **Frontend** | — | `frontend/src/App.jsx`, `api.js`, `main.jsx` (+ `package.json`, `vite.config.js`) |

In short: **I own the infra + data layer; AI wrote the API and UI inside the
contract I defined** (a FastAPI service on port 8000 reading `DATABASE_URL`, a
React app calling relative `/api`, all wired together by my Compose file).

---

## The Prompts That Shipped It

I drove the architecture myself (SQLite on a persisted volume to keep the MVP
beautifully simple — no separate DB service to run; nginx reverse-proxy instead of
exposing the backend port, to avoid CORS and keep a single entry point). The
prompts below are the ones that generated the application code on top of that
infrastructure.

### 1. Framing the build

> "I'm a DevOps engineer building a simple full-stack uptime monitor. I'll write
> the Docker, Compose, nginx and database config myself — I need you to generate
> the application layers I don't write day-to-day. Backend: register URLs, ping
> each every ~minute, store HTTP status code, response time and timestamp.
> Frontend: a dashboard showing each URL's up/down status and latest response
> time. Keep it beautifully simple — MVP scale, a few dozen URLs."

### 2. Generating the core backend (FastAPI)

> "Generate the FastAPI backend: SQLAlchemy models for `monitors` and `checks`
> (status code, response time in ms, is_up, error, timestamp); a `pinger` that
> does an HTTP GET with a timeout and classifies up vs down; an APScheduler job
> that pings every monitor on a configurable interval; REST endpoints to add,
> list (with the latest check), delete, and view history. **Read the DB
> connection string from a `DATABASE_URL` env var so it drops straight into the
> SQLite + Compose setup I've already written.**"

### 3. Generating the dashboard (React + Vite)

> "Now the React + Vite frontend: a form to add a URL and a table listing each
> monitor with a green UP / red DOWN badge, HTTP status, latest response time,
> last-checked time, and a delete button. Poll the API every 5 seconds for live
> updates. **Use relative `/api` URLs** so the nginx reverse proxy I wrote can
> forward them to the backend. Multi-stage build is fine — I'll own the Dockerfile."

---

## The Course Corrections

Where AI's first cut was wrong or dated, and how I steered it back. Most of these
came from reviewing its output against what I know about how this has to run in
containers:

### a) Up/down semantics were too narrow

AI's first ping logic only treated *network exceptions* (DNS failure, timeout) as
"down" and counted any completed HTTP response as "up" — so a site returning
**500 Internal Server Error** would have falsely shown as **UP**.

**My correction:** *"A 4xx/5xx response must count as down, not just connection
errors — only 2xx and 3xx are up."* The classification became
`is_up = 200 <= status_code < 400`, with `follow_redirects=True` so a 301→200 still
reads as up. Single most important correctness fix for an uptime tool — see
[`backend/app/pinger.py`](./backend/app/pinger.py).

### b) Deprecated FastAPI startup hook

AI wired table creation + scheduler startup with `@app.on_event("startup")`, which
is **deprecated** in current FastAPI and logs warnings.

**My correction:** *"Use the modern `lifespan` context manager, not the deprecated
`on_event` hooks."* Startup/shutdown now lives in an `asynccontextmanager` passed
to `FastAPI(lifespan=...)` — see [`backend/app/main.py`](./backend/app/main.py).

### c) `npm ci` in the Dockerfile I own

The frontend build first used `npm ci`, which **requires a committed
`package-lock.json`**. Since I didn't ship a lockfile, `npm ci` would have failed
the build outright. Since the Dockerfiles are mine, I caught this on review and
switched the build stage to `npm install` — a reminder that AI's "best-practice"
snippets assume context that may not hold for your repo.

### d) SQLite cross-thread error (caught from the infra side)

When I first ran the stack on SQLite, the app crashed with *"SQLite objects
created in a thread can only be used in that same thread."* The cause: APScheduler
runs the periodic checks on a **background thread**, while requests are served on
another — and SQLite's default `pysqlite` connection refuses to be shared across
threads. Since the DB wiring is mine, I fixed it in
[`backend/app/database.py`](./backend/app/database.py) by passing
`connect_args={"check_same_thread": False}` for SQLite URLs only (it's a no-op for
other engines). A classic "works on the happy path, breaks once a second thread
touches it" issue that you only catch by actually running the scheduler.

---

*Net takeaway:* I owned the infrastructure and data layer end-to-end; AI let me
move fast on the FastAPI and React layers I don't normally touch. The real
value-add was **integration and correctness review** — making AI's code fit the
container/DB contract I'd defined, and catching the up/down logic, the deprecation
drift, and the build/threading assumptions that looked fine at a glance.
