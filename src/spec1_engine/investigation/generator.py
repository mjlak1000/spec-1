"""
SPEC-1 — investigation/generator.py

Turns an Opportunity into a structured Investigation plan.
Generates hypothesis, follow-up queries, sources to check, and analyst leads.
"""

from __future__ import annotations

from spec1_engine.core import ids
from spec1_engine.schemas.models import Investigation, Opportunity, Signal
from spec1_engine.analysts.registry import ANALYST_REGISTRY


class InvestigationGenerator:
    """Generates a structured investigation plan from an Opportunity."""

    def generate(self, opportunity: Opportunity, signal: Signal) -> Investigation:
        hypothesis = self._build_hypothesis(signal)
        queries    = self._build_queries(signal)
        sources    = self._select_sources(signal)
        analysts   = self._find_analyst_leads(signal)

        return Investigation(
            investigation_id=ids.investigation_id(opportunity.opportunity_id),
            opportunity_id=opportunity.opportunity_id,
            signal_id=signal.signal_id,
            hypothesis=hypothesis,
            queries=queries,
            sources_to_check=sources,
            analyst_leads=analysts,
            run_id=signal.run_id,
            environment=signal.environment,
            metadata={
                "signal_source": signal.source,
                "priority":      opportunity.priority,
            },
        )

    def _build_hypothesis(self, signal: Signal) -> str:
        """Build an initial investigation hypothesis from the signal text."""
        # v0.1: simple template. v1.0: Claude API call.
        return (
            f"Signal from {signal.source} may indicate a developing situation "
            f"requiring corroboration. Initial claim: {signal.text[:200]}..."
        )

    def _build_queries(self, signal: Signal) -> list:
        """Generate follow-up queries for verification."""
        base = signal.text[:80].strip()
        return [
            base,
            f"{base} — corroboration",
            f"{base} — contradiction",
            f"{base} — primary source",
        ]

    def _select_sources(self, signal: Signal) -> list:
        """Select which sources to check for corroboration."""
        domains = signal.metadata.get("domains", [])
        candidates = []
        for source, meta in ANALYST_REGISTRY.items():
            if any(d in meta.get("domains", []) for d in domains):
                candidates.append(source)
        # Always include the originating source's peer publications
        return candidates[:5] if candidates else ["rand", "csis", "atlantic_council"]

    def _find_analyst_leads(self, signal: Signal) -> list:
        """Identify analysts who cover this signal's domain."""
        domains = signal.metadata.get("domains", [])
        leads = []
        for analyst_id, meta in ANALYST_REGISTRY.items():
            if any(d in meta.get("domains", []) for d in domains):
                leads.append(analyst_id)
        return leads[:3]
