"""FARA router — GET /fara."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query

from spec1_api.dependencies import OsintStoreDep

router = APIRouter(prefix="/fara", tags=["fara"])


@router.get("")
def list_fara(
    osint_store: OsintStoreDep,
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
    country: Optional[str] = Query(None),
    registrant: Optional[str] = Query(None),
) -> dict:
    """Return FARA records from the OSINT store."""
    records = list(osint_store.filter_by("source_type", "FARA"))
    if country:
        records = [
            r for r in records
            if r.get("metadata", {}).get("country", "").lower() == country.lower()
        ]
    if registrant:
        query = registrant.lower()
        records = [
            r for r in records
            if query in r.get("metadata", {}).get("registrant", "").lower()
        ]
    total = len(records)
    page = records[offset: offset + limit]
    return {"total": total, "limit": limit, "offset": offset, "items": page}
