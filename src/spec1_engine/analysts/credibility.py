"""
SPEC-1 — analysts/credibility.py

Credibility scoring for analysts and sources.
Updates are driven by Outcome classifications from the learning loop.
"""

from __future__ import annotations

from spec1_engine.analysts.registry import AnalystRegistryManager


class CredibilityEngine:
    """
    Updates analyst credibility based on outcome feedback.
    The system learns which voices to weight over time.
    """

    def __init__(self, registry: AnalystRegistryManager) -> None:
        self._registry = registry

    def update_from_outcome(
        self,
        analyst_keys: list,
        outcome_classification: str,
    ) -> None:
        """
        Update credibility for all analysts cited in an outcome.
        Called by the learning loop after each cycle.
        """
        for key in analyst_keys:
            self._registry.record_citation(key, outcome_classification)

    def credibility_report(self) -> dict:
        """Return a summary of current analyst credibility scores."""
        return {
            r.name: round(r.credibility_score, 4)
            for r in self._registry.top_by_credibility(n=20)
        }
