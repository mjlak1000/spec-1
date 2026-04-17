"""Generate briefs for historical run_ids not yet covered in briefs/.

Usage:
    python -m spec1_engine.tools.historical_briefs
"""

from __future__ import annotations

import json
import time
from collections import defaultdict
from pathlib import Path


JSONL_PATH = Path("spec1_intelligence.jsonl")
BRIEFS_DIR = Path("briefs")
_ELEVATED = {"CORROBORATED", "ESCALATE"}


def _load_and_group(path: Path) -> dict[str, list[dict]]:
    """Read the JSONL store and return records grouped by run_id."""
    groups: dict[str, list[dict]] = defaultdict(list)
    if not path.exists():
        return groups
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            run_id = rec.get("run_id", "unknown")
            groups[run_id].append(rec)
    return dict(groups)


def _date_from_group(records: list[dict]) -> str:
    """Derive YYYY-MM-DD from the latest written_at in a group."""
    timestamps = [r.get("written_at", "") for r in records if r.get("written_at")]
    if timestamps:
        latest = max(timestamps)
        return latest[:10]  # ISO date prefix
    return "0000-00-00"


def _existing_brief_dates() -> set[str]:
    """Return set of YYYY-MM-DD strings for briefs already on disk."""
    dates: set[str] = set()
    if not BRIEFS_DIR.exists():
        return dates
    for p in BRIEFS_DIR.glob("spec1_brief_????-??-??.md"):
        # filename: spec1_brief_YYYY-MM-DD.md
        stem = p.stem  # spec1_brief_YYYY-MM-DD
        date_part = stem[len("spec1_brief_"):]
        if len(date_part) == 10:
            dates.add(date_part)
    return dates


def _build_cycle_stats(run_id: str, records: list[dict]) -> dict:
    timestamps = sorted(r.get("written_at", "") for r in records if r.get("written_at"))
    started_at = timestamps[0] if timestamps else ""
    finished_at = timestamps[-1] if timestamps else ""
    elevated = sum(
        1 for r in records
        if r.get("outcome_classification", r.get("classification", "")) in _ELEVATED
    )
    return {
        "run_id": run_id,
        "started_at": started_at,
        "finished_at": finished_at,
        "signals_harvested": len(records),
        "opportunities_found": len(records),
        "records_stored": len(records),
        "elevated_count": elevated,
        "errors": [],
    }


def main() -> None:
    from spec1_engine.briefing.generator import generate_brief
    from spec1_engine.briefing.writer import write_brief

    print(f"Reading {JSONL_PATH} ...")
    groups = _load_and_group(JSONL_PATH)
    total_run_ids = len(groups)
    print(f"Found {total_run_ids} run_id(s) in {JSONL_PATH}")

    existing_dates = _existing_brief_dates()
    print(f"Existing brief dates in {BRIEFS_DIR}/: {sorted(existing_dates)}\n")

    already_had = 0
    generated = 0
    failed = 0

    for run_id, records in sorted(groups.items()):
        date = _date_from_group(records)
        if date in existing_dates:
            already_had += 1
            continue

        cycle_stats = _build_cycle_stats(run_id, records)
        timestamp = cycle_stats["finished_at"]
        elevated = cycle_stats["elevated_count"]

        try:
            brief_md, _prompts = generate_brief(records, cycle_stats)
            filepath = write_brief(brief_md, run_id, timestamp)
            word_count = len(brief_md.split())
            print(
                f"[{date}] {run_id} — {len(records)} records — "
                f"{elevated} elevated — brief written ({word_count} words) → {filepath}"
            )
            existing_dates.add(date)
            generated += 1
        except Exception as exc:
            print(f"[{date}] {run_id} — FAILED: {exc}")
            failed += 1

        time.sleep(2)

    print(f"\n{'='*60}")
    print(f"  Total run_ids found : {total_run_ids}")
    print(f"  Already had briefs  : {already_had}")
    print(f"  New briefs generated: {generated}")
    print(f"  Failed              : {failed}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
