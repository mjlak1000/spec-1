"""
SPEC-1 — app/cycle.py

Public entrypoint. Runs one full OSINT cycle end-to-end.

Usage:
    python -m spec1_engine.app.cycle
    # or
    from spec1_engine.app.cycle import run_cycle
    results = run_cycle()
"""

from __future__ import annotations

import json
from typing import List

from spec1_engine.core.engine import CycleResult, OSINTEngine
from spec1_engine.core import ids, logging_utils
from spec1_engine.signal.harvester import OSINTHarvester
from spec1_engine.analysts.discovery import AnalystDiscovery

logger = logging_utils.get_logger(__name__)


def run_cycle(environment: str = "osint") -> List[CycleResult]:
    """
    Run one full OSINT cycle.
    Harvest → Score → Investigate → Verify → Store Intelligence
    """
    run = ids.run_id(environment)
    engine    = OSINTEngine(environment=environment)
    harvester = OSINTHarvester()
    discovery = AnalystDiscovery()

    logging_utils.log_event(logger, "harvest_start", run_id=run)

    signals = harvester.collect(run_id=run)

    logging_utils.log_event(
        logger, "harvest_complete",
        run_id=run,
        signals_harvested=len(signals),
    )

    results = engine.run_batch(signals)

    # Analyst discovery pass
    all_candidates = []
    for signal in signals:
        candidates = discovery.discover(signal)
        all_candidates.extend(candidates)

    # Summary
    ok       = [r for r in results if r.status == "ok"]
    filtered = [r for r in results if r.status == "filtered"]
    failed   = [r for r in results if r.status == "failed"]

    logging_utils.log_event(
        logger, "cycle_summary",
        run_id=run,
        total=len(results),
        ok=len(ok),
        filtered=len(filtered),
        failed=len(failed),
        analyst_candidates=len(all_candidates),
    )

    # Print human-readable summary
    print("\n" + "="*60)
    print(f"SPEC-1 — CYCLE COMPLETE")
    print(f"Run ID:   {run}")
    print(f"Signals:  {len(signals)} harvested | {len(ok)} processed | {len(filtered)} filtered")
    print("="*60)

    for r in ok:
        if r.outcome and r.intelligence:
            print(f"\n  [{r.outcome.classification:>13}]  {r.signal.source}")
            print(f"   confidence: {r.outcome.confidence:.2f}  |  priority: {r.opportunity.priority}")
            print(f"   pattern:    {r.intelligence.pattern[:90]}")

    if all_candidates:
        needs_review = [c for c in all_candidates if c.get("needs_review")]
        if needs_review:
            print(f"\n  Analyst discovery: {len(needs_review)} candidates flagged for review")

    print("="*60 + "\n")

    return results


if __name__ == "__main__":
    run_cycle()
