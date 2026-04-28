"""
SPEC-1 — schemas/models.py

Typed dataclasses for every major object in the learning loop.
All objects carry run_id, environment, and metadata for full traceability.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


# ── Outcome classifications (OSINT-native) ────────────────────────────────────

OUTCOME_CLASSES = (
    "Investigate",
    "Monitor",
    "Archive",
    "Corroborated",
    "Conflicted",
    "Escalate",
)


# ── Core loop objects ─────────────────────────────────────────────────────────

@dataclass
class Signal:
    """
    A raw observation from the environment.
    May come from a publication, analyst post, RSS feed, or manual submission.
    """
    signal_id:   str
    source:      str                        # e.g. "war_on_the_rocks", "cipher_brief"
    source_type: str                        # publication | think_tank | journalist | platform
    text:        str
    url:         Optional[str]              = None
    author:      Optional[str]              = None
    published_at: Optional[str]             = None
    velocity:    float                      = 0.0   # how fast this topic is spreading
    engagement:  float                      = 0.0   # proxy for reach
    run_id:      str                        = ""
    environment: str                        = "osint"
    metadata:    Dict[str, Any]             = field(default_factory=dict)
    created_at:  str                        = field(
        default_factory=lambda: datetime.utcnow().isoformat()
    )


_PRIORITY_VALUES = ("ELEVATED", "STANDARD", "MONITOR")


@dataclass
class Opportunity:
    """
    A scored signal worth investigating.
    Produced by signal/scorer.py after gate validation.
    """
    opportunity_id:  str
    signal_id:       str
    score:           float                  # 0.0 – 1.0
    priority:        str                    # ELEVATED | STANDARD | MONITOR
    rationale:       str                    # why this scored the way it did
    gate_results:    Dict[str, bool]        = field(default_factory=dict)
    run_id:          str                    = ""
    environment:     str                    = "osint"
    metadata:        Dict[str, Any]         = field(default_factory=dict)
    created_at:      str                    = field(
        default_factory=lambda: datetime.utcnow().isoformat()
    )

    def __post_init__(self) -> None:
        if not (0.0 <= self.score <= 1.0):
            raise ValueError(f"Opportunity.score must be 0.0–1.0, got {self.score}")
        if self.priority not in _PRIORITY_VALUES:
            raise ValueError(f"Opportunity.priority must be one of {_PRIORITY_VALUES}, got {self.priority!r}")


@dataclass
class Investigation:
    """
    A structured investigation plan built from an Opportunity.
    Produced by investigation/generator.py.
    """
    investigation_id: str
    opportunity_id:   str
    signal_id:        str
    hypothesis:       str                   # what we think this signal means
    queries:          List[str]             = field(default_factory=list)
    sources_to_check: List[str]             = field(default_factory=list)
    analyst_leads:    List[str]             = field(default_factory=list)
    run_id:           str                   = ""
    environment:      str                   = "osint"
    metadata:         Dict[str, Any]        = field(default_factory=dict)
    created_at:       str                   = field(
        default_factory=lambda: datetime.utcnow().isoformat()
    )


@dataclass
class Outcome:
    """
    The measured result of an Investigation.
    Produced by investigation/verifier.py.
    """
    outcome_id:       str
    investigation_id: str
    opportunity_id:   str
    signal_id:        str
    classification:   str                   # one of OUTCOME_CLASSES
    confidence:       float                 # 0.0 – 1.0
    evidence:         List[str]             = field(default_factory=list)
    corroborating_sources: List[str]        = field(default_factory=list)
    conflicting_sources:   List[str]        = field(default_factory=list)
    analyst_citations:     List[str]        = field(default_factory=list)
    notes:            str                   = ""
    run_id:           str                   = ""
    environment:      str                   = "osint"
    metrics:          Dict[str, Any]        = field(default_factory=dict)
    metadata:         Dict[str, Any]        = field(default_factory=dict)
    created_at:       str                   = field(
        default_factory=lambda: datetime.utcnow().isoformat()
    )

    def __post_init__(self) -> None:
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError(f"Outcome.confidence must be 0.0–1.0, got {self.confidence}")
        if self.classification not in OUTCOME_CLASSES:
            raise ValueError(f"Outcome.classification must be one of {OUTCOME_CLASSES}, got {self.classification!r}")


@dataclass
class IntelligenceRecord:
    """
    Reusable intelligence extracted from repeated Outcomes.
    The memory of the system. Stored in intelligence/store.py.
    """
    record_id:        str
    outcome_id:       str
    signal_id:        str
    signal_text:      str                   # original signal text; use this, never pattern, for scoring
    pattern:          str                   # formatted summary extracted from the outcome
    classification:   str                   # same as Outcome classification
    confidence:       float
    source_weight:    float                 # how much to trust this source class next cycle
    analyst_weight:   float                 # how much to trust the citing analysts
    times_seen:       int                   = 1
    first_seen:       str                   = field(
        default_factory=lambda: datetime.utcnow().isoformat()
    )
    last_seen:        str                   = field(
        default_factory=lambda: datetime.utcnow().isoformat()
    )
    run_id:           str                   = ""
    environment:      str                   = "osint"
    metadata:         Dict[str, Any]        = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name, val in (
            ("confidence", self.confidence),
            ("source_weight", self.source_weight),
            ("analyst_weight", self.analyst_weight),
        ):
            if not (0.0 <= val <= 1.0):
                raise ValueError(f"IntelligenceRecord.{name} must be 0.0–1.0, got {val}")


# ── Analyst tracking ──────────────────────────────────────────────────────────

@dataclass
class AnalystRecord:
    """
    A known analyst, journalist, or institutional voice tracked by the system.
    Credibility and weight are updated by the learning loop.
    """
    analyst_id:       str
    name:             str
    affiliation:      str                   # publication, think tank, independent
    source_type:      str                   # journalist | analyst | researcher | blogger
    domains:          List[str]             = field(default_factory=list)   # geopolitics, cyber, etc.
    credibility_score: float                = 0.5   # 0.0 – 1.0, updated by outcomes
    times_cited:      int                   = 0
    times_corroborated: int                 = 0
    times_conflicted: int                   = 0
    known_urls:       List[str]             = field(default_factory=list)
    notes:            str                   = ""
    run_id:           str                   = ""
    environment:      str                   = "osint"
    metadata:         Dict[str, Any]        = field(default_factory=dict)
    created_at:       str                   = field(
        default_factory=lambda: datetime.utcnow().isoformat()
    )
    updated_at:       str                   = field(
        default_factory=lambda: datetime.utcnow().isoformat()
    )

    def __post_init__(self) -> None:
        if not (0.0 <= self.credibility_score <= 1.0):
            raise ValueError(f"AnalystRecord.credibility_score must be 0.0–1.0, got {self.credibility_score}")
