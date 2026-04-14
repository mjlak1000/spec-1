"""
SPEC-1 — investigation/verifier.py

Runs verification on an Investigation and produces an Outcome.
v0.1: mocked verification with realistic confidence scoring.
v1.0: real source checking, Claude API analysis, evidence bundling.

Outcome classifications:
  Corroborated  — multiple credible sources confirm
  Investigate   — promising but needs more work
  Monitor       — low confidence, watch for developments
  Conflicted    — contradictory signals
  Escalate      — high confidence, high importance, needs immediate attention
  Archive       — not actionable, store for reference
"""

from __future__ import annotations

from spec1_engine.core import ids
from spec1_engine.schemas.models import Investigation, Outcome, Signal


class Verifier:
    """
    Verifies an Investigation and classifies the outcome.
    v0.1: deterministic mock based on signal velocity and engagement.
    """

    def verify(self, investigation: Investigation, signal: Signal) -> Outcome:
        confidence, evidence, corroborating, conflicting = self._mock_verify(signal)
        classification = self._classify(confidence, signal)

        return Outcome(
            outcome_id=ids.outcome_id(investigation.investigation_id),
            investigation_id=investigation.investigation_id,
            opportunity_id=investigation.opportunity_id,
            signal_id=signal.signal_id,
            classification=classification,
            confidence=confidence,
            evidence=evidence,
            corroborating_sources=corroborating,
            conflicting_sources=conflicting,
            analyst_citations=investigation.analyst_leads,
            notes=f"v0.1 mocked verification. Hypothesis: {investigation.hypothesis[:120]}",
            run_id=signal.run_id,
            environment=signal.environment,
            metrics={
                "velocity":   signal.velocity,
                "engagement": signal.engagement,
            },
        )

    def _mock_verify(self, signal: Signal):
        """
        Mocked verification logic.
        In production: query corroborating sources, run Claude analysis,
        build evidence bundle.
        """
        # Confidence derived from signal strength as a proxy for verifiability
        confidence = round((signal.velocity * 0.5 + signal.engagement * 0.5), 4)
        confidence = min(1.0, max(0.0, confidence))

        evidence = [
            f"Source: {signal.source} — {signal.text[:100]}",
            f"Author: {signal.author or 'unknown'}",
        ]

        # Mock corroboration based on source type
        if signal.source_type in ("publication", "think_tank"):
            corroborating = ["rand", "csis"]
            conflicting   = []
        elif signal.source_type == "journalist":
            corroborating = ["war_on_the_rocks"]
            conflicting   = []
        else:
            corroborating = []
            conflicting   = ["unverified_platform"]

        return confidence, evidence, corroborating, conflicting

    def _classify(self, confidence: float, signal: Signal) -> str:
        """Map confidence + signal context to an OSINT-native classification."""
        if confidence >= 0.85 and signal.velocity >= 0.85:
            return "Escalate"
        if confidence >= 0.75:
            return "Corroborated"
        if confidence >= 0.55:
            return "Investigate"
        if confidence >= 0.35:
            return "Monitor"
        if len(signal.metadata.get("domains", [])) == 0:
            return "Archive"
        return "Monitor"
