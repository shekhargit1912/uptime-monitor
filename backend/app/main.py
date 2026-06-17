"""FastAPI application: register URLs, list their live status, view history.

On startup it creates the tables (retrying until the database is reachable) and
starts the background scheduler that pings every monitor on an interval.
"""
import logging
import time
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from .database import Base, engine, get_db
from .models import Check, Monitor
from .schemas import CheckOut, MonitorCreate, MonitorOut
from .scheduler import check_single_monitor, run_all_checks, start_scheduler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("uptime.main")


def _init_db(retries: int = 10, delay: float = 2.0) -> None:
    """Create tables, retrying so the backend can start before the DB is ready."""
    for attempt in range(1, retries + 1):
        try:
            Base.metadata.create_all(bind=engine)
            logger.info("Database initialized")
            return
        except OperationalError:
            logger.warning("DB not ready (attempt %d/%d); retrying...", attempt, retries)
            time.sleep(delay)
    raise RuntimeError("Could not connect to the database after several retries")


@asynccontextmanager
async def lifespan(app: FastAPI):
    _init_db()
    scheduler = start_scheduler()
    # Run one cycle immediately so existing monitors get a status without waiting.
    run_all_checks()
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(title="Uptime Monitor API", version="1.0.0", lifespan=lifespan)

# Permissive CORS as a fallback. In the Docker setup nginx proxies /api to this
# service same-origin, so this mainly helps when running the API standalone.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _latest_check(db: Session, monitor_id: int) -> Check | None:
    return db.execute(
        select(Check)
        .where(Check.monitor_id == monitor_id)
        .order_by(Check.checked_at.desc())
        .limit(1)
    ).scalar_one_or_none()


def _to_monitor_out(db: Session, monitor: Monitor) -> MonitorOut:
    latest = _latest_check(db, monitor.id)
    return MonitorOut(
        id=monitor.id,
        url=monitor.url,
        name=monitor.name,
        created_at=monitor.created_at,
        latest_check=CheckOut.model_validate(latest) if latest else None,
    )


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/monitors", response_model=list[MonitorOut])
def list_monitors(db: Session = Depends(get_db)) -> list[MonitorOut]:
    monitors = db.execute(select(Monitor).order_by(Monitor.created_at)).scalars().all()
    return [_to_monitor_out(db, m) for m in monitors]


@app.post("/monitors", response_model=MonitorOut, status_code=201)
def create_monitor(payload: MonitorCreate, db: Session = Depends(get_db)) -> MonitorOut:
    monitor = Monitor(url=str(payload.url), name=payload.name)
    db.add(monitor)
    db.commit()
    db.refresh(monitor)
    # Immediate check so the dashboard shows up/down within seconds.
    check_single_monitor(monitor.id, monitor.url)
    return _to_monitor_out(db, monitor)


@app.delete("/monitors/{monitor_id}", status_code=204)
def delete_monitor(monitor_id: int, db: Session = Depends(get_db)) -> None:
    monitor = db.get(Monitor, monitor_id)
    if monitor is None:
        raise HTTPException(status_code=404, detail="Monitor not found")
    db.delete(monitor)
    db.commit()


@app.get("/monitors/{monitor_id}/checks", response_model=list[CheckOut])
def monitor_checks(
    monitor_id: int, limit: int = 50, db: Session = Depends(get_db)
) -> list[CheckOut]:
    if db.get(Monitor, monitor_id) is None:
        raise HTTPException(status_code=404, detail="Monitor not found")
    checks = db.execute(
        select(Check)
        .where(Check.monitor_id == monitor_id)
        .order_by(Check.checked_at.desc())
        .limit(limit)
    ).scalars().all()
    return [CheckOut.model_validate(c) for c in checks]
