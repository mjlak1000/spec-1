"""Calibration router — GET /calibration/report.

Produces a CalibrationReport from current intelligence records + verdicts.
Phase 2 of the feedback loop. Read-only and idempotent.
"""

from __future__ import annotations

from fastapi import APIRouter

from fastapi import Query

from cls_calibration.aggregator import produce_report
from cls_calibration.proposer import propose_adjustments
from spec1_api.dependencies import IntelStoreDep, VerdictStoreDep

router = APIRouter(prefix="/calibration", tags=["calibration"])


@router.get("/report")
def calibration_report(
    intel_store: IntelStoreDep,
    verdict_store: VerdictStoreDep,
) -> dict:
    """Compute and return the current calibration report."""
    records = list(intel_store.read_all())
    verdicts = list(verdict_store.read_all())
    return produce_report(records, verdicts).to_dict()


@router.get("/proposals")
def calibration_proposals(
    intel_store: IntelStoreDep,
    verdict_store: VerdictStoreDep,
    sample_floor: int = Query(5, ge=1, le=1000),
    delta_floor: float = Query(0.15, ge=0.0, le=1.0),
) -> dict:
    """Return suggested calibration adjustments — descriptive only, never auto-applied."""
    records = list(intel_store.read_all())
    verdicts = list(verdict_store.read_all())
    cal = produce_report(records, verdicts)
    return propose_adjustments(
        cal, sample_floor=sample_floor, delta_floor=delta_floor
    ).to_dict()
