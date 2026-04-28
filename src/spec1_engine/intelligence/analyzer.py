"""
SPEC-1 — intelligence/analyzer.py

Extracts reusable intelligence patterns from Outcomes.
This is the learning arc — what the system remembers across cycles.
"""

from __future__ import annotations

from typing import Dict

from spec1_engine.core import ids
from spec1_engine.schemas.models import IntelligenceRecord, Outcome, Signal


# ANALYST_WEIGHT_MAP — last reviewed: 2026-04-28
# Weights reflect institutional credibility + national security beat depth.
# Review quarterly or when a listed analyst changes outlet or focus area.
ANALYST_WEIGHT_MAP: Dict[str, float] = {
    "Michael Kofman":    0.92,  # Carnegie Endowment; Ukraine/Russia force structure
    "Dara Massicot":     0.91,  # Carnegie Endowment; Russian military doctrine
    "Thomas Rid":        0.89,  # Johns Hopkins SAIS; influence ops / cyber history
    "Julian E. Barnes":  0.90,  # New York Times; intelligence / national security
    "Shane Harris":      0.88,  # Washington Post; national security / intelligence
    "Melinda Haring":    0.86,  # Atlantic Council; UkraineAlert editor
    "Natasha Bertrand":  0.87,  # CNN; defense / intelligence
    "Phillips O'Brien":  0.85,  # University of St Andrews; air power / Ukraine
    "Ken Dilanian":      0.85,  # NBC News; national security / intelligence
}

_ANALYST_WEIGHT_DEFAULT = 0.50  # fallback for analysts not in the map


class IntelligenceAnalyzer:
    """Converts an Outcome into an IntelligenceRecord."""

    def analyze(self, outcome: Outcome, signal: Signal) -> IntelligenceRecord:
        pattern        = self._extract_pattern(outcome, signal)
        source_weight  = self._compute_source_weight(outcome)
        analyst_weight = self._compute_analyst_weight(outcome)

        return IntelligenceRecord(
            record_id=ids.intelligence_id(signal.signal_id, outcome.classification),
            outcome_id=outcome.outcome_id,
            signal_id=signal.signal_id,
            signal_text=signal.text,
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
        """
        Weight for citing analysts, drawn from ANALYST_WEIGHT_MAP.
        Outcome classification adjusts the base weight up or down.
        Unknown analysts receive the default weight.
        """
        if not outcome.analyst_citations:
            return _ANALYST_WEIGHT_DEFAULT

        # Average the map weights for all cited analysts
        weights = [
            ANALYST_WEIGHT_MAP.get(name, _ANALYST_WEIGHT_DEFAULT)
            for name in outcome.analyst_citations
        ]
        base = sum(weights) / len(weights)

        # Outcome-driven adjustment on top of per-analyst base
        if outcome.classification in ("Corroborated", "Escalate"):
            return round(min(1.0, base + 0.05), 4)
        if outcome.classification == "Conflicted":
            return round(max(0.0, base - 0.05), 4)
        return round(base, 4)
