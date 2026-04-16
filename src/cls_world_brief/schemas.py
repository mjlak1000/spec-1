"""Data schemas for cls_world_brief."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class BriefSection:
    """A named section within a world brief."""

    title: str
    body: str
    source_record_ids: list[str] = field(default_factory=list)


@dataclass
class WorldBrief:
    """A daily world intelligence brief."""

    brief_id: str
    date: str                    # ISO date "YYYY-MM-DD"
    headline: str                # One-sentence top-line assessment
    summary: str                 # 2–3 paragraph executive summary
    sections: list[BriefSection] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)    # Source URLs
    confidence: float = 0.7
    produced_at: datetime = field(default_factory=_now)
    metadata: dict = field(default_factory=dict)

    @classmethod
    def make_id(cls, date: str) -> str:
        return "brief_" + hashlib.sha256(date.encode()).hexdigest()[:12]

    def to_dict(self) -> dict:
        return {
            "brief_id": self.brief_id,
            "date": self.date,
            "headline": self.headline,
            "summary": self.summary,
            "sections": [
                {
                    "title": s.title,
                    "body": s.body,
                    "source_record_ids": s.source_record_ids,
                }
                for s in self.sections
            ],
            "sources": self.sources,
            "confidence": self.confidence,
            "produced_at": self.produced_at.isoformat()
            if isinstance(self.produced_at, datetime)
            else str(self.produced_at),
            "metadata": self.metadata,
        }
