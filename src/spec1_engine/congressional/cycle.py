"""Congressional Signal Pipeline — spec1_engine.congressional.

Collects and scores signals from congressional activity: bills, hearings,
floor votes, and member statements. Follows the same 4-gate + investigate
+ verify + analyze + store pattern as the OSINT and Quant pipelines.

Usage:
    python -m spec1_engine.congressional.cycle           # live mode (NYI — extend collector)
    python -m spec1_engine.congressional.cycle --sample  # run on built-in sample signals
"""

from __future__ import annotations

import hashlib
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from spec1_engine.core.ids import run_id as new_run_id
from spec1_engine.core.logging_utils import configure_root, get_logger
from spec1_engine.intelligence.store import JsonlStore
from spec1_engine.investigation.generator import generate_investigation
from spec1_engine.investigation.verifier import verify_investigation
from spec1_engine.intelligence.analyzer import analyze
from spec1_engine.schemas.models import Opportunity, ParsedSignal, Signal
from spec1_engine.signal.scorer import score_signal

configure_root()
logger = get_logger(__name__)

DEFAULT_STORE_PATH = Path("spec1_congressional_intelligence.jsonl")

last_run_state: dict = {
    "run_id": None,
    "timestamp": None,
    "signal_count": 0,
    "record_count": 0,
    "domain": "congressional",
}

# ─── Signal ID ────────────────────────────────────────────────────────────────

def _signal_id(url: str, title: str) -> str:
    return hashlib.sha256(f"{url}::{title}".encode()).hexdigest()[:16]


# ─── Sample signals ───────────────────────────────────────────────────────────

_SAMPLE_ITEMS: list[dict] = [
    {
        "title": "Senate Armed Services Committee Hearing on Defense Authorization",
        "source": "senate_gov",
        "url": "https://www.armed-services.senate.gov/hearings/sample-fy2026-ndaa",
        "author": "Senate Armed Services Committee",
        "text": (
            "The Senate Armed Services Committee convened an oversight hearing on the "
            "Fiscal Year 2026 National Defense Authorization Act. Testimony was provided "
            "by the Secretary of Defense and Chairman of the Joint Chiefs. The hearing "
            "examined military readiness, nuclear deterrence strategy, cyber warfare "
            "capabilities, and intelligence operations. Senators questioned officials on "
            "defense budget allocations, troop deployment posture, and alliance commitments "
            "under NATO. Key issues included hypersonic weapon development timelines, "
            "space command funding, and special operations authority. The committee approved "
            "a markup schedule for next month with a full Senate floor vote anticipated "
            "before the August recess."
        ),
        "velocity": 0.85,
        "metadata": {"chamber": "Senate", "committee": "Armed Services", "action": "hearing"},
    },
    {
        "title": "H.R. 4821 - Cyber Infrastructure Protection Act Introduced",
        "source": "congress_gov",
        "url": "https://www.congress.gov/bill/119th-congress/house-bill/4821/sample",
        "author": "Rep. Jane Smith (D-CA)",
        "text": (
            "H.R. 4821, the Cyber Infrastructure Protection Act, was introduced in the "
            "House of Representatives. The legislation would require federal agencies to "
            "adopt mandatory cybersecurity standards and expand CISA authority to conduct "
            "threat assessments of critical infrastructure. The bill follows a classified "
            "intelligence briefing on foreign cyber operations targeting energy and financial "
            "networks. Co-sponsors include members of the House Homeland Security Committee. "
            "The measure would authorize the Department of Defense to share cyber threat "
            "intelligence with private sector partners under a new security classification "
            "framework. A companion Senate bill is expected. Oversight provisions include "
            "quarterly reporting requirements to the House Intelligence Committee."
        ),
        "velocity": 0.70,
        "metadata": {"chamber": "House", "bill_number": "HR4821", "action": "introduced"},
    },
    {
        "title": "Senate Foreign Relations Committee Markup: Ukraine Security Assistance",
        "source": "foreign_relations_senate_gov",
        "url": "https://www.foreign.senate.gov/markups/sample-ukraine-assistance",
        "author": "Senate Foreign Relations Committee",
        "text": (
            "The Senate Foreign Relations Committee approved by a bipartisan vote a "
            "supplemental security assistance package for Ukraine. The markup authorizes "
            "additional military aid including air defense systems, artillery ammunition, "
            "and intelligence-sharing enhancements. Senators debated classified threat "
            "assessments regarding Russian military operations and escalation risk. The "
            "committee adopted an amendment requiring the Pentagon to certify Ukraine's "
            "battlefield readiness before releasing funds. Oversight provisions mandate "
            "inspector general audits of weapons deliveries. The measure proceeds to the "
            "full Senate floor with a cloture vote expected. Opposition senators cited "
            "concerns about nuclear escalation and alliance burden-sharing."
        ),
        "velocity": 0.90,
        "metadata": {"chamber": "Senate", "committee": "Foreign Relations", "action": "markup"},
    },
    {
        "title": "House Intelligence Committee Releases Declassified Threat Assessment Summary",
        "source": "intelligence_house_gov",
        "url": "https://intelligence.house.gov/news/sample-threat-assessment",
        "author": "House Permanent Select Committee on Intelligence",
        "text": (
            "The House Permanent Select Committee on Intelligence released a declassified "
            "summary of the annual worldwide threat assessment. The document highlights "
            "strategic competition from China and Russia, expanding Iranian nuclear "
            "enrichment activity, and North Korea ballistic missile developments. The CIA "
            "and NSA contributed findings on foreign influence operations targeting the "
            "United States election infrastructure. The committee flagged covert Chinese "
            "military buildup near Taiwan. Cybersecurity threats from state-sponsored actors "
            "against Pentagon systems are described as increasing in sophistication. FBI "
            "officials testified that counterintelligence cases have grown significantly. "
            "The committee voted to pursue further classified investigation into espionage "
            "operations disclosed in the assessment."
        ),
        "velocity": 0.95,
        "metadata": {
            "chamber": "House",
            "committee": "Intelligence",
            "action": "report_release",
        },
    },
    {
        "title": "Senate Floor Vote: National Security Supplemental Appropriations",
        "source": "senate_gov",
        "url": "https://www.senate.gov/legislative/votes/sample-national-security-supp",
        "author": "United States Senate",
        "text": (
            "The United States Senate passed by a bipartisan majority a national security "
            "supplemental appropriations bill. The legislation provides emergency funding "
            "for defense operations, intelligence activities, and foreign military assistance. "
            "Floor debate centered on military readiness, threat response capability, and "
            "oversight accountability. Amendments addressing special operations authority, "
            "nuclear deterrence posture, and cyber defense investment were adopted. Senators "
            "supporting the measure cited classified threat briefings on adversary military "
            "buildups. The bill proceeds to a House-Senate conference to reconcile differences "
            "before final passage and presidential signature. The vote reflects the Senate's "
            "commitment to alliance commitments and security strategy."
        ),
        "velocity": 0.92,
        "metadata": {"chamber": "Senate", "action": "floor_vote", "result": "passed"},
    },
]


def _sample_signals(run_id: str, environment: str = "sample") -> list[Signal]:
    """Build Signal objects from built-in sample congressional items."""
    now = datetime.now(timezone.utc)
    signals = []
    for item in _SAMPLE_ITEMS:
        sig = Signal(
            signal_id=_signal_id(item["url"], item["title"]),
            source=item["source"],
            source_type="congressional_record",
            text=item["text"],
            url=item["url"],
            author=item["author"],
            published_at=now,
            velocity=item["velocity"],
            engagement=0.0,
            run_id=run_id,
            environment=environment,
            metadata=item["metadata"],
        )
        signals.append(sig)
    return signals


# ─── ParsedSignal construction (no HTML parser required) ─────────────────────

_STOPWORDS: frozenset[str] = frozenset({
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "was", "are", "were", "be", "been",
    "has", "have", "had", "will", "would", "could", "should", "that", "this",
    "it", "its", "as", "into", "than", "then", "so", "if", "not", "also",
    "about", "their", "they", "them", "what", "when", "who", "which", "more",
    "said", "over", "after", "before", "between", "his", "her", "him",
})


def _make_parsed_signal(signal: Signal) -> ParsedSignal:
    """Build a ParsedSignal directly from congressional Signal text.

    Avoids the HTML-parsing dependency of signal.parser for clean-text signals.
    """
    import re

    text = signal.text or ""
    words = re.findall(r"\b[a-zA-Z]{4,}\b", text.lower())
    seen: set[str] = set()
    keywords: list[str] = []
    for w in words:
        if w not in _STOPWORDS and w not in seen:
            keywords.append(w)
            seen.add(w)
        if len(keywords) >= 15:
            break

    entity_pattern = re.compile(r"\b([A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,})*)\b")
    entities = list(dict.fromkeys(entity_pattern.findall(text)))[:10]

    return ParsedSignal(
        signal_id=signal.signal_id,
        cleaned_text=text,
        keywords=keywords,
        entities=entities,
        language="en",
        word_count=len(text.split()),
    )


# ─── Cycle ────────────────────────────────────────────────────────────────────

def run_congressional_cycle(
    store_path: Path = DEFAULT_STORE_PATH,
    run_id: Optional[str] = None,
    environment: str = "production",
    sample: bool = False,
    verbose: bool = True,
) -> dict:
    """Execute one full congressional signal cycle and return a summary dict.

    Args:
        store_path: Path to the JSONL output file.
        run_id: Run identifier; generated if not provided.
        environment: Environment label ('production', 'sample', 'test').
        sample: If True, use built-in sample signals instead of live collection.
        verbose: Print progress to stdout.

    Returns:
        Summary dict with run stats.
    """
    run_id = run_id or new_run_id()
    store = JsonlStore(store_path)
    started_at = datetime.now(timezone.utc).isoformat()

    if verbose:
        print(f"\n{'='*60}")
        print(f"  SPEC-1 Congressional Pipeline — Cycle Start")
        print(f"  run_id     : {run_id}")
        print(f"  domain     : congressional")
        print(f"  mode       : {'sample' if sample else 'live'}")
        print(f"  store      : {store_path}")
        print(f"  started    : {started_at}")
        print(f"{'='*60}\n")

    stats: dict = {
        "run_id": run_id,
        "domain": "congressional",
        "mode": "sample" if sample else "live",
        "started_at": started_at,
        "signals_collected": 0,
        "opportunities_found": 0,
        "investigations": 0,
        "outcomes": 0,
        "records_stored": 0,
        "errors": [],
    }

    # ── Step 1: Collect signals ───────────────────────────────────────────────
    if verbose:
        mode_label = "built-in sample data" if sample else "live congressional feeds"
        print(f"[1/4] Collecting congressional signals from {mode_label}...")

    try:
        if sample:
            signals = _sample_signals(run_id=run_id, environment="sample")
        else:
            # Live collection hook: extend with a real congressional API client here.
            # e.g. Congress.gov API, GovTrack RSS, ProPublica Congress API.
            logger.warning("Live congressional collector not yet wired — no signals collected.")
            signals = []

        stats["signals_collected"] = len(signals)
        if verbose:
            print(f"      Collected {len(signals)} signals")
    except Exception as exc:
        stats["errors"].append(f"collect:{exc}")
        stats["finished_at"] = datetime.now(timezone.utc).isoformat()
        return stats

    # ── Step 2: Score — 4 gates ───────────────────────────────────────────────
    if verbose:
        print(f"[2/4] Scoring through 4 gates (credibility/volume/velocity/novelty)...")

    opportunities: list[tuple[Signal, ParsedSignal, Opportunity]] = []
    blocked = 0
    for sig in signals:
        try:
            parsed = _make_parsed_signal(sig)
            opp = score_signal(sig, parsed, run_id=run_id)
            if opp is not None:
                opportunities.append((sig, parsed, opp))
            else:
                blocked += 1
        except Exception as exc:
            stats["errors"].append(f"score:{sig.signal_id}:{exc}")
            blocked += 1

    stats["opportunities_found"] = len(opportunities)
    if verbose:
        print(f"      Opportunities: {len(opportunities)} | Blocked: {blocked}")

    # ── Steps 3–4: Investigate → Verify → Analyze → Store ────────────────────
    if verbose:
        print(f"[3/4] Investigating and verifying opportunities...")
        print(f"[4/4] Analyzing and writing to {store_path}\n")

    records_stored = 0
    for sig, parsed, opp in opportunities:
        try:
            inv = generate_investigation(opp, sig, parsed)
            stats["investigations"] += 1

            outcome = verify_investigation(inv)
            stats["outcomes"] += 1

            record = analyze(opp, inv, outcome, sig)

            store.append({
                **record.to_dict(),
                "run_id": run_id,
                "domain": "congressional",
                "signal_id": sig.signal_id,
                "signal_source": sig.source,
                "signal_url": sig.url,
                "environment": sig.environment,
                "chamber": sig.metadata.get("chamber", "unknown"),
                "committee": sig.metadata.get("committee", ""),
                "action": sig.metadata.get("action", ""),
                "opportunity_id": opp.opportunity_id,
                "opportunity_score": opp.score,
                "opportunity_priority": opp.priority,
                "gate_results": opp.gate_results,
                "investigation_id": inv.investigation_id,
                "hypothesis": inv.hypothesis,
                "outcome_classification": outcome.classification,
                "outcome_confidence": outcome.confidence,
            })
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

    last_run_state.update({
        "run_id": run_id,
        "timestamp": stats["finished_at"],
        "signal_count": stats["signals_collected"],
        "record_count": records_stored,
    })

    if verbose:
        print(f"\n{'='*60}")
        print(f"  Congressional Cycle Complete")
        print(f"  Signals collected : {stats['signals_collected']}")
        print(f"  Opportunities     : {stats['opportunities_found']}")
        print(f"  Records stored    : {records_stored}")
        print(f"  Errors            : {len(stats['errors'])}")
        print(f"  Store             : {store_path}")
        print(f"{'='*60}\n")

    return stats


# ─── CLI ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="SPEC-1 Congressional Signal Pipeline")
    parser.add_argument(
        "--sample",
        action="store_true",
        help="Run on built-in sample signals instead of live collection.",
    )
    parser.add_argument(
        "--store",
        default=str(DEFAULT_STORE_PATH),
        help="Path to JSONL output file.",
    )
    parser.add_argument(
        "--env",
        default="production",
        help="Environment label.",
    )
    args = parser.parse_args()

    summary = run_congressional_cycle(
        store_path=Path(args.store),
        environment=args.env,
        sample=args.sample,
        verbose=True,
    )

    if summary.get("errors"):
        print(f"\nErrors ({len(summary['errors'])}):")
        for e in summary["errors"][:10]:
            print(f"  - {e}")

    sys.exit(0 if summary["records_stored"] >= 0 else 1)
