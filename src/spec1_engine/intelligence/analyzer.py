"""
SPEC-1 — intelligence/analyzer.py

Extracts reusable intelligence patterns from Outcomes.
This is the learning arc — what the system remembers across cycles.
"""

from __future__ import annotations

from spec1_engine.core import ids
from spec1_engine.schemas.models import IntelligenceRecord, Outcome, Signal


class IntelligenceAnalyzer:
    """Converts an Outcome into an IntelligenceRecord."""

    def analyze(self, outcome: Outcome, signal: Signal) -> IntelligenceRecord:
        pattern        = self._extract_pattern(outcome, signal)
        source_weight  = self._compute_source_weight(outcome)
        analyst_weight = self._compute_analyst_weight(outcome)

        return IntelligenceRecord(
            record_id=ids.intelligence_id(outcome.outcome_id),
            outcome_id=outcome.outcome_id,
            signal_id=signal.signal_id,
            pattern=pattern,
            classification=outcome.classification,
            confidence=outcome.confidence,
            source_weight=source_weight,
            analyst_weight=analyst_weight,
            run_id=signal.run_id,
            environment=signal.environment,
            metadata={
                "source":         signal.source,
                "source_type":    signal.source_type,
                "domains":        signal.metadata.get("domains", []),
                "corroborating":  outcome.corroborating_sources,
                "conflicting":    outcome.conflicting_sources,
            },
        )

    def _extract_pattern(self, outcome: Outcome, signal: Signal) -> str:
        """
        Extract the reusable pattern from this outcome.
        v0.1: template. v1.0: Claude API call.
        """
        return (
            f"{signal.source_type.upper()} signal from {signal.source} "
            f"classified as {outcome.classification} "
            f"with confidence {outcome.confidence:.2f}. "
            f"Domains: {', '.join(signal.metadata.get('domains', []))}."
        )

    def _compute_source_weight(self, outcome: Outcome) -> float:
        """
        How much should we weight this source in future cycles?
        Corroborated/Escalate → increase. Conflicted → decrease.
        """
        base = 0.5
        adjustments = {
            "Corroborated": +0.20,
            "Escalate":     +0.25,
            "Investigate":  +0.05,
            "Monitor":       0.00,
            "Conflicted":   -0.20,
            "Archive":      -0.10,
        }
        delta = adjustments.get(outcome.classification, 0.0)
        return round(min(1.0, max(0.0, base + delta + outcome.confidence * 0.1)), 4)

    def _compute_analyst_weight(self, outcome: Outcome) -> float:
        """How much should we weight the citing analysts?"""
        if not outcome.analyst_citations:
            return 0.5
        base = 0.5
        if outcome.classification in ("Corroborated", "Escalate"):
            return round(min(1.0, base + 0.15), 4)
        if outcome.classification == "Conflicted":
            return round(max(0.0, base - 0.15), 4)
        return base
