"""
SPEC-1 — signal/scorer.py

Scores raw signals through four gates and produces Opportunities.

Gates (run in order — first failure stops evaluation):
  Gate 1: Source credibility — known disinfo or unverified source → reject
  Gate 2: Signal volume floor — insufficient corroboration signal → reject
  Gate 3: Velocity — declining or stale signal → reject
  Gate 4: Novelty — already surfaced in recent intelligence → deprioritize

Priority bands:
  ELEVATED:  score >= 0.75
  STANDARD:  score >= 0.45
  MONITOR:   score < 0.45  (passes gates but low signal strength)
"""

from __future__ import annotations

from typing import Optional

from spec1_engine.core import ids, logging_utils
from spec1_engine.schemas.models import Opportunity, Signal

logger = logging_utils.get_logger(__name__)

# ── Gate thresholds ───────────────────────────────────────────────────────────

# Gate 1: unknown sources receive credibility 0.0 and are rejected below the threshold
CREDIBILITY_REJECT_THRESHOLD = 0.50
VOLUME_FLOOR       = 0.30  # Gate 2: engagement proxy minimum
VELOCITY_FLOOR     = 0.40  # Gate 3: velocity minimum (below = trailing/stale)
NOVELTY_PENALTY    = 0.15  # Gate 4: deduct from score if seen recently

# ── Scoring weights (must sum to 1.0) ────────────────────────────────────────
SCORE_WEIGHT_VELOCITY    = 0.40
SCORE_WEIGHT_ENGAGEMENT  = 0.30
SCORE_WEIGHT_CREDIBILITY = 0.30

# ── Source credibility map ────────────────────────────────────────────────────
# 1.0 = fully trusted | 0.5 = use with caution | 0.0 = reject

SOURCE_CREDIBILITY = {
    "war_on_the_rocks":   1.0,
    "cipher_brief":       1.0,
    "lawfare":            1.0,
    "small_wars_journal": 1.0,
    "defense_one":        0.9,
    "breaking_defense":   0.9,
    "the_drive":          0.9,
    "rand":               1.0,
    "csis":               1.0,
    "atlantic_council":   0.95,
    "cfr":                0.95,
    "julian_barnes_nyt":  1.0,
    "ken_dilanian_nbc":   0.95,
    "natasha_bertrand":   0.95,
    "shane_harris_wapo":  1.0,
    "substack_osint":     0.70,
    "x_twitter":          0.60,
    "rss_feed":           0.65,
}


class SignalScorer:
    """
    Scores a Signal through four gates.
    Returns an Opportunity if the signal passes, None if rejected.
    """

    def score(self, signal: Signal) -> Optional[Opportunity]:
        gate_results = {}

        # ── Gate 1: Source credibility ────────────────────────────────────────
        cred = SOURCE_CREDIBILITY.get(signal.source, 0.0)
        gate_results["credibility"] = cred >= CREDIBILITY_REJECT_THRESHOLD
        if not gate_results["credibility"]:
            logging_utils.log_event(
                logger, "gate_failed",
                signal_id=signal.signal_id,
                gate="credibility",
                value=cred,
                threshold=CREDIBILITY_REJECT_THRESHOLD,
            )
            return None

        # ── Gate 2: Volume floor ──────────────────────────────────────────────
        gate_results["volume"] = signal.engagement >= VOLUME_FLOOR
        if not gate_results["volume"]:
            logging_utils.log_event(
                logger, "gate_failed",
                signal_id=signal.signal_id,
                gate="volume",
                value=signal.engagement,
                threshold=VOLUME_FLOOR,
            )
            return None

        # ── Gate 3: Velocity floor ────────────────────────────────────────────
        gate_results["velocity"] = signal.velocity >= VELOCITY_FLOOR
        if not gate_results["velocity"]:
            logging_utils.log_event(
                logger, "gate_failed",
                signal_id=signal.signal_id,
                gate="velocity",
                value=signal.velocity,
                threshold=VELOCITY_FLOOR,
            )
            return None

        # ── Gate 4: Novelty (soft gate — penalizes but doesn't reject) ────────
        # v0.1: no history store yet, so novelty is always full
        novelty_ok = True
        gate_results["novelty"] = novelty_ok
        novelty_penalty = 0.0 if novelty_ok else NOVELTY_PENALTY

        # ── Score calculation ─────────────────────────────────────────────────
        raw_score = (
            SCORE_WEIGHT_VELOCITY    * signal.velocity
            + SCORE_WEIGHT_ENGAGEMENT  * signal.engagement
            + SCORE_WEIGHT_CREDIBILITY * cred
            - novelty_penalty
        )
        score = round(min(1.0, max(0.0, raw_score)), 4)

        # ── Priority band ─────────────────────────────────────────────────────
        if score >= 0.75:
            priority = "ELEVATED"
        elif score >= 0.45:
            priority = "STANDARD"
        else:
            priority = "MONITOR"

        rationale = (
            f"Source credibility: {cred:.2f} | "
            f"Velocity: {signal.velocity:.2f} | "
            f"Engagement: {signal.engagement:.2f} | "
            f"Novelty penalty: {novelty_penalty:.2f} | "
            f"Final score: {score:.4f}"
        )

        return Opportunity(
            opportunity_id=ids.opportunity_id(signal.signal_id),
            signal_id=signal.signal_id,
            score=score,
            priority=priority,
            rationale=rationale,
            gate_results=gate_results,
            run_id=signal.run_id,
            environment=signal.environment,
        )
