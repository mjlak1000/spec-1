"""Analyst Registry.

Contains the authoritative list of known national security analysts and think tanks.
"""

from __future__ import annotations

import uuid
from typing import Optional

from spec1_engine.schemas.models import AnalystRecord

# ─── Registry ────────────────────────────────────────────────────────────────
_ANALYST_DATA: list[dict] = [
    {
        "name": "Julian E. Barnes",
        "affiliation": "The New York Times",
        "domains": ["national security", "intelligence", "cia", "nsa"],
        "credibility_score": 0.90,
    },
    {
        "name": "Ken Dilanian",
        "affiliation": "NBC News",
        "domains": ["intelligence", "fbi", "counterterrorism", "national security"],
        "credibility_score": 0.85,
    },
    {
        "name": "Natasha Bertrand",
        "affiliation": "CNN",
        "domains": ["national security", "pentagon", "defense", "military"],
        "credibility_score": 0.87,
    },
    {
        "name": "Shane Harris",
        "affiliation": "The Washington Post",
        "domains": ["intelligence", "security", "nsa", "cyber", "surveillance"],
        "credibility_score": 0.88,
    },
    {
        "name": "Phillips O'Brien",
        "affiliation": "University of St Andrews",
        "domains": ["military strategy", "naval", "air power", "world war", "academic"],
        "credibility_score": 0.85,
    },
    {
        "name": "Michael Kofman",
        "affiliation": "CNA",
        "domains": ["russia", "ukraine", "military", "armed forces", "eastern europe"],
        "credibility_score": 0.92,
    },
    {
        "name": "Dara Massicot",
        "affiliation": "RAND Corporation",
        "domains": ["russia", "military", "russian armed forces", "defense"],
        "credibility_score": 0.91,
    },
    {
        "name": "Thomas Rid",
        "affiliation": "Johns Hopkins University",
        "domains": ["information warfare", "cyber", "disinformation", "technology"],
        "credibility_score": 0.89,
    },
    {
        "name": "Melinda Haring",
        "affiliation": "Atlantic Council",
        "domains": ["ukraine", "eastern europe", "democracy", "kyiv"],
        "credibility_score": 0.86,
    },
    {
        "name": "RAND Corp",
        "affiliation": "RAND Corporation",
        "domains": ["defense policy", "national security", "military", "research"],
        "credibility_score": 0.92,
    },
    {
        "name": "CSIS",
        "affiliation": "Center for Strategic and International Studies",
        "domains": ["international security", "defense", "foreign policy", "geopolitics"],
        "credibility_score": 0.91,
    },
]


def _build_analyst_id(name: str) -> str:
    """Build a stable analyst ID from name."""
    import hashlib
    return "analyst-" + hashlib.sha256(name.encode()).hexdigest()[:8]


def load_all() -> list[AnalystRecord]:
    """Return all analysts as AnalystRecord instances."""
    return [
        AnalystRecord(
            analyst_id=_build_analyst_id(d["name"]),
            name=d["name"],
            affiliation=d["affiliation"],
            domains=d["domains"],
            credibility_score=d["credibility_score"],
        )
        for d in _ANALYST_DATA
    ]


def find_by_name(name: str) -> Optional[AnalystRecord]:
    """Find an analyst by exact name (case-insensitive)."""
    name_lower = name.lower()
    for record in load_all():
        if record.name.lower() == name_lower:
            return record
    return None


def find_by_domain(domain: str) -> list[AnalystRecord]:
    """Find analysts matching a domain keyword."""
    domain_lower = domain.lower()
    return [
        r for r in load_all()
        if any(domain_lower in d for d in r.domains)
    ]


def get_all_names() -> list[str]:
    """Return all analyst names."""
    return [d["name"] for d in _ANALYST_DATA]


def get_credibility(name: str) -> float:
    """Get credibility score for an analyst by name."""
    record = find_by_name(name)
    return record.credibility_score if record else 0.50
