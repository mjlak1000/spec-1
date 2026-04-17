"""Leads router — GET /leads, POST /leads/generate."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query

from spec1_api.dependencies import IntelStoreDep, LeadStoreDep, OsintStoreDep
from cls_leads.generator import generate_leads

router = APIRouter(prefix="/leads", tags=["leads"])


@router.get("")
def list_leads(
    lead_store: LeadStoreDep,
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
    priority: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
) -> dict:
    """Return stored intelligence leads."""
    records = list(lead_store.read_all())
    if priority:
        records = [r for r in records if r.get("priority") == priority.upper()]
    if category:
        records = [r for r in records if r.get("category") == category.lower()]
    total = len(records)
    page = records[offset: offset + limit]
    return {"total": total, "limit": limit, "offset": offset, "items": page}


@router.post("/generate")
def generate_leads_now(
    intel_store: IntelStoreDep,
    osint_store: OsintStoreDep,
    lead_store: LeadStoreDep,
    max_leads: int = Query(50, ge=1, le=200),
) -> dict:
    """Generate leads from current intelligence records and store them."""
    intel_records = list(intel_store.read_all())
    osint_records = list(osint_store.read_all())
    all_records = intel_records + osint_records
    leads = generate_leads(all_records, max_leads=max_leads)
    written = lead_store.save_batch(leads)
    return {"generated": len(leads), "stored": len(written)}
