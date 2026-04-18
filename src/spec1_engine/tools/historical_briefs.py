"""Generate briefs for every run_id in spec1_intelligence.jsonl that lacks one.

Usage:
    python -m spec1_engine.tools.historical_briefs
"""

from __future__ import annotations

import json
import time
from collections import defaultdict
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ModuleNotFoundError:
    pass

JSONL_PATH = Path("spec1_intelligence.jsonl")
BRIEFS_DIR = Path("briefs")

ELEVATED_CLASSIFICATIONS = {"CORROBORATED", "ESCALATE", "Corroborated", "Escalate"}


def _load_and_group(path: Path) -> dict[str, list[dict]]:
    """Read all records from JSONL and group by run_id."""
    groups: dict[str, list[dict]] = defaultdict(list)
    if not path.exists():
        return groups
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            run_id = record.get("run_id") or "unknown"
            groups[run_id].append(record)
    return dict(groups)


def _existing_brief_dates(briefs_dir: Path) -> set[str]:
    """Return set of YYYY-MM-DD strings for which a brief already exists."""
    if not briefs_dir.exists():
        return set()
    return {
        p.stem.replace("spec1_brief_", "")
        for p in briefs_dir.glob("spec1_brief_*.md")
        if p.stem != "spec1_brief_latest"
    }


def _date_for_group(records: list[dict]) -> str:
    """Return YYYY-MM-DD from the first record's created_at field."""
    for r in records:
        val = r.get("created_at", "")
        if val:
            return str(val)[:10]
    return ""


def _timestamp_for_group(records: list[dict]) -> str:
    """Return full ISO timestamp from the first record's created_at field."""
    for r in records:
        val = r.get("created_at", "")
        if val:
            return str(val)
    return ""


def _build_cycle_stats(run_id: str, records: list[dict]) -> dict:
    timestamp = _timestamp_for_group(records)
    elevated_count = sum(
        1 for r in records
        if r.get("outcome_classification", r.get("classification", "")) in ELEVATED_CLASSIFICATIONS
    )
    signals_harvested = records[0].get("signals_harvested", len(records)) if records else 0
    opportunities_found = records[0].get("opportunities_found", elevated_count) if records else 0

    return {
        "run_id": run_id,
        "started_at": records[0].get("started_at", timestamp) if records else timestamp,
        "finished_at": timestamp,
        "signals_harvested": signals_harvested,
        "opportunities_found": opportunities_found,
        "records_stored": len(records),
    }


def run() -> None:
    from spec1_engine.briefing.generator import generate_brief
    from spec1_engine.briefing.writer import write_brief

    groups = _load_and_group(JSONL_PATH)
    total_run_ids = len(groups)

    if total_run_ids == 0:
        print(f"[historical_briefs] No records found in {JSONL_PATH}")
        print("\n--- Summary ---")
        print("Total run_ids found in JSONL: 0")
        print("Already had briefs:           0")
        print("New briefs generated:         0")
        print("Failed:                       0")
        return

    existing_dates = _existing_brief_dates(BRIEFS_DIR)
    already_had = 0
    generated = 0
    failed = 0
    pending = 0

    for run_id, records in sorted(groups.items()):
        date = _date_for_group(records)

        if date and date in existing_dates:
            already_had += 1
            continue

        pending += 1
        cycle_stats = _build_cycle_stats(run_id, records)
        timestamp = cycle_stats["finished_at"] or "unknown"

        try:
            brief_md, _prompts = generate_brief(records, cycle_stats)
            write_brief(brief_md, run_id, timestamp)
            word_count = len(brief_md.split())
            display_date = date if date else (timestamp[:10] if timestamp != "unknown" else run_id[:10])
            print(f"[{display_date}] {run_id} — {len(records)} records — brief written ({word_count} words)")
            generated += 1
            if date:
                existing_dates.add(date)
        except Exception as exc:
            print(f"[ERROR] {run_id}: {type(exc).__name__}: {exc}")
            failed += 1

        if pending < total_run_ids - already_had:
            time.sleep(2)

    print("\n--- Summary ---")
    print(f"Total run_ids found in JSONL: {total_run_ids}")
    print(f"Already had briefs:           {already_had}")
    print(f"New briefs generated:         {generated}")
    print(f"Failed:                       {failed}")


if __name__ == "__main__":
    run()
