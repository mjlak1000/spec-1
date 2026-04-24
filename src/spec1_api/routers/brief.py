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


@router.get("/index")
def get_brief_index(brief_store: BriefStoreDep) -> dict:
    """Return all briefs sorted newest first with summary metadata."""
    all_briefs = list(brief_store.read_all())
    items = []
    for b in reversed(all_briefs):
        text = b.get("headline", "") + " " + b.get("summary", "")
        for section in b.get("sections", []):
            text += " " + section.get("body", "")
        items.append({
            "brief_id": b.get("brief_id"),
            "date": b.get("date"),
            "headline": b.get("headline"),
            "word_count": len(text.split()),
            "confidence": b.get("confidence"),
            "produced_at": b.get("produced_at"),
        })
    return {"total": len(items), "items": items}


@router.get("/latest")
def get_latest_brief_named(brief_store: BriefStoreDep) -> dict:
    """Return the most recently produced world brief (named endpoint)."""
    brief = brief_store.latest()
    if brief is None:
        return {"message": "No brief available yet"}
    return brief


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


@router.get("/{date}")
def get_brief_by_date(date: str, brief_store: BriefStoreDep) -> dict:
    """Return the brief for a specific date (YYYY-MM-DD)."""
    brief = brief_store.get_by_date(date)
    if brief is None:
        return {"message": f"No brief found for date {date}"}
    return brief
