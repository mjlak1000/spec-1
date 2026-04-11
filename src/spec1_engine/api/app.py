"""SPEC-1 FastAPI application.

Startup: initialises APScheduler and optionally fires an immediate cycle.
Shutdown: stops the scheduler cleanly.

Mount point: /api/v1
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from spec1_engine.api.routes import router
from spec1_engine.api.scheduler import build_scheduler, maybe_run_on_start
from spec1_engine.core.logging_utils import configure_root

configure_root()


@asynccontextmanager
async def lifespan(application: FastAPI):
    # ── Startup ──────────────────────────────────────────────────────────────
    scheduler = build_scheduler()
    scheduler.start()
    maybe_run_on_start()
    yield
    # ── Shutdown ─────────────────────────────────────────────────────────────
    if scheduler.running:
        scheduler.shutdown(wait=False)


app = FastAPI(
    title="SPEC-1 Signal Intelligence Engine",
    version="0.2",
    description="Real-time intelligence signal harvesting, scoring, and analysis.",
    lifespan=lifespan,
)

app.include_router(router, prefix="/api/v1")
