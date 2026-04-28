"""spec1_api — FastAPI application factory."""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from spec1_api import __version__
from spec1_api.routers import (
    brief,
    calibration,
    cycle,
    fara,
    health,
    intel,
    leads,
    psyop,
    signals,
    verdicts,
)
from spec1_api.scheduler import start_scheduler, stop_scheduler

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — start/stop scheduler."""
    start_scheduler()
    yield
    stop_scheduler()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="SPEC-1 Intelligence API",
        description="Real-time OSINT intelligence engine API",
        version=__version__,
        lifespan=lifespan,
    )

    app.include_router(health.router)
    app.include_router(signals.router)
    app.include_router(intel.router)
    app.include_router(leads.router)
    app.include_router(brief.router)
    app.include_router(psyop.router)
    app.include_router(fara.router)
    app.include_router(cycle.router)
    app.include_router(verdicts.router)
    app.include_router(calibration.router)

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    host = os.environ.get("SPEC1_API_HOST", "127.0.0.1")
    port = int(os.environ.get("SPEC1_API_PORT", "8000"))
    uvicorn.run("spec1_api.main:app", host=host, port=port, reload=False)
