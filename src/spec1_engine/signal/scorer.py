"""Signal Scorer — implements 4-gate scoring logic.

Ported from cls_osint/scorers/signal_scorer.py with new 4-gate architecture.

Gates:
  1. Credibility gate — source must have credibility >= threshold
  2. Volume gate     — parsed text must have enough words
  3. Velocity gate   — signal velocity score (freshness/recency proxy)
  4. Novelty gate    — text must contain high-value intelligence keywords

Only signals passing all 4 gates become Opportunity instances.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from spec1_engine.schemas.models import Opportunity, ParsedSignal, Signal

# ─── Credibility gate ────────────────────────────────────────────────────────
SOURCE_CREDIBILITY: dict[str, float] = {
    "war_on_the_rocks": 0.85,
    "cipher_brief": 0.88,
    "lawfare": 0.87,
    "rand": 0.90,
    "atlantic_council": 0.82,
    "defense_one": 0.83,
    # legacy sources (from cls_osint)
    "reuters_world": 0.90,
    "reuters_us": 0.90,
    "ap_top": 0.88,
    "propublica": 0.85,
    "politico": 0.78,
}
DEFAULT_CREDIBILITY = 0.60
CREDIBILITY_THRESHOLD = 0.60  # gate passes if credibility >= this

# ─── Volume gate ─────────────────────────────────────────────────────────────
VOLUME_TIERS: list[tuple[int, float]] = [
    (500, 1.0),
    (200, 0.75),
    (80,  0.50),
    (30,  0.30),
    (0,   0.10),
]
VOLUME_THRESHOLD = 0.30  # gate passes if volume score >= this (≥30 words)

# ─── Velocity gate ───────────────────────────────────────────────────────────
# We use signal.velocity if set; otherwise derive from age in hours
VELOCITY_THRESHOLD = 0.0  # gate passes if velocity >= 0 (always pass unless explicitly negative)

# ─── Novelty gate ────────────────────────────────────────────────────────────
NOVELTY_TERMS: set[str] = {
    "investigation", "exclusive", "lawsuit", "indicted", "whistleblower",
    "leak", "classified", "subpoena", "fraud", "corruption", "arrested",
    "charged", "criminal", "federal", "oversight", "hearing", "testimony",
    "intelligence", "military", "strategy", "conflict", "nuclear", "cyber",
    "espionage", "covert", "sanctions", "treaty", "deployment", "warfare",
    "threat", "security", "defense", "attack", "operation", "weapon",
    "missile", "drone", "navy", "army", "coalition", "alliance", "nato",
    "ukraine", "russia", "china", "iran", "north korea", "taiwan",
    "pentagon", "cia", "nsa", "fbi", "dod", "state department",
}
NOVELTY_THRESHOLD = 1  # must have at least 1 novelty term hit


# ─── Composite scoring ───────────────────────────────────────────────────────
def _score_credibility(source: str) -> float:
    return SOURCE_CREDIBILITY.get(source, DEFAULT_CREDIBILITY)


def _score_volume(word_count: int) -> float:
    for threshold, score in VOLUME_TIERS:
        if word_count >= threshold:
            return score
    return 0.10


def _score_velocity(signal: Signal) -> float:
    """Score velocity based on signal.velocity field or age."""
    if signal.velocity > 0:
        return signal.velocity
    # Derive from age: fresh signals (< 24h) score higher
    try:
        if isinstance(signal.published_at, datetime):
            pub = signal.published_at
        else:
            from dateutil import parser as dp
            pub = dp.parse(str(signal.published_at))
        if pub.tzinfo is None:
            pub = pub.replace(tzinfo=timezone.utc)
        age_hours = (datetime.now(timezone.utc) - pub).total_seconds() / 3600
        if age_hours < 6:
            return 1.0
        elif age_hours < 24:
            return 0.75
        elif age_hours < 72:
            return 0.50
        elif age_hours < 168:
            return 0.25
        else:
            return 0.10
    except Exception:
        return 0.50


def _score_novelty(text: str, keywords: list[str]) -> tuple[float, int]:
    """Return (score, hit_count) for novelty terms."""
    lower_text = text.lower()
    kw_set = {k.lower() for k in keywords}
    hits = sum(1 for term in NOVELTY_TERMS if term in lower_text or term in kw_set)
    if hits == 0:
        return 0.0, 0
    elif hits == 1:
        return 0.40, 1
    elif hits < 4:
        return 0.65, hits
    else:
        return min(0.85 + (hits - 4) * 0.03, 1.0), hits


def _priority(score: float) -> str:
    if score >= 0.75:
        return "ELEVATED"
    elif score >= 0.55:
        return "STANDARD"
    else:
        return "MONITOR"


def score_signal(
    signal: Signal,
    parsed: ParsedSignal,
    run_id: str = "",
) -> Optional[Opportunity]:
    """Score a signal through 4 gates. Returns Opportunity if all pass, else None."""
    credibility = _score_credibility(signal.source)
    volume = _score_volume(parsed.word_count)
    velocity = _score_velocity(signal)
    novelty_score, novelty_hits = _score_novelty(parsed.cleaned_text, parsed.keywords)

    gate_credibility = credibility >= CREDIBILITY_THRESHOLD
    gate_volume = volume >= VOLUME_THRESHOLD
    gate_velocity = velocity >= VELOCITY_THRESHOLD
    gate_novelty = novelty_hits >= NOVELTY_THRESHOLD

    gate_results = {
        "credibility": gate_credibility,
        "volume": gate_volume,
        "velocity": gate_velocity,
        "novelty": gate_novelty,
    }

    if not all(gate_results.values()):
        return None

    # Composite score
    composite = round(
        credibility * 0.30
        + volume * 0.20
        + velocity * 0.20
        + novelty_score * 0.30,
        4,
    )

    return Opportunity(
        opportunity_id=f"opp-{uuid.uuid4().hex[:12]}",
        signal_id=signal.signal_id,
        score=composite,
        priority=_priority(composite),
        gate_results=gate_results,
        run_id=run_id,
    )


def score_batch(
    signals: list[Signal],
    parsed_signals: list[ParsedSignal],
    run_id: str = "",
) -> dict:
    """Score a batch of signals. Returns opportunities and blocked signals."""
    opportunities: list[Opportunity] = []
    blocked: list[dict] = []
    for sig, ps in zip(signals, parsed_signals):
        opp = score_signal(sig, ps, run_id=run_id)
        if opp:
            opportunities.append(opp)
        else:
            blocked.append({"signal_id": sig.signal_id, "source": sig.source})
    return {"opportunities": opportunities, "blocked": blocked}
