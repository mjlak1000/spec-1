"""Signals router — GET /signals."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query

from spec1_api.dependencies import IntelStoreDep, OsintStoreDep

router = APIRouter(prefix="/signals", tags=["signals"])


@router.get("")
def list_signals(
    intel_store: IntelStoreDep,
    osint_store: OsintStoreDep,
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
    source_type: Optional[str] = Query(None),
) -> dict:
    """Return recent signals from the OSINT store."""
    records = list(osint_store.read_all())
    if source_type:
        records = [r for r in records if r.get("source_type") == source_type]
    total = len(records)
    page = records[offset: offset + limit]
    return {"total": total, "limit": limit, "offset": offset, "items": page}
