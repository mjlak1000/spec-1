"""APScheduler setup for SPEC-1.

Schedules run_cycle() on a daily cron at 06:00 America/Los_Angeles.
Checks for .cls_kill file before every run. Optionally runs immediately on
startup when SPEC1_RUN_ON_START=true.
"""

from __future__ import annotations

import logging
import os
import threading
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

KILL_FILE = Path(".cls_kill")


def _guarded_cycle() -> None:
    """Run one cycle unless the kill file is present."""
    if KILL_FILE.exists():
        logger.warning("Kill file present — skipping scheduled cycle run.")
        return

    # Import here to avoid circular imports at module load time
    from spec1_engine.app.cycle import run_cycle

    logger.info("Scheduled cycle starting.")
    try:
        stats = run_cycle(verbose=False)
        logger.info(
            "Scheduled cycle complete — signals=%d records=%d",
            stats.get("signals_harvested", 0),
            stats.get("records_stored", 0),
        )
    except Exception as exc:
        logger.error("Scheduled cycle failed: %s", exc)


def build_scheduler() -> BackgroundScheduler:
    """Create and configure the BackgroundScheduler (not yet started)."""
    scheduler = BackgroundScheduler(timezone="America/Los_Angeles")
    scheduler.add_job(
        _guarded_cycle,
        trigger=CronTrigger(hour=6, minute=0, timezone="America/Los_Angeles"),
        id="daily_cycle",
        name="SPEC-1 Daily Intelligence Cycle",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    return scheduler


def maybe_run_on_start() -> None:
    """Fire an immediate cycle in a daemon thread if SPEC1_RUN_ON_START=true."""
    if os.environ.get("SPEC1_RUN_ON_START", "").lower() == "true":
        logger.info("SPEC1_RUN_ON_START=true — triggering immediate cycle.")
        t = threading.Thread(target=_guarded_cycle, daemon=True, name="spec1-startup-cycle")
        t.start()
