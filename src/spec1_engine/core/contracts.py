"""Canonical scoring contracts for SPEC-1 Intelligence Engine.

This file is part of the frozen core package. It defines authoritative
constants, thresholds, and interface contracts for the 4-gate signal
scoring pipeline.

IMMUTABILITY RULE: No agent or module may write to ``core/``.
All imports flow *from* ``core/`` outward.

4-Gate Pipeline
---------------
Every signal must pass **all four gates** to become an
:class:`~spec1_engine.core.schemas.Opportunity`:

+-------------+-----------------------------------------------+-------------------+
| Gate        | Criterion                                     | Default Threshold |
+=============+===============================================+===================+
| credibility | Source credibility score ≥ threshold          | 0.60              |
+-------------+-----------------------------------------------+-------------------+
| volume      | Word-count-derived score ≥ threshold          | 0.30 (≥ 30 words) |
+-------------+-----------------------------------------------+-------------------+
| velocity    | Signal freshness score ≥ threshold            | 0.0 (always pass) |
+-------------+-----------------------------------------------+-------------------+
| novelty     | High-value keyword hits ≥ threshold           | 1 term hit        |
+-------------+-----------------------------------------------+-------------------+
"""

from __future__ import annotations

# ── Credibility gate ─────────────────────────────────────────────────────────
#: Credibility weights for primary SPEC-1 intelligence sources in ``[0.0, 1.0]``.
PRIMARY_SOURCE_CREDIBILITY: dict[str, float] = {
    "war_on_the_rocks": 0.85,
    "cipher_brief": 0.88,
    "lawfare": 0.87,
    "rand": 0.90,
    "atlantic_council": 0.82,
    "defense_one": 0.83,
}

#: Credibility weights for legacy cls_osint sources in ``[0.0, 1.0]``.
LEGACY_SOURCE_CREDIBILITY: dict[str, float] = {
    "reuters_world": 0.90,
    "reuters_us": 0.90,
    "ap_top": 0.88,
    "propublica": 0.85,
    "politico": 0.78,
}

#: Combined per-source credibility weights (primary + legacy) in ``[0.0, 1.0]``.
#: This is the authoritative lookup used by the credibility gate scorer.
SOURCE_CREDIBILITY: dict[str, float] = {
    **PRIMARY_SOURCE_CREDIBILITY,
    **LEGACY_SOURCE_CREDIBILITY,
}

#: Fallback credibility for unknown sources.
DEFAULT_CREDIBILITY: float = 0.60

#: Minimum credibility score required to pass the credibility gate.
CREDIBILITY_THRESHOLD: float = 0.60

# ── Volume gate ───────────────────────────────────────────────────────────────
#: Tiered volume scores ``(min_words, score)``, evaluated top-to-bottom.
VOLUME_TIERS: list[tuple[int, float]] = [
    (500, 1.0),
    (200, 0.75),
    (80,  0.50),
    (30,  0.30),
    (0,   0.10),
]

#: Minimum volume score required to pass the volume gate (≈ 30 words).
VOLUME_THRESHOLD: float = 0.30

# ── Velocity gate ─────────────────────────────────────────────────────────────
#: Minimum velocity/freshness score required to pass the velocity gate.
#: Set to ``0.0`` so the gate passes unless the score is explicitly negative.
VELOCITY_THRESHOLD: float = 0.0

# ── Novelty gate ─────────────────────────────────────────────────────────────
#: High-value intelligence/journalism keywords used for novelty scoring.
NOVELTY_TERMS: frozenset[str] = frozenset({
    "investigation", "exclusive", "lawsuit", "indicted", "whistleblower",
    "leak", "classified", "subpoena", "fraud", "corruption", "arrested",
    "charged", "criminal", "federal", "oversight", "hearing", "testimony",
    "intelligence", "military", "strategy", "conflict", "nuclear", "cyber",
    "espionage", "covert", "sanctions", "treaty", "deployment", "warfare",
    "threat", "security", "defense", "attack", "operation", "weapon",
    "missile", "drone", "navy", "army", "coalition", "alliance", "nato",
    "ukraine", "russia", "china", "iran", "north korea", "taiwan",
    "pentagon", "cia", "nsa", "fbi", "dod", "state department",
})

#: Minimum number of novelty term hits required to pass the novelty gate.
NOVELTY_THRESHOLD: int = 1

# ── Composite score weights ───────────────────────────────────────────────────
#: Weight applied to the credibility component in the composite score.
CREDIBILITY_WEIGHT: float = 0.30

#: Weight applied to the volume component in the composite score.
VOLUME_WEIGHT: float = 0.20

#: Weight applied to the velocity component in the composite score.
VELOCITY_WEIGHT: float = 0.20

#: Weight applied to the novelty component in the composite score.
NOVELTY_WEIGHT: float = 0.30

# ── Priority assignment ───────────────────────────────────────────────────────
#: Composite score threshold above which an opportunity is labelled ELEVATED.
PRIORITY_ELEVATED_THRESHOLD: float = 0.75

#: Composite score threshold above which an opportunity is labelled STANDARD.
#: Scores below this threshold receive the MONITOR label.
PRIORITY_STANDARD_THRESHOLD: float = 0.55

#: Valid priority labels produced by the scorer.
PRIORITY_LABELS: tuple[str, ...] = ("ELEVATED", "STANDARD", "MONITOR")

# ── Outcome classifications ───────────────────────────────────────────────────
#: All valid outcome classification strings returned by the verifier.
VALID_CLASSIFICATIONS: frozenset[str] = frozenset({
    "CORROBORATED",
    "ESCALATE",
    "INVESTIGATE",
    "MONITOR",
    "CONFLICTED",
    "ARCHIVE",
})

# ── Gate interface contract ───────────────────────────────────────────────────
#: Ordered list of gate names — order is significant for documentation only.
GATE_NAMES: tuple[str, ...] = ("credibility", "volume", "velocity", "novelty")

#: Human-readable description of each gate.
GATE_DESCRIPTIONS: dict[str, str] = {
    "credibility": (
        "Source credibility gate — validates that the originating source has a "
        "known credibility score at or above CREDIBILITY_THRESHOLD."
    ),
    "volume": (
        "Volume gate — ensures the parsed text has sufficient word-count depth "
        "to support analysis (score derived via VOLUME_TIERS)."
    ),
    "velocity": (
        "Velocity gate — ensures the signal is fresh enough to be actionable "
        "(derived from signal.velocity or publication age)."
    ),
    "novelty": (
        "Novelty gate — confirms the text contains at least one high-value "
        "intelligence keyword from NOVELTY_TERMS."
    ),
}
