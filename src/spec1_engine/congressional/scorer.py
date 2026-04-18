"""Congressional trade scorer — 4-gate scoring.

Gates:
  1. Credibility — always passes; score varies by data source
  2. Amount      — trade value must exceed $15,000
  3. Recency     — trade must be within 30 days
  4. Novelty     — same politician+ticker not seen in last 5 run IDs

Priority:
  ELEVATED if amount > $250,000 AND trade within 7 days
  STANDARD if composite score >= 0.55
  MONITOR  otherwise
"""

from __future__ import annotations

import uuid
from collections import deque
from datetime import datetime, timezone
from typing import Optional

from spec1_engine.schemas.models import Opportunity, Signal

# ─── Gate thresholds ──────────────────────────────────────────────────────────

AMOUNT_THRESHOLD = 15_000     # Gate 2: minimum notional value
RECENCY_DAYS     = 30         # Gate 3: trade must be within N days
ELEVATED_AMOUNT  = 250_000    # Priority: threshold for ELEVATED
ELEVATED_DAYS    = 7          # Priority: age cap for ELEVATED

# ─── Source credibility ───────────────────────────────────────────────────────

SOURCE_CREDIBILITY: dict[str, float] = {
    "quiver":         0.80,
    "capitol_trades": 0.75,
    "sample":         0.60,
}
DEFAULT_CREDIBILITY = 0.60

# ─── Novelty: rolling window of last 5 run IDs per politician+ticker ──────────

_WINDOW = 5
_novelty_cache: dict[str, deque] = {}


def clear_novelty_cache() -> None:
    """Clear the cross-run novelty cache. Call at the start of each cycle."""
    _novelty_cache.clear()


def _is_novel(politician: str, ticker: str, run_id: str) -> bool:
    """Return True if this politician+ticker combo has not fired in the last 5 runs."""
    key = f"{politician.lower().strip()}::{ticker.upper().strip()}"
    if key not in _novelty_cache:
        _novelty_cache[key] = deque(maxlen=_WINDOW)
    seen = _novelty_cache[key]
    if run_id in seen:
        return False
    seen.append(run_id)
    return True


# ─── Scoring helpers ──────────────────────────────────────────────────────────

def _credibility(source: str) -> float:
    return SOURCE_CREDIBILITY.get(source, DEFAULT_CREDIBILITY)


def _age_days(signal: Signal) -> float:
    dt = signal.published_at
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - dt).total_seconds() / 86_400


def _composite(signal: Signal) -> float:
    cred = _credibility(signal.source)
    amount_norm = min(signal.engagement, 1.0)   # log10(amount)/7 from parser
    vel = signal.velocity                        # 1.0 or 0.5 from parser
    return round(cred * 0.30 + amount_norm * 0.40 + vel * 0.30, 4)


def _priority(signal: Signal) -> str:
    amount = signal.metadata.get("amount", 0)
    age = _age_days(signal)
    if amount > ELEVATED_AMOUNT and age <= ELEVATED_DAYS:
        return "ELEVATED"
    return "STANDARD" if _composite(signal) >= 0.55 else "MONITOR"


# ─── Public scoring functions ─────────────────────────────────────────────────

def score_signal(signal: Signal, run_id: str = "") -> Optional[Opportunity]:
    """Score a single congressional trade through 4 gates.

    Args:
        signal: Parsed congressional trade Signal (source_type="congressional_trade").
        run_id: Current cycle run ID used for novelty tracking.

    Returns:
        Opportunity if all four gates pass, else None.
    """
    politician = signal.metadata.get("politician", "")
    ticker     = signal.metadata.get("ticker", signal.source)
    amount     = signal.metadata.get("amount", 0)
    age        = _age_days(signal)

    gate_credibility = True                          # Gate 1: always pass
    gate_amount      = amount > AMOUNT_THRESHOLD     # Gate 2: > $15,000
    gate_recency     = age <= RECENCY_DAYS           # Gate 3: within 30 days
    gate_novelty     = _is_novel(politician, ticker, run_id)  # Gate 4

    gate_results = {
        "credibility": gate_credibility,
        "amount":      gate_amount,
        "recency":     gate_recency,
        "novelty":     gate_novelty,
    }

    if not all(gate_results.values()):
        return None

    return Opportunity(
        opportunity_id=f"opp-c-{uuid.uuid4().hex[:10]}",
        signal_id=signal.signal_id,
        score=_composite(signal),
        priority=_priority(signal),
        gate_results=gate_results,
        run_id=run_id,
    )


def score_batch(signals: list[Signal], run_id: str = "") -> dict:
    """Score a batch of congressional trade signals.

    Args:
        signals: List of parsed Signals.
        run_id: Current cycle run ID.

    Returns:
        Dict with 'opportunities' (list[Opportunity]) and 'blocked' (list[dict]).
    """
    opportunities = []
    blocked = []
    for sig in signals:
        opp = score_signal(sig, run_id=run_id)
        if opp:
            opportunities.append(opp)
        else:
            blocked.append({"signal_id": sig.signal_id, "source": sig.source})
    return {"opportunities": opportunities, "blocked": blocked}
