"""World brief router — GET /brief."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query

from spec1_api.dependencies import BriefStoreDep, IntelStoreDep
from cls_world_brief.producer import produce_brief

router = APIRouter(prefix="/brief", tags=["brief"])


@router.get("")
def get_latest_brief(brief_store: BriefStoreDep) -> dict:
    """Return the most recently produced world brief."""
    brief = brief_store.latest()
    if brief is None:
        return {"message": "No brief available yet"}
    return brief


@router.get("/history")
def list_briefs(
    brief_store: BriefStoreDep,
    limit: int = Query(10, ge=1, le=50),
) -> dict:
    """Return brief history."""
    all_briefs = list(brief_store.read_all())
    return {"total": len(all_briefs), "items": all_briefs[-limit:]}


@router.post("/generate")
def generate_brief(
    intel_store: IntelStoreDep,
    brief_store: BriefStoreDep,
    date: Optional[str] = Query(None, description="ISO date YYYY-MM-DD"),
) -> dict:
    """Generate a new world brief from current intelligence records."""
    records = list(intel_store.read_all())
    brief = produce_brief(records, date=date)
    entry = brief_store.save(brief, write_markdown=False)
    return entry
