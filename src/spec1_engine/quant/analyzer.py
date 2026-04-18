"""Quant Analyzer — classifies market patterns into IntelligenceRecord instances.

Mirrors intelligence/analyzer.py but uses market-specific classification
logic: price action patterns, sector rotation signals, and anomaly flags.
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
from spec1_engine.quant.collector import TICKER_SECTOR

# Classification weight — how much outcome confidence feeds into final score
CLASSIFICATION_WEIGHTS: dict[str, float] = {
    "CORROBORATED": 1.0,
    "ESCALATE":     0.85,
    "INVESTIGATE":  0.70,
    "MONITOR":      0.55,
    "CONFLICTED":   0.35,
    "ARCHIVE":      0.15,
}

# Sector credibility weights — defense/cyber higher signal-to-noise for SPEC-1
SECTOR_WEIGHTS: dict[str, float] = {
    "defense": 0.88,
    "cyber":   0.85,
    "energy":  0.78,
    "macro":   0.82,
    "unknown": 0.65,
}


def _detect_pattern(signal: Signal, opportunity: Opportunity) -> str:
    """Identify the market pattern driving this opportunity."""
    daily_ret = signal.velocity
    rel_vol   = signal.engagement
    ticker    = signal.source
    sector    = TICKER_SECTOR.get(ticker, "unknown")
    priority  = opportunity.priority

    if abs(daily_ret) >= 0.03 and rel_vol >= 2.0:
        label = "HIGH_VOL_BREAKOUT" if daily_ret > 0 else "HIGH_VOL_BREAKDOWN"
    elif abs(daily_ret) >= 0.015:
        label = "MOMENTUM_UP" if daily_ret > 0 else "MOMENTUM_DOWN"
    elif rel_vol >= 2.5:
        label = "VOLUME_SPIKE"
    elif rel_vol >= 1.5:
        label = "ELEVATED_VOLUME"
    else:
        label = "SIGNAL"

    date_str = signal.published_at.strftime("%Y-%m-%d")
    return f"[{priority}][{sector.upper()}] {ticker} {label} | ret={daily_ret:+.3%} rel_vol={rel_vol:.2f}x | {date_str}"


def analyze(
    opportunity: Opportunity,
    investigation: Investigation,
    outcome: Outcome,
    signal: Signal,
) -> IntelligenceRecord:
    """Produce an IntelligenceRecord from quant pipeline results."""
    sector         = TICKER_SECTOR.get(signal.source, "unknown")
    source_weight  = SECTOR_WEIGHTS.get(sector, 0.65)
    analyst_weight = 0.70  # quant domain uses systematic weight, not human analyst

    classification_weight = CLASSIFICATION_WEIGHTS.get(outcome.classification, 0.50)

    final_confidence = round(
        outcome.confidence  * 0.50
        + source_weight     * 0.25
        + analyst_weight    * 0.15
        + classification_weight * 0.10,
        4,
    )

    return IntelligenceRecord(
        record_id=f"rec-q-{uuid.uuid4().hex[:10]}",
        pattern=_detect_pattern(signal, opportunity),
        classification=outcome.classification,
        confidence=min(final_confidence, 0.99),
        source_weight=source_weight,
        analyst_weight=analyst_weight,
    )
