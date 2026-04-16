"""Data schemas for cls_leads."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class Lead:
    """An actionable intelligence lead derived from one or more records."""

    lead_id: str
    title: str
    summary: str
    priority: str                    # "CRITICAL" | "HIGH" | "MEDIUM" | "LOW"
    category: str                    # "military" | "cyber" | "geopolitical" | "fara" | "psyop" | "quant"
    source_record_ids: list[str] = field(default_factory=list)
    action_items: list[str] = field(default_factory=list)
    confidence: float = 0.5
    generated_at: datetime = field(default_factory=_now)
    expires_at: datetime | None = None
    metadata: dict = field(default_factory=dict)

    @classmethod
    def make_id(cls, title: str, generated_at: str) -> str:
        raw = f"{title}::{generated_at}"
        return "lead_" + hashlib.sha256(raw.encode()).hexdigest()[:12]

    def to_dict(self) -> dict:
        return {
            "lead_id": self.lead_id,
            "title": self.title,
            "summary": self.summary,
            "priority": self.priority,
            "category": self.category,
            "source_record_ids": self.source_record_ids,
            "action_items": self.action_items,
            "confidence": self.confidence,
            "generated_at": self.generated_at.isoformat()
            if isinstance(self.generated_at, datetime)
            else str(self.generated_at),
            "expires_at": self.expires_at.isoformat()
            if isinstance(self.expires_at, datetime)
            else None,
            "metadata": self.metadata,
        }
