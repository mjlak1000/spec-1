"""Data schemas for cls_psyop."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class PsyopPattern:
    """A known psychological-operation signature pattern."""

    pattern_id: str
    name: str
    description: str
    indicators: list[str]          # Keyword/phrase indicators
    threat_level: str              # "HIGH" | "MEDIUM" | "LOW"
    category: str                  # "amplification" | "framing" | "disinformation" | "fear" | "wedge"
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "pattern_id": self.pattern_id,
            "name": self.name,
            "description": self.description,
            "indicators": self.indicators,
            "threat_level": self.threat_level,
            "category": self.category,
            "metadata": self.metadata,
        }


@dataclass
class PsyopScore:
    """Result of scoring a piece of text for psyop patterns."""

    score_id: str
    text_hash: str                 # SHA-256 of the analysed text
    text_excerpt: str              # First 200 chars of text
    patterns_matched: list[str]    # pattern_ids that matched
    pattern_names: list[str]       # human-readable pattern names
    score: float                   # 0–1 psyop likelihood
    classification: str            # "HIGH_RISK" | "MEDIUM_RISK" | "LOW_RISK" | "CLEAN"
    threat_categories: list[str]   # unique threat categories matched
    scored_at: datetime = field(default_factory=_now)
    metadata: dict = field(default_factory=dict)

    @classmethod
    def make_id(cls, text_hash: str) -> str:
        return "psyop_" + hashlib.sha256(text_hash.encode()).hexdigest()[:12]

    def to_dict(self) -> dict:
        return {
            "score_id": self.score_id,
            "text_hash": self.text_hash,
            "text_excerpt": self.text_excerpt,
            "patterns_matched": self.patterns_matched,
            "pattern_names": self.pattern_names,
            "score": self.score,
            "classification": self.classification,
            "threat_categories": self.threat_categories,
            "scored_at": self.scored_at.isoformat()
            if isinstance(self.scored_at, datetime)
            else str(self.scored_at),
            "metadata": self.metadata,
        }
