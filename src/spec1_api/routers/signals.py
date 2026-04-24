"""Signals router — GET /signals  +  POST /signals/ingest."""

from __future__ import annotations

import logging
import uuid
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Query

from spec1_api.dependencies import IntelStoreDep, OsintStoreDep
from spec1_api.schemas import IngestResponse, SignalIngestRequest
from spec1_engine.intelligence.store import JsonlStore
from spec1_engine.signal.complexity import complexity_score, route as complexity_route
from spec1_engine.signal.parser import parse_signal
from spec1_engine.signal.scorer import score_signal
from spec1_engine.schemas.models import Signal
from spec1_engine.investigation.generator import generate_investigation
from spec1_engine.investigation.verifier import verify_investigation
from spec1_engine.intelligence.analyzer import analyze

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/signals", tags=["signals"])


# ─── Background task implementations ─────────────────────────────────────────

def _store_direct(record: dict, store: JsonlStore) -> None:
    """BYPASS path: write the signal straight to the intel store, no LLM."""
    store.append({**record, "route": "BYPASS", "classification": "ARCHIVED_LOW_COMPLEXITY"})
    logger.debug("bypass store: %s", record.get("signal_id"))


def _run_llm_pipeline(record: dict, store: JsonlStore, run_id: str) -> None:
    """LLM_GATE path: parse → 4-gate score → investigate → verify → store.

    Runs entirely in a background thread; does not block the API response.
    If any stage gates out, the signal is archived at that stage.
    """
    sid = record.get("signal_id", "")
    try:
        from datetime import datetime, timezone
        published_raw = record.get("published_at", "")
        try:
            from dateutil import parser as dp
            pub_dt = dp.parse(published_raw) if published_raw else datetime.now(timezone.utc)
        except Exception:
            pub_dt = datetime.now(timezone.utc)

        signal = Signal(
            signal_id=sid,
            source=record.get("source", "unknown"),
            source_type="API",
            text=record.get("text", ""),
            url=record.get("url", ""),
            author=record.get("author", ""),
            published_at=pub_dt,
            velocity=record.get("velocity", 0.5),
            engagement=record.get("engagement", 0.0),
            run_id=run_id,
            environment="production",
            metadata=record.get("metadata", {}),
        )

        parsed = parse_signal(signal)
        opportunity = score_signal(signal, parsed, run_id=run_id)

        if opportunity is None:
            store.append({**record, "route": "LLM_GATE", "classification": "GATED_OUT", "run_id": run_id})
            logger.debug("gated out: %s", sid)
            return

        investigation = generate_investigation(signal, parsed, opportunity)
        outcome = verify_investigation(investigation)
        intel_record = analyze(opportunity, investigation, outcome, signal)

        store.append({
            **intel_record.to_dict(),
            "signal_id": sid,
            "route": "LLM_GATE",
            "run_id": run_id,
        })
        logger.info("llm pipeline done: %s score=%.3f", sid, opportunity.score)

    except Exception as exc:
        logger.error("pipeline error %s: %s", sid, exc)
        store.append({**record, "route": "LLM_GATE", "classification": "PIPELINE_ERROR",
                      "error": str(exc), "run_id": run_id})


# ─── Routes ───────────────────────────────────────────────────────────────────

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


@router.post("/ingest", status_code=202)
def ingest_signal(
    payload: SignalIngestRequest,
    background_tasks: BackgroundTasks,
    intel_store: IntelStoreDep,
) -> dict:
    """Accept a signal, score complexity, enqueue pipeline, return immediately."""
    signal_id = payload.signal_id or f"sig-{uuid.uuid4().hex[:12]}"
    run_id = f"api-ingest-{uuid.uuid4().hex[:8]}"

    score = complexity_score(payload.text, payload.keywords, payload.entities)
    routing = complexity_route(score)

    record = {
        "signal_id": signal_id,
        "source": payload.source,
        "text": payload.text,
        "url": payload.url,
        "author": payload.author,
        "published_at": payload.published_at,
        "keywords": payload.keywords,
        "entities": payload.entities,
        "metadata": payload.metadata,
        "complexity_score": score,
    }

    if routing == "BYPASS":
        background_tasks.add_task(_store_direct, record, intel_store)
    else:
        background_tasks.add_task(_run_llm_pipeline, record, intel_store, run_id)

    return {"signal_id": signal_id, "status": "queued"}
