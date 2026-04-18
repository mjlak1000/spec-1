"""SPEC-1 API route handlers."""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

import json

from fastapi import APIRouter, HTTPException, Query

from spec1_engine.core.ids import run_id as new_run_id
from spec1_engine.api.scheduler import KILL_FILE
from spec1_engine.intelligence.store import JsonlStore
import spec1_engine.briefing.writer as _brief_writer

router = APIRouter()

STORE_PATH = Path("spec1_intelligence.jsonl")
VERSION = "0.2"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Health ────────────────────────────────────────────────────────────────────

@router.get("/health")
def health() -> dict:
    return {"status": "ok", "timestamp": _now_iso(), "version": VERSION}


# ── Cycle ─────────────────────────────────────────────────────────────────────

@router.post("/cycle/run")
def trigger_cycle() -> dict:
    """Trigger an immediate cycle run in a background thread."""
    rid = new_run_id()

    def _run() -> None:
        from spec1_engine.app.cycle import run_cycle
        try:
            run_cycle(run_id=rid, verbose=False)
        except Exception as exc:
            import logging
            logging.getLogger(__name__).error("Background cycle failed: %s", exc)

    t = threading.Thread(target=_run, daemon=True, name=f"spec1-cycle-{rid}")
    t.start()

    return {"status": "triggered", "run_id": rid, "timestamp": _now_iso()}


@router.get("/cycle/status")
def cycle_status() -> dict:
    from spec1_engine.app.cycle import last_run_state
    return dict(last_run_state)


# ── Signals ───────────────────────────────────────────────────────────────────

@router.get("/signals/latest")
def signals_latest(
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[dict]:
    """Return last N records from the JSONL store that contain signal_id."""
    store = JsonlStore(STORE_PATH)
    all_records = store.read_all()
    signal_records = [r for r in all_records if "signal_id" in r]
    return signal_records[-limit:]


# ── Intelligence ──────────────────────────────────────────────────────────────

@router.get("/intelligence/latest")
def intelligence_latest(
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[dict]:
    """Return last N intelligence records from the JSONL store."""
    store = JsonlStore(STORE_PATH)
    all_records = store.read_all()
    return all_records[-limit:]


# ── Brief ─────────────────────────────────────────────────────────────────────

@router.get("/brief/latest")
def brief_latest() -> dict:
    """Return the most recently generated intelligence brief."""
    briefs_dir = _brief_writer.BRIEFS_DIR
    latest = briefs_dir / "spec1_brief_latest.md"
    if not latest.exists():
        raise HTTPException(status_code=404, detail="No brief generated yet.")
    brief_text = latest.read_text(encoding="utf-8")
    index_path = briefs_dir / "brief_index.jsonl"
    run_id_val, generated_at = None, None
    if index_path.exists():
        lines = [l.strip() for l in index_path.read_text(encoding="utf-8").splitlines() if l.strip()]
        if lines:
            last = json.loads(lines[-1])
            run_id_val = last.get("run_id")
            generated_at = last.get("timestamp")
    return {"brief": brief_text, "run_id": run_id_val, "generated_at": generated_at}


@router.get("/brief/index")
def brief_index() -> list[dict]:
    """Return brief index metadata, newest first."""
    index_path = _brief_writer.BRIEFS_DIR / "brief_index.jsonl"
    if not index_path.exists():
        return []
    entries = []
    for line in index_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return list(reversed(entries))


@router.get("/brief/{date}")
def brief_by_date(date: str) -> dict:
    """Return the brief for a specific date (YYYY-MM-DD)."""
    brief_path = _brief_writer.BRIEFS_DIR / f"spec1_brief_{date}.md"
    if not brief_path.exists():
        raise HTTPException(status_code=404, detail=f"No brief found for {date}.")
    return {"brief": brief_path.read_text(encoding="utf-8"), "date": date}


# ── Congressional ─────────────────────────────────────────────────────────────

CONGRESSIONAL_STORE_PATH = Path("spec1_congressional_intelligence.jsonl")


@router.post("/congressional/cycle/run")
def congressional_cycle_run() -> dict:
    """Trigger a congressional trade cycle in a background thread."""
    rid = new_run_id()

    def _run() -> None:
        from spec1_engine.congressional.cycle import run_congressional_cycle
        try:
            run_congressional_cycle(run_id=rid, verbose=False)
        except Exception as exc:
            import logging
            logging.getLogger(__name__).error("Congressional cycle failed: %s", exc)

    t = threading.Thread(target=_run, daemon=True, name=f"congressional-cycle-{rid}")
    t.start()
    return {"status": "triggered", "run_id": rid, "timestamp": _now_iso()}


@router.get("/congressional/status")
def congressional_status() -> dict:
    """Return the last congressional cycle run state."""
    from spec1_engine.congressional.cycle import last_run_state
    return dict(last_run_state)


@router.get("/congressional/latest")
def congressional_latest(
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[dict]:
    """Return the last N records from the congressional JSONL store."""
    store = JsonlStore(CONGRESSIONAL_STORE_PATH)
    return list(store.read_all())[-limit:]


# ── Kill switch ───────────────────────────────────────────────────────────────

@router.post("/kill")
def engage_kill() -> dict:
    """Create the .cls_kill file to halt scheduled cycle runs."""
    KILL_FILE.touch()
    return {"status": "kill_switch_engaged", "timestamp": _now_iso()}


@router.delete("/kill")
def clear_kill() -> dict:
    """Remove the .cls_kill file to resume scheduled cycle runs."""
    if KILL_FILE.exists():
        KILL_FILE.unlink()
    return {"status": "kill_switch_cleared", "timestamp": _now_iso()}
