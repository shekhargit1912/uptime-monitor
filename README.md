# ⏱️ Uptime Monitor

A lightweight, full-stack uptime monitor. It lets you register URLs, pings each
one on a schedule, stores every check (HTTP status code, response time,
timestamp), and shows live **UP / DOWN** status on an auto-refreshing dashboard.

The entire stack comes up with a **single command**.

> **Built by:** infrastructure (Docker, Compose, nginx, database config)
> hand-built; FastAPI backend + React frontend generated with Claude — see
> [AI_LOG.md](./AI_LOG.md).

---

## Architecture

```
                         ┌──────────────────────────────────────┐
   Browser  ──:8080──►   │  frontend (nginx + React/Vite build)  │
                         │   • serves the dashboard SPA          │
                         │   • proxies /api/* ──► backend:8000    │
                         └───────────────────┬──────────────────┘
                                             │
                         ┌───────────────────▼──────────────────┐
                         │  backend (FastAPI + APScheduler)      │
                         │   • REST API to register/list URLs    │
                         │   • pings every URL on an interval    │
                         │   • SQLite file on a persisted volume │
                         │     (/data/uptime.db)                 │
                         └──────────────────────────────────────┘
```

Two containers (frontend + backend); the backend stores everything in a SQLite
file on a Docker volume, so there's no separate database service to run.

**Stack:** Python · FastAPI · APScheduler · httpx · SQLAlchemy · SQLite ·
React · Vite · nginx · Docker Compose.

```
uptime-monitor/
├── backend/      # FastAPI pinging + metric-logging API
├── frontend/     # React status dashboard (served via nginx)
└── docker-compose.yml
```

---

## 🗄️ Why SQLite (and when you'd reach for PostgreSQL)

**This MVP uses SQLite on purpose.** At the target scale — a few dozen URLs checked
about once a minute — SQLite satisfies every requirement (durable storage of each
check's status code, response time, and timestamp) with the least possible
complexity: no separate database container, no credentials, zero config. The file
lives on a Docker volume, so data survives restarts. This matches the brief's
"keep it beautifully simple" guidance — a managed database here would be
over-engineering.

**Why not PostgreSQL up front?** Postgres earns its keep in *production* —
concurrent writers, multiple backend replicas, high availability, large/long-lived
history. None of those apply at MVP scale. SQLite's one real limitation is that
it's **single-writer / single-node**.

**The production-grade path:** when you outgrow single-writer (horizontal scaling
or HA), move to **PostgreSQL** (e.g. **AWS RDS**). Because the backend reads its
connection string from the `DATABASE_URL` environment variable and uses SQLAlchemy
(which speaks both engines), that migration is essentially a **one-line config
change** — point `DATABASE_URL` at Postgres — with **no application code rewrite**.

---

## 🚀 1-Line Setup

From the repository root:

```bash
docker compose up --build
```

Then open **http://localhost:8080**.

That's it — the API and the dashboard start together. No `.env` file is required
(sensible defaults are baked in); copy `.env.example` to `.env` only if you want
to change the check interval. Health-check data is stored in a SQLite file on the
`sqlitedata` Docker volume.

To stop: `Ctrl+C`, then `docker compose down` (add `-v` to also wipe the SQLite
data volume).

---

## ✅ Testing the UP / DOWN logic

The dashboard runs an **immediate check** the moment you add a URL, so you don't
have to wait for the next scheduled cycle to see a result. After that it
re-checks every `CHECK_INTERVAL` seconds (default 60) and the UI polls every 5s.

1. Open **http://localhost:8080**.
2. **Add a healthy URL** — paste `https://example.com` and click **Add URL**.
   Within a couple of seconds it shows a green **UP** badge, HTTP `200`, and a
   response time in milliseconds.
3. **Add a broken URL** — paste one of:
   - `https://does-not-exist.invalid.example` (DNS resolution fails), or
   - `https://example.com:81` (connection times out).

   It shows a red **DOWN** badge with the captured error (e.g.
   `ConnectError: ...` or `ConnectTimeout: ...`) and no HTTP status.
4. Watch the table auto-refresh every 5 seconds. Both states persist and keep
   updating each scheduled cycle.

You can also verify the stored data directly through the API:

```bash
# List all monitors with their latest check
curl http://localhost:8080/api/monitors

# Full check history for monitor #1 (status code, response time, timestamp)
curl http://localhost:8080/api/monitors/1/checks
```

---

## 📡 API Reference

The API is reachable at `http://localhost:8080/api` (proxied) or directly on the
backend container at port `8000`.

| Method   | Path                         | Description                                   |
| -------- | ---------------------------- | --------------------------------------------- |
| `POST`   | `/monitors`                  | Register a URL. Body: `{ "url": "https://…" }`. Runs one check immediately. |
| `GET`    | `/monitors`                  | List all monitors, each with its latest check. |
| `DELETE` | `/monitors/{id}`             | Remove a monitor and its check history.       |
| `GET`    | `/monitors/{id}/checks`      | Recent check history for a monitor (`?limit=`).|
| `GET`    | `/health`                    | Liveness probe.                               |

Interactive docs are auto-generated by FastAPI — port-forward 8000 and visit
`/docs` if you want to poke at it directly.

---

## ☁️ Deployment Sketch (hypothetical)

Because storage is a single SQLite file (single-writer), the natural topology for
this MVP scale is **one backend instance with the DB file on a persistent volume**
— no managed database needed. On **AWS**:

- **Images → Amazon ECR.** Push the `backend` and `frontend` images built here.
- **Compute → ECS Fargate**, two services in one cluster (no servers to manage):
  - `frontend` task (nginx) and a **single** `backend` task (uvicorn) — keep
    backend at one replica so there's exactly one writer to the SQLite file.
  - The APScheduler loop runs inside the backend task; at this scale no separate
    scheduler/worker is needed.
- **Storage → Amazon EFS**, mounted into the backend task at `/data`, so the
  SQLite file survives task restarts/redeploys. (On a single EC2/Lightsail box,
  this is just `docker compose up` with the file on an attached **EBS** volume.)
- **Routing → Application Load Balancer** with path-based rules:
  `/api/*` → backend target group, everything else → frontend target group.
  (Same split nginx does locally, just promoted to the ALB.)

A sketch of the core resources in Terraform:

```hcl
# --- not applied; illustrative only ---
resource "aws_ecs_cluster" "uptime" {
  name = "uptime-monitor"
}

# Persistent storage for the SQLite file (mounted at /data in the backend task).
resource "aws_efs_file_system" "uptime_data" {
  creation_token = "uptime-monitor-data"
}

resource "aws_lb" "alb" {
  name               = "uptime-alb"
  load_balancer_type = "application"
  subnets            = var.public_subnets
}

# backend (desired_count = 1, EFS volume at /data, DATABASE_URL=sqlite:////data/uptime.db)
# + frontend: each an aws_ecs_task_definition + aws_ecs_service, registered behind
# aws_lb_target_group + aws_lb_listener_rule:
#   /api/*  -> backend target group
#   /*      -> frontend target group
```

**When to outgrow this:** SQLite-on-a-volume is single-writer and tied to one
instance. The moment you need multiple backend replicas or HA, that's the trigger
to swap the volume for **Amazon RDS (PostgreSQL)** — only `DATABASE_URL` changes,
since the app already reads it from the environment.

---

## 🤖 AI Collaboration Log

**Authorship at a glance:** the infrastructure layer — Docker, Compose, nginx, and
the database configuration — was **hand-built** by me (DevOps engineer); the
**FastAPI backend logic and the React frontend were generated with Claude** (the
layers outside my day-to-day) and reviewed/corrected by me.

See **[AI_LOG.md](./AI_LOG.md)** for the full breakdown: the AI tools/LLMs used, a
what-I-wrote-vs-what-AI-generated table, the prompts that shipped it, and the
course corrections.
