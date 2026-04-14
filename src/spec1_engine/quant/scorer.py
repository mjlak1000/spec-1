"""Quant Scorer — 4 technical gates for market data signals.

Gates:
  1. Credibility — ticker must be in the known watchlist
  2. Volume      — relative volume > 1.2 (unusual volume required)
  3. Velocity    — |daily_return| > 0.005 (minimum 0.5% move)
  4. Novelty     — ticker+date not already scored in this run (dedup)

Only signals passing all 4 gates become Opportunity instances.
"""

from __future__ import annotations

import uuid
from typing import Optional

from spec1_engine.schemas.models import Opportunity, Signal
from spec1_engine.quant.collector import ALL_TICKERS

# ── Gate thresholds ────────────────────────────────────────────────────────────

VOLUME_THRESHOLD     = 0.8    # relative volume must exceed this (0.2% above 30-day avg)
VELOCITY_THRESHOLD   = 0.002  # |daily_return| must exceed this (0.2% minimum move)
ELEVATED_VELOCITY    = 0.02   # velocity to trigger ELEVATED priority (2%+ move)
CREDIBILITY_SCORE    = 0.80   # all watchlist tickers get this base credibility

# ── Run-level novelty dedup ────────────────────────────────────────────────────
# Maps run_id → set of "ticker::date" strings already scored this run.
_seen: dict[str, set[str]] = {}


def _novelty_key(signal: Signal) -> str:
    date_str = signal.published_at.strftime("%Y-%m-%d")
    return f"{signal.source}::{date_str}"


def _is_novel(signal: Signal, run_id: str) -> bool:
    key = _novelty_key(signal)
    if run_id not in _seen:
        _seen[run_id] = set()
    if key in _seen[run_id]:
        return False
    _seen[run_id].add(key)
    return True


def clear_seen(run_id: str | None = None) -> None:
    """Clear the novelty cache. If run_id is None, clear all runs."""
    if run_id is None:
        _seen.clear()
    else:
        _seen.pop(run_id, None)


# ── Composite score ────────────────────────────────────────────────────────────

def _composite(signal: Signal) -> float:
    """Weighted composite from 0‒1. Higher = more actionable."""
    rel_vol     = signal.engagement          # Gate 2 raw value
    daily_ret   = abs(signal.velocity)       # Gate 3 raw value

    # Normalise relative volume: 0.8 → 0.0 … 2.0+ → 1.0
    vol_norm = min((rel_vol - VOLUME_THRESHOLD) / (2.0 - VOLUME_THRESHOLD), 1.0)
    vol_norm = max(vol_norm, 0.0)

    # Normalise velocity: 0.2% → 0.0 … 2%+ → 1.0
    vel_norm = min((daily_ret - VELOCITY_THRESHOLD) / (0.02 - VELOCITY_THRESHOLD), 1.0)
    vel_norm = max(vel_norm, 0.0)

    return round(
        CREDIBILITY_SCORE   * 0.30
        + vol_norm          * 0.35
        + vel_norm          * 0.35,
        4,
    )


def _priority(score: float, velocity: float = 0.0) -> str:
    """Assign priority based on score and velocity thresholds."""
    if score >= 0.70 and abs(velocity) >= ELEVATED_VELOCITY:
        return "ELEVATED"
    elif score >= 0.50:
        return "STANDARD"
    else:
        return "MONITOR"


def score_signal(
    signal: Signal,
    run_id: str = "",
) -> Optional[Opportunity]:
    """Score a quant signal through 4 gates.

    Returns an Opportunity if:
    - All 4 gates pass (STANDARD or ELEVATED), OR
    - Gates 1+2 pass but gate 3 fails (MONITOR tier)

    Gate 4 (novelty) is always required.
    """
    # Gate 1 — Credibility: ticker must be in watchlist
    gate_credibility = signal.source in ALL_TICKERS

    # Gate 2 — Volume: relative volume > 0.8
    gate_volume = signal.engagement > VOLUME_THRESHOLD

    # Gate 3 — Velocity: |daily_return| > 0.2%
    gate_velocity = abs(signal.velocity) > VELOCITY_THRESHOLD

    # Gate 4 — Novelty: not already seen this run
    gate_novelty = _is_novel(signal, run_id)

    gate_results = {
        "credibility": gate_credibility,
        "volume":      gate_volume,
        "velocity":    gate_velocity,
        "novelty":     gate_novelty,
    }

    # Gate 4 (novelty) is mandatory
    if not gate_novelty:
        return None

    # Gates 1+2 must pass for any tier
    if not (gate_credibility and gate_volume):
        return None

    # If gates 1,2,4 pass but gate 3 fails: MONITOR tier
    # If all gates pass: STANDARD or ELEVATED tier
    score = _composite(signal)
    priority = _priority(score, signal.velocity)

    return Opportunity(
        opportunity_id=f"opp-q-{uuid.uuid4().hex[:10]}",
        signal_id=signal.signal_id,
        score=score,
        priority=priority,
        gate_results=gate_results,
        run_id=run_id,
    )


def score_batch(
    signals: list[Signal],
    run_id: str = "",
) -> dict:
    """Score a list of quant signals. Returns opportunities and blocked counts."""
    opportunities: list[Opportunity] = []
    blocked: list[dict] = []
    for sig in signals:
        opp = score_signal(sig, run_id=run_id)
        if opp:
            opportunities.append(opp)
        else:
            blocked.append({"signal_id": sig.signal_id, "source": sig.source})
    return {"opportunities": opportunities, "blocked": blocked}
