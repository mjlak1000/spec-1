"""Psyop router — GET /psyop, POST /psyop/analyse."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Body, Query

from spec1_api.dependencies import OsintStoreDep, PsyopStoreDep
from cls_psyop.scorer import score_records, score_text
from cls_psyop.pipeline import PsyopPipeline

router = APIRouter(prefix="/psyop", tags=["psyop"])


@router.get("")
def list_psyop(
    psyop_store: PsyopStoreDep,
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
    classification: Optional[str] = Query(None),
) -> dict:
    """Return stored psyop scores."""
    records = list(psyop_store.read_all())
    if classification:
        records = [r for r in records if r.get("classification") == classification.upper()]
    total = len(records)
    page = records[offset: offset + limit]
    return {"total": total, "limit": limit, "offset": offset, "items": page}


@router.post("/analyse")
def analyse_text(
    psyop_store: PsyopStoreDep,
    text: str = Body(..., embed=True),
) -> dict:
    """Score a single text snippet for psyop patterns."""
    score = score_text(text)
    psyop_store.save(score)
    return score.to_dict()


@router.post("/run")
def run_psyop_pipeline(
    osint_store: OsintStoreDep,
    psyop_store: PsyopStoreDep,
) -> dict:
    """Run psyop detection over current OSINT records."""
    records = list(osint_store.read_all())
    pipeline = PsyopPipeline(store_path=psyop_store.path)
    stats = pipeline.run(records)
    return stats.to_dict()
