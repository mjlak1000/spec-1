"""
SPEC-1 — analysts/registry.py

Known analyst registry. Tracks credible voices in geopolitics and cyber.
These are the humans the system learns to weight over time.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from spec1_engine.core import ids
from spec1_engine.schemas.models import AnalystRecord


# ── Static registry (seed data) ───────────────────────────────────────────────

ANALYST_REGISTRY: Dict[str, Dict] = {
    # Journalists
    "julian_barnes": {
        "name":        "Julian E. Barnes",
        "affiliation": "New York Times",
        "type":        "journalist",
        "domains":     ["intelligence", "national_security", "russia"],
    },
    "ken_dilanian": {
        "name":        "Ken Dilanian",
        "affiliation": "NBC News",
        "type":        "journalist",
        "domains":     ["intelligence", "national_security", "cia"],
    },
    "natasha_bertrand": {
        "name":        "Natasha Bertrand",
        "affiliation": "CNN",
        "type":        "journalist",
        "domains":     ["defense", "intelligence", "ukraine"],
    },
    "shane_harris": {
        "name":        "Shane Harris",
        "affiliation": "Washington Post",
        "type":        "journalist",
        "domains":     ["intelligence", "cyber", "nsa"],
    },
    # Analysts
    "phillips_obrien": {
        "name":        "Phillips O'Brien",
        "affiliation": "University of St Andrews",
        "type":        "analyst",
        "domains":     ["geopolitics", "defense", "ukraine", "airpower"],
    },
    "michael_kofman": {
        "name":        "Michael Kofman",
        "affiliation": "Carnegie Endowment",
        "type":        "analyst",
        "domains":     ["russia", "military", "geopolitics"],
    },
    "dara_massicot": {
        "name":        "Dara Massicot",
        "affiliation": "Carnegie Endowment",
        "type":        "analyst",
        "domains":     ["russia", "military", "doctrine"],
    },
    "thomas_rid": {
        "name":        "Thomas Rid",
        "affiliation": "Johns Hopkins SAIS",
        "type":        "analyst",
        "domains":     ["cyber", "information_operations", "history"],
    },
    "melinda_haring": {
        "name":        "Melinda Haring",
        "affiliation": "Atlantic Council",
        "type":        "analyst",
        "domains":     ["ukraine", "geopolitics", "eastern_europe"],
    },
    # Think tank voices
    "rand_corp": {
        "name":        "RAND Corporation",
        "affiliation": "RAND",
        "type":        "institution",
        "domains":     ["geopolitics", "defense", "policy", "cyber"],
    },
    "csis_team": {
        "name":        "CSIS Research Team",
        "affiliation": "CSIS",
        "type":        "institution",
        "domains":     ["geopolitics", "cyber", "defense", "indo_pacific"],
    },
}


class AnalystRegistryManager:
    """
    Manages the analyst registry.
    Supports lookup, scoring updates, and new analyst addition.
    """

    def __init__(self) -> None:
        self._records: Dict[str, AnalystRecord] = {}
        self._seed_from_registry()

    def _seed_from_registry(self) -> None:
        for key, meta in ANALYST_REGISTRY.items():
            record = AnalystRecord(
                analyst_id=ids.analyst_id(meta["name"], meta["affiliation"]),
                name=meta["name"],
                affiliation=meta["affiliation"],
                source_type=meta["type"],
                domains=meta.get("domains", []),
            )
            self._records[key] = record

    def get(self, key: str) -> Optional[AnalystRecord]:
        return self._records.get(key)

    def all(self) -> List[AnalystRecord]:
        return list(self._records.values())

    def by_domain(self, domain: str) -> List[AnalystRecord]:
        return [
            r for r in self._records.values()
            if domain in r.domains
        ]

    def update_credibility(self, key: str, delta: float) -> None:
        """Adjust an analyst's credibility score after an outcome."""
        if key in self._records:
            r = self._records[key]
            r.credibility_score = round(
                min(1.0, max(0.0, r.credibility_score + delta)), 4
            )

    def record_citation(self, key: str, outcome_class: str) -> None:
        if key not in self._records:
            return
        r = self._records[key]
        r.times_cited += 1
        if outcome_class in ("Corroborated", "Escalate"):
            r.times_corroborated += 1
            self.update_credibility(key, +0.02)
        elif outcome_class == "Conflicted":
            r.times_conflicted += 1
            self.update_credibility(key, -0.02)

    def top_by_credibility(self, n: int = 5) -> List[AnalystRecord]:
        return sorted(
            self._records.values(),
            key=lambda r: r.credibility_score,
            reverse=True,
        )[:n]
