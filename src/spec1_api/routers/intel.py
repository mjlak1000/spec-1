"""Intelligence records router — GET /intel."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query

from spec1_api.dependencies import IntelStoreDep

router = APIRouter(prefix="/intel", tags=["intel"])


@router.get("")
def list_intel(
    intel_store: IntelStoreDep,
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
    classification: Optional[str] = Query(None),
    min_confidence: float = Query(0.0, ge=0.0, le=1.0),
) -> dict:
    """Return intelligence records, optionally filtered."""
    records = list(intel_store.read_all())
    if classification:
        records = [r for r in records if r.get("classification") == classification]
    if min_confidence > 0:
        records = [r for r in records if float(r.get("confidence", 0)) >= min_confidence]
    total = len(records)
    page = records[offset: offset + limit]
    return {"total": total, "limit": limit, "offset": offset, "items": page}
