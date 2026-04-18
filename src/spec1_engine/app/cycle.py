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
load_dotenv()  # loads .env from cwd if present

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

    Derives each required field from the collected signal batch:
    - topic: most common keyword across all parsed signals
    - entities: deduplicated union of parsed entities (up to 20)
    - sources: unique source names from signals
    - narrative_markets: same as sources (each distinct feed = one media market)
    - fara_matches: empty list — hook for future FARA integration
    - legislation_matches: empty list — hook for future legislation integration
    - consensus_velocity: average velocity across signals (proxy for rapid consensus)
    - origin_traceable: True — RSS sources have verifiable origin by default
    """
    all_keywords: list[str] = []
    all_entities: list[str] = []
    all_sources: list[str] = []
    velocities: list[float] = []

    for ps in parsed_signals:
        all_entities.extend(ps.entities[:5])
        all_keywords.extend(ps.keywords[:5])

    for sig in signals:
        all_sources.append(sig.source)
        velocities.append(float(sig.velocity))

    topic_counts = Counter(all_keywords)
    topic = topic_counts.most_common(1)[0][0] if topic_counts else "unknown"
    unique_sources = list(dict.fromkeys(all_sources))  # preserve insertion order, dedupe
    avg_velocity = sum(velocities) / len(velocities) if velocities else 0.0

    return {
        "topic": topic,
        "entities": list(dict.fromkeys(all_entities))[:20],
        "sources": unique_sources,
        "fara_matches": [],        # Hook: populate from FARA API integration
        "legislation_matches": [], # Hook: populate from model-legislation DB
        "narrative_markets": unique_sources,
        "consensus_velocity": avg_velocity,
        "origin_traceable": True,  # RSS sources are traceable by default
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

    # ── Psyop scoring — runs after collection, before brief assembly ──────────
    if verbose:
        print(f"\n[Psyop] Scoring signal batch for influence-operation patterns...")
    try:
        from spec1_engine.cls_psyop.scorer import DEFAULT_STORE_PATH, score_psyop
        psyop_signal = _build_psyop_signal(signals, parsed_signals)
        psyop_result = score_psyop(
            psyop_signal,
            run_id=run_id,
            store_path=DEFAULT_STORE_PATH,
        )
        stats["psyop_score"] = psyop_result["score"]
        stats["psyop_classification"] = psyop_result["classification"]
        stats["psyop_patterns_fired"] = psyop_result["patterns_fired"]
        if verbose:
            print(
                f"      score={psyop_result['score']} "
                f"class={psyop_result['classification']} "
                f"patterns={psyop_result['patterns_fired'] or '(none)'}"
            )
    except Exception as exc:
        logger.exception("Psyop scoring step failed: %s", exc)
        stats["errors"].append(f"psyop:{exc}")
        if verbose:
            print(f"      [WARN] Psyop scoring failed: {exc}")

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
        from spec1_engine.briefing.writer import write_brief
        if verbose:
            print(f"\n[Briefing] Generating daily intelligence brief...")
        brief_md = generate_brief(stored_records, stats)
        brief_path = write_brief(brief_md, run_id, stats["finished_at"])
        brief_word_count = len(brief_md.split())
        stats["brief_path"] = brief_path
        stats["brief_word_count"] = brief_word_count
        if verbose:
            print(f"  Brief written: {brief_path} ({brief_word_count} words)")
    except Exception as exc:
        logger.error("Briefing step failed: %s", exc)
        stats["errors"].append(f"briefing:{exc}")

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
