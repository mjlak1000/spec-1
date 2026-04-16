"""Cross-source verifier for OSINT records.

Checks whether a claim or record appears across multiple independent sources,
assigning a corroboration score and classification.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Sequence

from cls_osint.schemas import FaraRecord, CongressRecord, NarrativeRecord, OSINTRecord


@dataclass
class VerificationResult:
    """Result of cross-source verification."""

    result_id: str
    claim: str
    corroboration_count: int       # Number of independent sources confirming
    total_sources_checked: int
    corroboration_score: float     # 0–1
    classification: str            # "Corroborated" | "Partial" | "Unverified" | "Conflicted"
    supporting_urls: list[str] = field(default_factory=list)
    conflicting_urls: list[str] = field(default_factory=list)
    verified_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        return {
            "result_id": self.result_id,
            "claim": self.claim,
            "corroboration_count": self.corroboration_count,
            "total_sources_checked": self.total_sources_checked,
            "corroboration_score": self.corroboration_score,
            "classification": self.classification,
            "supporting_urls": self.supporting_urls,
            "conflicting_urls": self.conflicting_urls,
            "verified_at": self.verified_at.isoformat(),
        }


def _make_result_id(claim: str) -> str:
    return "verif_" + hashlib.sha256(claim.encode()).hexdigest()[:12]


def _extract_keywords(text: str) -> set[str]:
    """Extract meaningful keywords (3+ char words) from text."""
    words = re.findall(r"\b[a-zA-Z]{3,}\b", text.lower())
    stopwords = {
        "the", "and", "for", "are", "was", "has", "have", "that", "with",
        "this", "from", "its", "been", "also", "will", "can", "but", "not",
        "they", "their", "which", "more", "said", "into", "about", "than",
    }
    return {w for w in words if w not in stopwords}


def _text_overlap(claim_kw: set[str], record_text: str) -> float:
    """Compute keyword overlap ratio between claim and record text."""
    if not claim_kw:
        return 0.0
    record_kw = _extract_keywords(record_text)
    intersection = claim_kw & record_kw
    return len(intersection) / len(claim_kw)


def _classify(score: float, count: int) -> str:
    if score >= 0.7 and count >= 2:
        return "Corroborated"
    if score >= 0.4 or count >= 2:
        return "Partial"
    if score > 0 and count >= 1:
        return "Unverified"
    return "Unverified"


def verify_claim(
    claim: str,
    records: Sequence[OSINTRecord],
    overlap_threshold: float = 0.3,
) -> VerificationResult:
    """Verify a claim against a corpus of OSINTRecords.

    A record is considered supporting if its text overlaps the claim
    keywords above `overlap_threshold`.
    """
    claim_kw = _extract_keywords(claim)
    supporting: list[str] = []
    conflicting: list[str] = []
    total = len(list(records))

    seen_sources: set[str] = set()

    for rec in records:
        overlap = _text_overlap(claim_kw, rec.content)
        if overlap >= overlap_threshold:
            # Count unique source names for corroboration
            if rec.source_name not in seen_sources:
                seen_sources.add(rec.source_name)
                supporting.append(rec.url)

    corroboration_count = len(seen_sources)
    score = min(1.0, corroboration_count / max(total, 1) * 5.0) if total > 0 else 0.0
    score = round(min(1.0, score), 3)
    classification = _classify(score, corroboration_count)

    return VerificationResult(
        result_id=_make_result_id(claim),
        claim=claim,
        corroboration_count=corroboration_count,
        total_sources_checked=total,
        corroboration_score=score,
        classification=classification,
        supporting_urls=supporting[:10],
        conflicting_urls=conflicting[:10],
    )


def verify_fara_record(
    record: FaraRecord,
    osint_records: Sequence[OSINTRecord],
) -> VerificationResult:
    """Verify a FARA record against the broader OSINT corpus."""
    claim = (
        f"{record.registrant} acting as foreign agent for "
        f"{record.foreign_principal} ({record.country})"
    )
    return verify_claim(claim, osint_records)


def verify_congress_record(
    record: CongressRecord,
    osint_records: Sequence[OSINTRecord],
) -> VerificationResult:
    """Verify a congressional record against the broader OSINT corpus."""
    claim = f"{record.bill_id} {record.title} sponsored by {record.sponsor}"
    return verify_claim(claim, osint_records)


def verify_narrative(
    record: NarrativeRecord,
    osint_records: Sequence[OSINTRecord],
) -> VerificationResult:
    """Verify a narrative record against the broader OSINT corpus."""
    claim = record.theme + " " + record.description
    return verify_claim(claim, osint_records)
