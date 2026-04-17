"""Cycle router — POST /cycle/run."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks

from spec1_api.schemas import CycleRequest, CycleResponse
from spec1_engine.core.engine import Engine, EngineConfig

router = APIRouter(prefix="/cycle", tags=["cycle"])

_last_run: dict = {}


@router.post("/run", response_model=CycleResponse)
def run_cycle(request: CycleRequest, background_tasks: BackgroundTasks) -> CycleResponse:
    """Trigger a full SPEC-1 intelligence cycle synchronously."""
    config = EngineConfig(
        environment=request.environment,
        max_signals=request.max_signals,
    )
    engine = Engine(config)
    stats = engine.run()
    result = CycleResponse(
        run_id=stats.run_id,
        started_at=stats.started_at,
        finished_at=stats.finished_at,
        signals_harvested=stats.signals_harvested,
        signals_parsed=stats.signals_parsed,
        opportunities_found=stats.opportunities_found,
        investigations_generated=stats.investigations_generated,
        outcomes_verified=stats.outcomes_verified,
        records_stored=stats.records_stored,
        errors=stats.errors,
    )
    _last_run.update(result.model_dump())
    return result


@router.get("/status")
def cycle_status() -> dict:
    """Return the status of the last cycle run."""
    if not _last_run:
        return {"status": "no_run", "message": "No cycle has been run yet"}
    return {"status": "completed", **_last_run}
