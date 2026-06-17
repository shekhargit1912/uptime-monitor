"""Background scheduler that pings every registered monitor on an interval.

Runs inside the backend process via APScheduler. The interval is configurable
through the CHECK_INTERVAL environment variable (seconds, default 60).
"""
import logging
import os

from apscheduler.schedulers.background import BackgroundScheduler

from .database import SessionLocal
from .models import Check, Monitor
from .pinger import check_url

logger = logging.getLogger("uptime.scheduler")

CHECK_INTERVAL_SECONDS = int(os.getenv("CHECK_INTERVAL", "60"))


def run_all_checks() -> None:
    """Ping every monitor once and persist the results."""
    db = SessionLocal()
    try:
        monitors = db.query(Monitor).all()
        for monitor in monitors:
            result = check_url(monitor.url)
            result.monitor_id = monitor.id
            db.add(result)
        db.commit()
        if monitors:
            logger.info("Checked %d monitor(s)", len(monitors))
    except Exception:  # noqa: BLE001 - never let a bad cycle kill the scheduler
        logger.exception("Scheduled check cycle failed")
        db.rollback()
    finally:
        db.close()


def check_single_monitor(monitor_id: int, url: str) -> Check:
    """Run one immediate check for a freshly created monitor and persist it."""
    result = check_url(url)
    result.monitor_id = monitor_id
    db = SessionLocal()
    try:
        db.add(result)
        db.commit()
        db.refresh(result)
        return result
    finally:
        db.close()


def start_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone="UTC")
    scheduler.add_job(
        run_all_checks,
        trigger="interval",
        seconds=CHECK_INTERVAL_SECONDS,
        id="uptime_checks",
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    logger.info("Scheduler started; interval=%ds", CHECK_INTERVAL_SECONDS)
    return scheduler
