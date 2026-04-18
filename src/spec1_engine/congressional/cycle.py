"""Congressional Trade Pipeline — full cycle runner.

Collects, scores, and analyzes congressional stock trades for
conflict-of-interest (COI) patterns using a 3-source data fallback chain.

Usage:
    python -m spec1_engine.congressional.cycle            # live mode
    python -m spec1_engine.congressional.cycle --sample  # built-in sample data
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from spec1_engine.core.ids import run_id as new_run_id
from spec1_engine.core.logging_utils import configure_root, get_logger
from spec1_engine.intelligence.store import JsonlStore
from spec1_engine.investigation.generator import generate_investigation
from spec1_engine.investigation.verifier import verify_investigation
from spec1_engine.schemas.models import ParsedSignal, Signal

from spec1_engine.congressional.collector import fetch_trades, SAMPLE_TRADES
from spec1_engine.congressional.parser import parse_batch
from spec1_engine.congressional.scorer import score_signal, clear_novelty_cache
from spec1_engine.congressional.analyzer import analyze

configure_root()
logger = get_logger(__name__)

DEFAULT_STORE_PATH = Path("spec1_congressional_intelligence.jsonl")
KILL_FILE = Path(".cls_kill")

# Module-level state consumed by API /congressional/status
last_run_state: dict = {
    "run_id":       None,
    "timestamp":    None,
    "signal_count": 0,
    "record_count": 0,
    "domain":       "congressional",
}


# ─── ParsedSignal builder (no HTML parser required) ───────────────────────────

def _make_parsed_signal(signal: Signal) -> ParsedSignal:
    """Build a minimal ParsedSignal from a congressional trade Signal.

    Bypasses the HTML-dependent signal.parser for clean structured text.
    """
    politician = signal.metadata.get("politician", "")
    ticker     = signal.metadata.get("ticker", signal.source)
    committee  = signal.metadata.get("committee", "")
    trade_type = signal.metadata.get("trade_type", "")

    keywords = [
        w for w in [
            ticker.lower(),
            trade_type.lower().split()[0] if trade_type else None,
            committee.lower().split()[0] if committee else None,
            "congressional", "trade", "disclosure",
        ]
        if w
    ]

    entities = [e for e in [politician, ticker, committee] if e]

    return ParsedSignal(
        signal_id=signal.signal_id,
        cleaned_text=signal.text,
        keywords=keywords[:15],
        entities=entities[:10],
        language="en",
        word_count=len(signal.text.split()),
    )


# ─── Cycle ────────────────────────────────────────────────────────────────────

def run_congressional_cycle(
    store_path: Path = DEFAULT_STORE_PATH,
    run_id: Optional[str] = None,
    sample: bool = False,
    verbose: bool = True,
) -> dict:
    """Execute one full congressional trade cycle and return a summary dict.

    Checks the kill file before starting. Never raises — all errors are
    collected in stats['errors'].

    Args:
        store_path: JSONL output path.
        run_id: Run identifier; auto-generated if not provided.
        sample: If True, bypass live fetch and use built-in sample trades.
        verbose: Print progress banners to stdout.

    Returns:
        Summary dict with run stats (domain, trades_fetched, signals_parsed,
        opportunities_found, records_stored, errors, …).
    """
    if KILL_FILE.exists():
        logger.warning("Kill file present — congressional cycle aborted.")
        return {"status": "killed", "run_id": None, "domain": "congressional"}

    run_id = run_id or new_run_id()
    store  = JsonlStore(store_path)
    started_at = datetime.now(timezone.utc).isoformat()
    clear_novelty_cache()

    if verbose:
        print(f"\n{'='*60}")
        print(f"  SPEC-1 Congressional Trade Pipeline")
        print(f"  run_id   : {run_id}")
        print(f"  mode     : {'sample' if sample else 'live'}")
        print(f"  store    : {store_path}")
        print(f"  started  : {started_at}")
        print(f"{'='*60}\n")

    stats: dict = {
        "run_id":               run_id,
        "domain":               "congressional",
        "mode":                 "sample" if sample else "live",
        "started_at":           started_at,
        "trades_fetched":       0,
        "signals_parsed":       0,
        "opportunities_found":  0,
        "investigations":       0,
        "outcomes":             0,
        "records_stored":       0,
        "errors":               [],
    }

    # ── Step 1: Collect ───────────────────────────────────────────────────────
    src_label = "sample data" if sample else "live (Quiver → Capitol Trades → fallback)"
    if verbose:
        print(f"[1/4] Collecting congressional trades from {src_label}...")

    try:
        raw_trades = list(SAMPLE_TRADES) if sample else fetch_trades()
        stats["trades_fetched"] = len(raw_trades)
        if verbose:
            print(f"      Fetched {len(raw_trades)} raw trades")
    except Exception as exc:
        stats["errors"].append(f"collect:{exc}")
        stats["finished_at"] = datetime.now(timezone.utc).isoformat()
        return stats

    # ── Step 2: Parse → Signals ───────────────────────────────────────────────
    if verbose:
        print(f"[2/4] Parsing into Signal objects...")

    signals = parse_batch(raw_trades, run_id=run_id, environment="congressional")
    stats["signals_parsed"] = len(signals)
    if verbose:
        print(f"      Parsed {len(signals)} signals")

    # ── Step 3: Score — 4 gates ───────────────────────────────────────────────
    if verbose:
        print(f"[3/4] Scoring (credibility / amount / recency / novelty)...")

    opportunities = []
    blocked = 0
    for sig in signals:
        try:
            opp = score_signal(sig, run_id=run_id)
            if opp is not None:
                opportunities.append((sig, opp))
            else:
                blocked += 1
        except Exception as exc:
            stats["errors"].append(f"score:{sig.signal_id}:{exc}")
            blocked += 1

    stats["opportunities_found"] = len(opportunities)
    if verbose:
        print(f"      Opportunities: {len(opportunities)} | Blocked: {blocked}")

    # ── Step 4: Investigate → Verify → Analyze → Store ───────────────────────
    if verbose:
        print(f"[4/4] Investigating, verifying, analyzing...\n")

    records_stored = 0
    for sig, opp in opportunities:
        try:
            parsed  = _make_parsed_signal(sig)
            inv     = generate_investigation(opp, sig, parsed)
            stats["investigations"] += 1

            outcome = verify_investigation(inv)
            stats["outcomes"] += 1

            record  = analyze(opp, inv, outcome, sig)

            store.append({
                **record.to_dict(),
                "run_id":                 run_id,
                "domain":                 "congressional",
                "signal_id":              sig.signal_id,
                "signal_source":          sig.source,
                "signal_url":             sig.url,
                "environment":            sig.environment,
                "politician":             sig.metadata.get("politician", ""),
                "ticker":                 sig.metadata.get("ticker", ""),
                "amount":                 sig.metadata.get("amount", 0),
                "trade_type":             sig.metadata.get("trade_type", ""),
                "committee":              sig.metadata.get("committee", ""),
                "trade_date":             sig.metadata.get("trade_date", ""),
                "opportunity_id":         opp.opportunity_id,
                "opportunity_score":      opp.score,
                "opportunity_priority":   opp.priority,
                "gate_results":           opp.gate_results,
                "investigation_id":       inv.investigation_id,
                "hypothesis":             inv.hypothesis,
                "outcome_classification": outcome.classification,
                "outcome_confidence":     outcome.confidence,
            })
            records_stored += 1

            if verbose:
                pol  = sig.metadata.get("politician", "?")[:28]
                tkr  = sig.metadata.get("ticker", "?")
                amt  = sig.metadata.get("amount", 0)
                print(
                    f"  [{records_stored:03d}] [{opp.priority:8s}] "
                    f"{pol:28s} {tkr:6s} ${amt:>10,}  class={record.classification}"
                )

        except Exception as exc:
            stats["errors"].append(f"pipeline:{opp.opportunity_id}:{exc}")
            if verbose:
                print(f"  [ERR] {opp.opportunity_id}: {exc}")

    stats["records_stored"] = records_stored
    stats["finished_at"]    = datetime.now(timezone.utc).isoformat()

    last_run_state.update({
        "run_id":       run_id,
        "timestamp":    stats["finished_at"],
        "signal_count": stats["signals_parsed"],
        "record_count": records_stored,
    })

    if verbose:
        print(f"\n{'='*60}")
        print(f"  Congressional Cycle Complete")
        print(f"  Trades fetched    : {stats['trades_fetched']}")
        print(f"  Signals parsed    : {stats['signals_parsed']}")
        print(f"  Opportunities     : {stats['opportunities_found']}")
        print(f"  Records stored    : {records_stored}")
        print(f"  Errors            : {len(stats['errors'])}")
        print(f"  Store             : {store_path}")
        print(f"{'='*60}\n")

    return stats


# ─── CLI ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="SPEC-1 Congressional Trade Pipeline")
    parser.add_argument(
        "--sample", action="store_true",
        help="Use built-in sample trades instead of live fetch.",
    )
    parser.add_argument(
        "--store", default=str(DEFAULT_STORE_PATH),
        help="JSONL output file path.",
    )
    args = parser.parse_args()

    summary = run_congressional_cycle(
        store_path=Path(args.store),
        sample=args.sample,
        verbose=True,
    )

    if summary.get("errors"):
        print(f"\nErrors ({len(summary['errors'])}):")
        for e in summary["errors"][:10]:
            print(f"  - {e}")

    sys.exit(0 if summary.get("records_stored", 0) >= 0 else 1)
