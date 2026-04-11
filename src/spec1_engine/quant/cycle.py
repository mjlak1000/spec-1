"""Quant Cycle — market data pipeline.

Full loop:
  OHLCV collect → parse → score (4 gates) → investigation → verify → analyze → JSONL store

Usage:
    python -m spec1_engine.quant.cycle
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from spec1_engine.core.ids import run_id as new_run_id
from spec1_engine.core.logging_utils import configure_root, get_logger
from spec1_engine.schemas.models import Signal
from spec1_engine.intelligence.store import JsonlStore
from spec1_engine.investigation.generator import generate_investigation
from spec1_engine.investigation.verifier import verify_investigation
from spec1_engine.quant.collector import fetch_all, ALL_TICKERS
from spec1_engine.quant.parser import parse_dataframe
from spec1_engine.quant.scorer import score_signal, clear_seen
from spec1_engine.quant.analyzer import analyze

configure_root()
logger = get_logger(__name__)

DEFAULT_STORE_PATH = Path("spec1_quant_intelligence.jsonl")

# Module-level state — consumed by API /cycle/status equivalent
last_run_state: dict = {
    "run_id": None,
    "timestamp": None,
    "signal_count": 0,
    "record_count": 0,
    "domain": "quant",
}


def _make_parsed_signal(signal: Signal):
    """Wrap a quant Signal into a minimal ParsedSignal for the shared pipeline."""
    from spec1_engine.schemas.models import ParsedSignal
    ticker  = signal.source
    meta    = signal.metadata
    ret     = meta.get("daily_return", signal.velocity)
    rel_vol = meta.get("relative_volume", signal.engagement)
    sector  = meta.get("sector", "unknown")

    # Synthetic keywords sufficient for investigation generation
    keywords = [ticker, sector, "market_data"]
    if abs(ret) >= 0.03:
        keywords.append("breakout" if ret > 0 else "breakdown")
    if rel_vol >= 2.0:
        keywords.append("volume_spike")

    return ParsedSignal(
        signal_id=signal.signal_id,
        cleaned_text=signal.text,
        keywords=keywords,
        entities=[ticker],
        language="en",
        word_count=len(signal.text.split()),
    )


def run_quant_cycle(
    store_path: Path = DEFAULT_STORE_PATH,
    run_id: Optional[str] = None,
    tickers: Optional[list[str]] = None,
    period: str = "3mo",
    interval: str = "1d",
    latest_only: bool = True,
    verbose: bool = True,
) -> dict:
    """Execute one full quant cycle and return a summary dict."""
    run_id = run_id or new_run_id()
    store  = JsonlStore(store_path)
    started_at = datetime.now(timezone.utc).isoformat()

    clear_seen(run_id)

    if verbose:
        print(f"\n{'='*60}")
        print(f"  SPEC-1 Quant Engine — Cycle Start")
        print(f"  run_id    : {run_id}")
        print(f"  domain    : quant")
        print(f"  store     : {store_path}")
        print(f"  started   : {started_at}")
        print(f"{'='*60}\n")

    stats: dict = {
        "run_id":              run_id,
        "domain":              "quant",
        "started_at":          started_at,
        "tickers_requested":   len(tickers or ALL_TICKERS),
        "tickers_fetched":     0,
        "signals_parsed":      0,
        "opportunities_found": 0,
        "investigations":      0,
        "outcomes":            0,
        "records_stored":      0,
        "errors":              [],
    }

    # ── Step 1: Collect OHLCV ─────────────────────────────────────────────────
    if verbose:
        print("[1/5] Collecting OHLCV data from yfinance...")
    try:
        ohlcv = fetch_all(tickers=tickers, period=period, interval=interval)
        stats["tickers_fetched"] = len(ohlcv)
        if verbose:
            print(f"      Fetched {len(ohlcv)} tickers")
    except Exception as exc:
        stats["errors"].append(f"fetch_all:{exc}")
        stats["finished_at"] = datetime.now(timezone.utc).isoformat()
        return stats

    # ── Step 2: Parse → Signal ────────────────────────────────────────────────
    if verbose:
        print(f"[2/5] Parsing OHLCV rows into signals...")
    signals: list[Signal] = []
    for ticker, df in ohlcv.items():
        try:
            batch = parse_dataframe(ticker, df, run_id=run_id, latest_only=latest_only)
            signals.extend(batch)
        except Exception as exc:
            stats["errors"].append(f"parse:{ticker}:{exc}")
    stats["signals_parsed"] = len(signals)
    if verbose:
        print(f"      Parsed {len(signals)} signals")

    # ── Step 3: Score — 4 gates ───────────────────────────────────────────────
    if verbose:
        print("[3/5] Scoring through 4 gates (credibility/volume/velocity/novelty)...")
    opportunities = []
    blocked = 0
    for sig in signals:
        try:
            opp = score_signal(sig, run_id=run_id)
            if opp:
                opportunities.append((sig, opp))
            else:
                blocked += 1
        except Exception as exc:
            stats["errors"].append(f"score:{sig.signal_id}:{exc}")
            blocked += 1
    stats["opportunities_found"] = len(opportunities)
    if verbose:
        print(f"      Opportunities: {len(opportunities)} | Blocked: {blocked}")

    # ── Steps 4–5: Investigate → Verify → Analyze → Store ────────────────────
    if verbose:
        print("[4/5] Investigating, verifying, analyzing...")
        print(f"[5/5] Writing to {store_path}\n")

    records_stored = 0
    for sig, opp in opportunities:
        try:
            parsed = _make_parsed_signal(sig)

            inv     = generate_investigation(opp, sig, parsed)
            stats["investigations"] += 1

            outcome = verify_investigation(inv)
            stats["outcomes"] += 1

            record  = analyze(opp, inv, outcome, sig)

            store.append({
                **record.to_dict(),
                "run_id":               run_id,
                "domain":               "quant",
                "signal_id":            sig.signal_id,
                "ticker":               sig.source,
                "sector":               sig.metadata.get("sector", "unknown"),
                "signal_url":           sig.url,
                "opportunity_id":       opp.opportunity_id,
                "opportunity_score":    opp.score,
                "opportunity_priority": opp.priority,
                "gate_results":         opp.gate_results,
                "daily_return":         sig.velocity,
                "relative_volume":      sig.engagement,
                "close":                sig.metadata.get("close", 0.0),
                "investigation_id":     inv.investigation_id,
                "hypothesis":           inv.hypothesis,
                "outcome_classification": outcome.classification,
                "outcome_confidence":     outcome.confidence,
            })
            records_stored += 1

            if verbose:
                ticker = sig.source
                ret    = sig.velocity
                rvol   = sig.engagement
                print(
                    f"  [{records_stored:03d}] [{opp.priority:8s}] {ticker:10s} "
                    f"ret={ret:+.3%} rvol={rvol:.2f}x score={opp.score:.3f} "
                    f"class={outcome.classification}"
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
        print(f"  Quant Cycle Complete")
        print(f"  Tickers fetched : {stats['tickers_fetched']}")
        print(f"  Signals parsed  : {stats['signals_parsed']}")
        print(f"  Opportunities   : {stats['opportunities_found']}")
        print(f"  Records stored  : {records_stored}")
        print(f"  Errors          : {len(stats['errors'])}")
        print(f"  Store           : {store_path}")
        print(f"{'='*60}\n")

    return stats


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="SPEC-1 Quant Cycle")
    parser.add_argument("--store",    default="spec1_quant_intelligence.jsonl")
    parser.add_argument("--period",   default="3mo")
    parser.add_argument("--interval", default="1d")
    parser.add_argument("--all-rows", action="store_true",
                        help="Parse all historical rows, not just latest")
    parser.add_argument("--tickers",  nargs="*", default=None,
                        help="Override ticker list")
    args = parser.parse_args()

    summary = run_quant_cycle(
        store_path=Path(args.store),
        tickers=args.tickers,
        period=args.period,
        interval=args.interval,
        latest_only=not args.all_rows,
        verbose=True,
    )

    if summary.get("errors"):
        print(f"\nErrors ({len(summary['errors'])}):")
        for e in summary["errors"][:10]:
            print(f"  - {e}")

    sys.exit(0 if summary["records_stored"] >= 0 else 1)
