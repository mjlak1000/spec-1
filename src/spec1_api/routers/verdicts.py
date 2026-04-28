"""Verdicts router — POST /verdicts, GET /verdicts, GET /verdicts/{record_id}.

Captures human ground truth on intelligence records — Phase 1 of the
calibration feedback loop. Aggregation lives in cls_calibration (later).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from cls_verdicts.schemas import VALID_VERDICTS, Verdict
from spec1_api.dependencies import VerdictStoreDep

router = APIRouter(prefix="/verdicts", tags=["verdicts"])


class VerdictRequest(BaseModel):
    record_id: str = Field(..., description="ID of the IntelligenceRecord being judged")
    verdict: str = Field(..., description="One of: correct | incorrect | partial | unclear")
    reviewer: str = Field("anonymous", description="Reviewer identifier")
    notes: str = Field("", description="Free-form notes on why this verdict was given")


@router.post("")
def submit_verdict(
    body: VerdictRequest,
    verdict_store: VerdictStoreDep,
) -> dict:
    """File a human verdict on a stored intelligence record."""
    if body.verdict not in VALID_VERDICTS:
        raise HTTPException(
            status_code=422,
            detail=f"verdict must be one of {sorted(VALID_VERDICTS)}",
        )
    reviewed_at = datetime.now(timezone.utc)
    verdict = Verdict(
        verdict_id=Verdict.make_id(body.record_id, body.reviewer, reviewed_at),
        record_id=body.record_id,
        verdict=body.verdict,  # type: ignore[arg-type]
        reviewer=body.reviewer,
        reviewed_at=reviewed_at,
        notes=body.notes,
    )
    return verdict_store.save(verdict)


@router.get("")
def list_verdicts(
    verdict_store: VerdictStoreDep,
    record_id: Optional[str] = Query(None, description="Filter by intelligence record_id"),
    reviewer: Optional[str] = Query(None, description="Filter by reviewer"),
    verdict: Optional[str] = Query(None, description="Filter by verdict kind"),
    since: Optional[str] = Query(None, description="ISO8601 — only verdicts reviewed at or after this instant"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> dict:
    """List verdicts with optional filtering."""
    items = list(verdict_store.read_all())
    if record_id:
        items = [v for v in items if v.get("record_id") == record_id]
    if reviewer:
        items = [v for v in items if v.get("reviewer") == reviewer]
    if verdict:
        items = [v for v in items if v.get("verdict") == verdict]
    if since:
        items = [v for v in items if v.get("reviewed_at", "") >= since]
    total = len(items)
    page = items[offset: offset + limit]
    return {"total": total, "limit": limit, "offset": offset, "items": page}


@router.get("/{record_id}")
def verdicts_for_record(
    record_id: str,
    verdict_store: VerdictStoreDep,
) -> dict:
    """Return every verdict filed for a single intelligence record."""
    items = verdict_store.for_record(record_id)
    return {"record_id": record_id, "total": len(items), "items": items}
