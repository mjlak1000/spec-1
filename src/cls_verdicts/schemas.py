"""Data schemas for cls_verdicts."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal


VerdictKind = Literal["correct", "incorrect", "partial", "unclear"]
VALID_VERDICTS: frozenset[str] = frozenset({"correct", "incorrect", "partial", "unclear"})


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class Verdict:
    """A human verdict on a previously stored intelligence record.

    Multiple verdicts can be filed for the same record_id over time;
    aggregators in cls_calibration decide how to fold them.
    """

    verdict_id: str
    record_id: str
    verdict: VerdictKind
    reviewer: str = "anonymous"
    reviewed_at: datetime = field(default_factory=_now)
    notes: str = ""

    def __post_init__(self) -> None:
        if self.verdict not in VALID_VERDICTS:
            raise ValueError(
                f"verdict must be one of {sorted(VALID_VERDICTS)}, got {self.verdict!r}"
            )

    @classmethod
    def make_id(cls, record_id: str, reviewer: str, reviewed_at: datetime | str) -> str:
        ts = reviewed_at.isoformat() if isinstance(reviewed_at, datetime) else str(reviewed_at)
        raw = f"{record_id}::{reviewer}::{ts}"
        return "verdict_" + hashlib.sha256(raw.encode()).hexdigest()[:12]

    def to_dict(self) -> dict:
        return {
            "verdict_id": self.verdict_id,
            "record_id": self.record_id,
            "verdict": self.verdict,
            "reviewer": self.reviewer,
            "reviewed_at": self.reviewed_at.isoformat()
            if isinstance(self.reviewed_at, datetime)
            else str(self.reviewed_at),
            "notes": self.notes,
        }
