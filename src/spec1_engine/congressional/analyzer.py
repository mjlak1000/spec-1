"""Congressional trade analyzer — conflict-of-interest scoring.

Five scoring dimensions:
  committee_overlap    — politician's committee oversees the traded sector
  timing_proximity     — trade recency relative to legislative activity
  amount_significance  — normalized trade size
  trade_direction      — purchase vs. sale in context of pending legislation
  repeat_pattern       — proxy via outcome classification confidence

Final COI score (0.0 – 1.0) maps to:
  >= 0.80 → Corroborated
  >= 0.65 → Escalate
  >= 0.45 → Investigate
  <  0.45 → Monitor
"""

from __future__ import annotations

import uuid

from spec1_engine.schemas.models import (
    IntelligenceRecord,
    Investigation,
    Opportunity,
    Outcome,
    Signal,
)

# ─── Committee → traded ticker/sector overlap ─────────────────────────────────

COMMITTEE_SECTORS: dict[str, set[str]] = {
    "armed services":    {"LMT", "RTX", "NOC", "GD", "BA", "HII", "L3", "LDOS"},
    "intelligence":      {"PANW", "CRWD", "S", "FTNT", "PLTR", "BAH", "SAIC"},
    "homeland security": {"PANW", "CRWD", "S", "FTNT", "ICE", "GEO", "CXW"},
    "financial services":{"JPM", "GS", "BAC", "WFC", "C", "MS", "BLK", "V", "MA"},
    "energy":            {"XOM", "CVX", "COP", "SLB", "HAL", "PSX", "VLO"},
    "health":            {"UNH", "JNJ", "PFE", "ABT", "MRK", "BMY", "LLY"},
    "foreign affairs":   {"LMT", "RTX", "NOC", "BA", "GD"},
    "judiciary":         {"META", "GOOGL", "AMZN", "MSFT", "NFLX", "AAPL"},
    "commerce":          {"AMZN", "META", "GOOGL", "MSFT", "NFLX", "SHOP"},
}

# ─── Classification thresholds ────────────────────────────────────────────────

_THRESHOLDS = [
    (0.80, "Corroborated"),
    (0.65, "Escalate"),
    (0.45, "Investigate"),
    (0.00, "Monitor"),
]

_OUTCOME_REPEAT: dict[str, float] = {
    "Corroborated": 1.0,
    "Escalate":     0.80,
    "Investigate":  0.60,
    "Monitor":      0.40,
    "Conflicted":   0.30,
    "Archive":      0.10,
}


# ─── Dimension scorers ────────────────────────────────────────────────────────

def _committee_overlap(signal: Signal) -> float:
    """Score 1.0 if committee directly oversees traded ticker; 0.35 partial; 0.10 unknown."""
    committee = signal.metadata.get("committee", "").lower()
    ticker = signal.metadata.get("ticker", "").upper()
    for key, tickers in COMMITTEE_SECTORS.items():
        if key in committee:
            return 1.0 if ticker in tickers else 0.35
    return 0.10


def _timing_proximity(signal: Signal) -> float:
    """Signal velocity: 1.0 within 7 days (parser-set), 0.5 otherwise."""
    return signal.velocity


def _amount_significance(signal: Signal) -> float:
    """Normalized trade size via engagement field (log10(amount)/7 from parser)."""
    return min(signal.engagement, 1.0)


def _trade_direction(signal: Signal) -> float:
    """Purchases score 0.80 (buying ahead of committee action); sales 0.60; unknown 0.50."""
    trade_type = signal.metadata.get("trade_type", "").lower()
    if any(w in trade_type for w in ("purchase", "buy")):
        return 0.80
    if any(w in trade_type for w in ("sale", "sell")):
        return 0.60
    return 0.50


def _repeat_pattern(outcome: Outcome) -> float:
    """Proxy for repeat behaviour through outcome classification weight."""
    return _OUTCOME_REPEAT.get(outcome.classification, 0.40)


def _classify(score: float) -> str:
    for threshold, label in _THRESHOLDS:
        if score >= threshold:
            return label
    return "Monitor"


# ─── Public analyzer ─────────────────────────────────────────────────────────

def analyze(
    opportunity: Opportunity,
    investigation: Investigation,
    outcome: Outcome,
    signal: Signal,
) -> IntelligenceRecord:
    """Produce an IntelligenceRecord from congressional trade pipeline results.

    Blends five conflict-of-interest dimensions into a final confidence score.

    Args:
        opportunity: Scored Opportunity from the congressional scorer.
        investigation: Generated Investigation from the investigation generator.
        outcome: Verified Outcome (or fallback) from the verifier.
        signal: Parsed congressional trade Signal.

    Returns:
        IntelligenceRecord with COI confidence and pattern label.
    """
    comm_score   = _committee_overlap(signal)
    timing_score = _timing_proximity(signal)
    amount_score = _amount_significance(signal)
    dir_score    = _trade_direction(signal)
    repeat_score = _repeat_pattern(outcome)

    coi_score = round(
        comm_score   * 0.30
        + timing_score * 0.20
        + amount_score * 0.20
        + dir_score    * 0.15
        + repeat_score * 0.15,
        4,
    )

    classification = _classify(coi_score)

    politician = signal.metadata.get("politician", "Unknown")
    ticker     = signal.metadata.get("ticker", "?")
    amount     = signal.metadata.get("amount", 0)
    trade_type = signal.metadata.get("trade_type", "trade")
    committee  = signal.metadata.get("committee", "?")

    pattern = (
        f"[{opportunity.priority}][COI] {politician} — {trade_type} {ticker} "
        f"${amount:,} | committee={committee} "
        f"overlap={comm_score:.2f} timing={timing_score:.2f} amount={amount_score:.2f}"
    )

    return IntelligenceRecord(
        record_id=f"rec-c-{uuid.uuid4().hex[:10]}",
        pattern=pattern,
        classification=classification,
        confidence=min(coi_score, 0.99),
        source_weight=opportunity.score,
        analyst_weight=comm_score,
    )
