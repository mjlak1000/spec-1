"""SPEC-1 Full Pipeline Cycle.

Implements and runs the full loop:
  RSS fetch → parse → score (4 gates) → investigation → verify → intelligence → JSONL store

Usage:
    python -m spec1_engine.app.cycle
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
load_dotenv(encoding="utf-8-sig")  # utf-8-sig strips PowerShell BOM if present

from collections import Counter

from spec1_engine.core.ids import run_id as new_run_id
from spec1_engine.core.logging_utils import configure_root, get_logger
from spec1_engine.schemas.models import (
    IntelligenceRecord,
    Investigation,
    Opportunity,
    Outcome,
    ParsedSignal,
    Signal,
)
from spec1_engine.signal.harvester import harvest_all, DEFAULT_FEEDS
from spec1_engine.signal.parser import parse_signal
from spec1_engine.signal.scorer import score_signal
from spec1_engine.investigation.generator import generate_investigation
from spec1_engine.investigation.verifier import verify_investigation
from spec1_engine.intelligence.analyzer import analyze
from spec1_engine.intelligence.store import JsonlStore

configure_root()
logger = get_logger(__name__)

DEFAULT_STORE_PATH = Path("spec1_intelligence.jsonl")

# Module-level state updated after every completed cycle — read by API routes.
last_run_state: dict = {
    "run_id": None,
    "timestamp": None,
    "signal_count": 0,
    "record_count": 0,
}


def _build_psyop_signal(
    signals: list[Signal],
    parsed_signals: list[ParsedSignal],
) -> dict:
    """Aggregate harvested signals into a psyop signal dict for scoring.

    Args:
        signals: List of Signal objects.
        parsed_signals: List of ParsedSignal objects.

    Returns:
        Dict with psyop signal structure for scoring.
    """
    # topic: most common keyword across parsed signals
    all_keywords = []
    for ps in parsed_signals:
        all_keywords.extend(ps.keywords)
    topic = max(set(all_keywords), key=all_keywords.count) if all_keywords else "unknown"

    # entities: deduplicated union of entities
    entities = list(set().union(*(ps.entities for ps in parsed_signals)))

    # sources: unique source names
    sources = list(set(sig.source for sig in signals))

    # narrative_markets: same as sources (each feed = one media market)
    narrative_markets = sources

    # fara_matches: [] — hook for future FARA integration
    fara_matches = []

    # legislation_matches: [] — hook for future legislation integration
    legislation_matches = []

    # consensus_velocity: average signal velocity
    velocities = [sig.velocity for sig in signals]
    consensus_velocity = sum(velocities) / len(velocities) if velocities else 0.0

    # origin_traceable: True (RSS sources are traceable by default)
    origin_traceable = True

    # signals_data: per-signal details for evidence chain construction
    signals_data = [
        {
            "signal_id": sig.signal_id,
            "source": sig.source,
            "text": sig.text[:280] if sig.text else "",
            "url": sig.url or "",
            "published_at": sig.published_at.isoformat() if sig.published_at else "",
        }
        for sig in signals
    ]

    return {
        "topic": topic,
        "entities": entities,
        "sources": sources,
        "fara_matches": fara_matches,
        "legislation_matches": legislation_matches,
        "narrative_markets": narrative_markets,
        "consensus_velocity": consensus_velocity,
        "origin_traceable": origin_traceable,
        "signals_data": signals_data,
    }


def run_cycle(
    store_path: Path = DEFAULT_STORE_PATH,
    run_id: Optional[str] = None,
    environment: str = "production",
    feed_timeout: int = 15,
    feeds: Optional[dict] = None,
    max_signals: Optional[int] = None,
    verbose: bool = True,
) -> dict:
    """Execute one full SPEC-1 cycle and return a summary dict."""
    run_id = run_id or new_run_id()
    store = JsonlStore(store_path)
    started_at = datetime.now(timezone.utc).isoformat()

    if verbose:
        print(f"\n{'='*60}")
        print(f"  SPEC-1 Intelligence Engine — Cycle Start")
        print(f"  run_id    : {run_id}")
        print(f"  environment: {environment}")
        print(f"  store     : {store_path}")
        print(f"  started   : {started_at}")
        print(f"{'='*60}\n")

    stats = {
        "run_id": run_id,
        "started_at": started_at,
        "signals_harvested": 0,
        "signals_parsed": 0,
        "opportunities_found": 0,
        "investigations_generated": 0,
        "outcomes_verified": 0,
        "records_stored": 0,
        "errors": [],
    }

    # ── Step 1: Harvest RSS signals ──────────────────────────────────────────
    if verbose:
        print("[1/7] Harvesting RSS feeds...")
        sources = feeds or DEFAULT_FEEDS
        for name, url in sources.items():
            print(f"      - {name}: {url}")

    try:
        result = harvest_all(
            feeds=feeds,
            run_id=run_id,
            environment=environment,
            timeout=feed_timeout,
        )
        signals: list[Signal] = result["signals"]
        if max_signals:
            signals = signals[:max_signals]
        stats["signals_harvested"] = len(signals)

        for src, err in result.get("errors", {}).items():
            stats["errors"].append(f"harvest:{src}:{err}")
            if verbose:
                print(f"      [WARN] Feed error — {src}: {err}")

        if verbose:
            print(f"      Harvested {len(signals)} signals from {len(sources)} feeds")
    except Exception as exc:
        stats["errors"].append(f"harvest_all:{exc}")
        if verbose:
            print(f"      [ERROR] Harvest failed: {exc}")
        stats["finished_at"] = datetime.now(timezone.utc).isoformat()
        return stats

    # ── Step 2: Parse signals ─────────────────────────────────────────────────
    if verbose:
        print(f"\n[2/7] Parsing {len(signals)} signals...")

    parsed_signals: list[ParsedSignal] = []
    for sig in signals:
        try:
            ps = parse_signal(sig)
            parsed_signals.append(ps)
        except Exception as exc:
            stats["errors"].append(f"parse:{sig.signal_id}:{exc}")

    stats["signals_parsed"] = len(parsed_signals)
    if verbose:
        print(f"      Parsed {len(parsed_signals)} signals")

    # ── Psyop scoring ──────────────────────────────────────────────────────────
    if verbose:
        print(f"\n[Psyop] Scoring signal batch for psyop patterns...")
    try:
        from spec1_engine.cls_psyop.scorer import score_psyop
        psyop_signal = _build_psyop_signal(signals, parsed_signals)
        psyop_result = score_psyop(psyop_signal, run_id=run_id)
        stats["psyop_classification"] = psyop_result["classification"]
        stats["psyop_score"] = psyop_result["score"]
        stats["psyop_patterns_fired"] = psyop_result["patterns_fired"]
        stats["psyop_evidence_chains"] = psyop_result.get("evidence_chains", [])
        if verbose:
            print(f"      Psyop score={psyop_result['score']} "
                  f"class={psyop_result['classification']} "
                  f"patterns={psyop_result['patterns_fired']} "
                  f"evidence_chains={len(stats['psyop_evidence_chains'])}")
    except Exception as exc:
        logger.error("Psyop scoring failed: %s", exc)
        stats["errors"].append(f"psyop:{exc}")

    # ── Step 3: Score — 4 gates ───────────────────────────────────────────────
    if verbose:
        print(f"\n[3/7] Scoring through 4 gates (credibility/volume/velocity/novelty)...")

    opportunities: list[tuple[Signal, ParsedSignal, Opportunity]] = []
    blocked = 0
    for sig, ps in zip(signals, parsed_signals):
        try:
            opp = score_signal(sig, ps, run_id=run_id)
            if opp is not None:
                opportunities.append((sig, ps, opp))
            else:
                blocked += 1
        except Exception as exc:
            stats["errors"].append(f"score:{sig.signal_id}:{exc}")
            blocked += 1

    stats["opportunities_found"] = len(opportunities)
    if verbose:
        print(f"      Opportunities: {len(opportunities)} | Blocked: {blocked}")
        if opportunities:
            print(f"      Priority breakdown:")
            for prio in ("ELEVATED", "STANDARD", "MONITOR"):
                n = sum(1 for _, _, o in opportunities if o.priority == prio)
                if n:
                    print(f"        {prio}: {n}")

    # ── Steps 4–7: Investigate → Verify → Analyze → Store ───────────────────
    if verbose:
        print(f"\n[4/7] Generating investigations...")
        print(f"[5/7] Verifying investigations...")
        print(f"[6/7] Analyzing into intelligence records...")
        print(f"[7/7] Writing to JSONL store: {store_path}\n")

    records_stored = 0
    stored_records: list[dict] = []
    for sig, ps, opp in opportunities:
        try:
            # Step 4: Generate investigation
            inv = generate_investigation(opp, sig, ps)
            stats["investigations_generated"] += 1

            # Step 5: Verify
            outcome = verify_investigation(inv)
            stats["outcomes_verified"] += 1

            # Step 6: Analyze
            record = analyze(opp, inv, outcome, sig)

            # Step 7: Store
            record_dict = {
                **record.to_dict(),
                "run_id": run_id,
                "signal_id": sig.signal_id,
                "signal_source": sig.source,
                "signal_url": sig.url,
                "environment": environment,
                "opportunity_id": opp.opportunity_id,
                "opportunity_score": opp.score,
                "opportunity_priority": opp.priority,
                "gate_results": opp.gate_results,
                "investigation_id": inv.investigation_id,
                "hypothesis": inv.hypothesis,
                "outcome_classification": outcome.classification,
                "outcome_confidence": outcome.confidence,
            }
            store.append(record_dict)
            stored_records.append(record_dict)
            records_stored += 1

            if verbose:
                print(
                    f"  [{records_stored:03d}] [{opp.priority:8s}] score={opp.score:.3f} "
                    f"class={outcome.classification:14s} conf={outcome.confidence:.2f} "
                    f"src={sig.source}"
                )
        except Exception as exc:
            stats["errors"].append(f"pipeline:{opp.opportunity_id}:{exc}")
            if verbose:
                print(f"  [ERR] {opp.opportunity_id}: {exc}")

    stats["records_stored"] = records_stored
    stats["finished_at"] = datetime.now(timezone.utc).isoformat()

    # Update module-level state for API consumption
    last_run_state["run_id"] = run_id
    last_run_state["timestamp"] = stats["finished_at"]
    last_run_state["signal_count"] = stats["signals_harvested"]
    last_run_state["record_count"] = records_stored

    # ── Briefing ──────────────────────────────────────────────────────────────
    try:
        from spec1_engine.briefing.generator import generate_brief
        from spec1_engine.briefing.templates import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE
        from spec1_engine.briefing.writer import write_brief
        if verbose:
            print(f"\n[Briefing] Generating daily intelligence brief...")
        brief_md, brief_prompts = generate_brief(stored_records, stats)
        brief_path = write_brief(brief_md, run_id, stats["finished_at"], brief_prompts)
        brief_word_count = len(brief_md.split())
        stats["brief_path"] = brief_path
        stats["brief_word_count"] = brief_word_count
        if verbose:
            print(f"  Brief written: {brief_path} ({brief_word_count} words)")
    except Exception as exc:
        logger.error("Briefing step failed: %s", exc)
        stats["errors"].append(f"briefing:{exc}")

    # ── Case workspace: Match signals to open cases and run research ──────────
    try:
        from spec1_engine.workspace.tracker import match_signals_to_cases
        from spec1_engine.workspace.researcher import run_research
        from spec1_engine.workspace.case import update_case, list_cases as list_open_cases

        if verbose:
            print(f"\n[Workspace] Processing investigation cases...")

        open_cases = list_open_cases(status="OPEN")
        cases_updated = 0

        if open_cases and signals:
            matches = match_signals_to_cases(signals)
            for case in open_cases:
                matched = matches.get(case.case_id, [])
                if matched:
                    finding = run_research(case, matched)
                    if finding:
                        update_case(case.case_id, matched, finding)
                        cases_updated += 1
                        if verbose:
                            print(f"  [{case.case_id}] {case.title} - {len(matched)} signal(s) matched")

        stats["cases_updated"] = cases_updated
        if verbose and cases_updated:
            print(f"  {cases_updated} case(s) updated with research findings")
    except ImportError:
        # Workspace not available, continue gracefully
        stats["cases_updated"] = 0
    except Exception as exc:
        logger.error("Workspace processing failed: %s", exc)
        stats["errors"].append(f"workspace:{exc}")
        stats["cases_updated"] = 0

    if verbose:
        print(f"\n{'='*60}")
        print(f"  Cycle Complete")
        print(f"  Records stored : {records_stored}")
        print(f"  Errors         : {len(stats['errors'])}")
        print(f"  Store file     : {store_path}")
        print(f"  Finished       : {stats['finished_at']}")
        print(f"{'='*60}\n")

    return stats


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="SPEC-1 Intelligence Engine")
    parser.add_argument("--store", default="spec1_intelligence.jsonl", help="JSONL output path")
    parser.add_argument("--env", default="production", help="Environment label")
    parser.add_argument("--timeout", type=int, default=15, help="Feed fetch timeout (seconds)")
    parser.add_argument("--max-signals", type=int, default=None, help="Cap signals processed")
    args = parser.parse_args()

    summary = run_cycle(
        store_path=Path(args.store),
        environment=args.env,
        feed_timeout=args.timeout,
        max_signals=args.max_signals,
        verbose=True,
    )

    print("\nRun Summary:")
    for k, v in summary.items():
        if k != "errors":
            print(f"  {k}: {v}")
    if summary.get("errors"):
        print(f"\n  Errors ({len(summary['errors'])}):")
        for e in summary["errors"][:10]:
            print(f"    - {e}")

    sys.exit(0 if summary["records_stored"] >= 0 else 1)
