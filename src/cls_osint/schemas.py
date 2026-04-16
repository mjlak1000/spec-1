"""Data schemas for cls_osint."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _make_id(prefix: str, *parts: str) -> str:
    raw = ":".join(parts)
    return f"{prefix}_{hashlib.sha256(raw.encode()).hexdigest()[:12]}"


@dataclass
class OSINTRecord:
    """Generic OSINT record produced by any adapter."""

    record_id: str
    source_type: str       # "fara" | "congressional" | "narrative" | "rss"
    source_name: str
    content: str
    url: str
    collected_at: datetime = field(default_factory=_now)
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "record_id": self.record_id,
            "source_type": self.source_type,
            "source_name": self.source_name,
            "content": self.content,
            "url": self.url,
            "collected_at": self.collected_at.isoformat(),
            "metadata": self.metadata,
        }


@dataclass
class FaraRecord:
    """A Foreign Agents Registration Act filing."""

    record_id: str
    registrant: str              # Entity registering as foreign agent
    foreign_principal: str       # Foreign government / entity being represented
    country: str
    activities: list[str]        # Described activities
    filed_at: datetime
    doc_url: str
    registration_number: str = ""
    status: str = "ACTIVE"       # "active" | "terminated"
    metadata: dict = field(default_factory=dict)

    @classmethod
    def make_id(cls, registrant: str, foreign_principal: str, filed_at: str) -> str:
        return _make_id("fara", registrant, foreign_principal, filed_at)

    def to_dict(self) -> dict:
        return {
            "record_id": self.record_id,
            "registrant": self.registrant,
            "foreign_principal": self.foreign_principal,
            "country": self.country,
            "activities": self.activities,
            "filed_at": self.filed_at.isoformat() if isinstance(self.filed_at, datetime) else str(self.filed_at),
            "doc_url": self.doc_url,
            "registration_number": self.registration_number,
            "status": self.status,
            "metadata": self.metadata,
        }

    def to_osint_record(self) -> OSINTRecord:
        summary = (
            f"{self.registrant} registered as foreign agent for {self.foreign_principal} "
            f"({self.country}). Activities: {'; '.join(self.activities)}."
        )
        return OSINTRecord(
            record_id=self.record_id,
            source_type="FARA",
            source_name="fara_db",
            content=summary,
            url=self.doc_url,
            collected_at=_now(),
            metadata=self.to_dict(),
        )


@dataclass
class CongressRecord:
    """A US Congressional record (bill, hearing, or resolution)."""

    record_id: str
    record_type: str         # BILL | RESOLUTION | HEARING | AMENDMENT
    bill_id: str             # e.g. "H.R.1234" or "S.567"
    title: str
    sponsor: str
    chamber: str             # HOUSE | SENATE
    status: str              # INTRODUCED | PASSED_HOUSE | PASSED_SENATE | ENACTED | FAILED
    date: datetime
    summary: str
    url: str
    tags: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    @classmethod
    def make_id(cls, bill_id: str, date: str) -> str:
        return _make_id("congress", bill_id, date)

    def to_dict(self) -> dict:
        return {
            "record_id": self.record_id,
            "record_type": self.record_type,
            "bill_id": self.bill_id,
            "title": self.title,
            "sponsor": self.sponsor,
            "chamber": self.chamber,
            "status": self.status,
            "date": self.date.isoformat() if isinstance(self.date, datetime) else str(self.date),
            "summary": self.summary,
            "url": self.url,
            "tags": self.tags,
            "metadata": self.metadata,
        }

    def to_osint_record(self) -> OSINTRecord:
        content = f"{self.bill_id}: {self.title}. Sponsor: {self.sponsor}. Status: {self.status}. {self.summary}"
        return OSINTRecord(
            record_id=self.record_id,
            source_type="CONGRESSIONAL",
            source_name="congress_gov",
            content=content,
            url=self.url,
            collected_at=_now(),
            metadata=self.to_dict(),
        )


@dataclass
class NarrativeRecord:
    """A detected influence or narrative pattern across sources."""

    record_id: str
    theme: str               # Short label, e.g. "China-Taiwan escalation"
    description: str         # Human-readable summary
    amplifiers: list[str]    # Accounts / outlets amplifying
    reach_score: float       # 0–1 estimated reach
    sentiment: str           # POSITIVE | NEGATIVE | NEUTRAL | MIXED
    source_urls: list[str]
    detected_at: datetime = field(default_factory=_now)
    metadata: dict = field(default_factory=dict)

    @classmethod
    def make_id(cls, theme: str, detected_at: str) -> str:
        return _make_id("narrative", theme, detected_at)

    def to_dict(self) -> dict:
        return {
            "record_id": self.record_id,
            "theme": self.theme,
            "description": self.description,
            "amplifiers": self.amplifiers,
            "reach_score": self.reach_score,
            "sentiment": self.sentiment,
            "source_urls": self.source_urls,
            "detected_at": self.detected_at.isoformat() if isinstance(self.detected_at, datetime) else str(self.detected_at),
            "metadata": self.metadata,
        }

    def to_osint_record(self) -> OSINTRecord:
        amplifier_str = ", ".join(self.amplifiers[:5])
        content = (
            f"Narrative detected: {self.theme}. {self.description} "
            f"Amplifiers: {amplifier_str}. Reach score: {self.reach_score:.2f}."
        )
        return OSINTRecord(
            record_id=self.record_id,
            source_type="NARRATIVE",
            source_name="narrative_tracker",
            content=content,
            url=self.source_urls[0] if self.source_urls else "",
            collected_at=self.detected_at,
            metadata=self.to_dict(),
        )
