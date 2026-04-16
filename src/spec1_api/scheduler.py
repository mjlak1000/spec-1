"""APScheduler background scheduler for spec1_api."""

from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

_scheduler = None


def _run_cycle_job() -> None:
    """Background job — runs a full intelligence cycle."""
    try:
        from spec1_engine.core.engine import Engine, EngineConfig
        config = EngineConfig(
            environment=os.environ.get("SPEC1_ENVIRONMENT", "production"),
            store_path=Path(os.environ.get("SPEC1_STORE_PATH", "spec1_intelligence.jsonl")),
        )
        engine = Engine(config)
        stats = engine.run()
        logger.info(
            "Scheduled cycle complete: %d records stored, %d errors",
            stats.records_stored,
            len(stats.errors),
        )
    except Exception as exc:
        logger.error("Scheduled cycle failed: %s", exc)


def start_scheduler() -> None:
    """Start the APScheduler if not already running."""
    global _scheduler
    if _scheduler is not None:
        return
    try:
        from apscheduler.schedulers.background import BackgroundScheduler

        hour = int(os.environ.get("SPEC1_CRON_HOUR", "6"))
        minute = int(os.environ.get("SPEC1_CRON_MINUTE", "0"))
        timezone = os.environ.get("SPEC1_TIMEZONE", "America/Los_Angeles")

        _scheduler = BackgroundScheduler(timezone=timezone)
        _scheduler.add_job(
            _run_cycle_job,
            trigger="cron",
            hour=hour,
            minute=minute,
            id="daily_cycle",
            replace_existing=True,
        )
        _scheduler.start()
        logger.info("Scheduler started: daily cycle at %02d:%02d %s", hour, minute, timezone)
    except ImportError:
        logger.warning("APScheduler not installed — scheduler disabled")
    except Exception as exc:
        logger.error("Scheduler failed to start: %s", exc)


def stop_scheduler() -> None:
    """Stop the scheduler gracefully."""
    global _scheduler
    if _scheduler is not None:
        try:
            _scheduler.shutdown(wait=False)
        except Exception:
            pass
        _scheduler = None
        logger.info("Scheduler stopped")


def get_scheduler():
    return _scheduler
