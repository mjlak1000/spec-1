"""
SPEC-1 — intelligence/store.py

In-memory intelligence store for v0.1.
v1.0: replace with PostgreSQL append-only insert layer.

Design rules:
  - Append-only: records are never deleted or updated in place
  - run_id links every record to its cycle
  - query by classification, source, domain, or confidence
"""

from __future__ import annotations

from typing import Dict, List, Optional

from spec1_engine.schemas.models import IntelligenceRecord


class IntelligenceStore:
    """
    Stores IntelligenceRecords in memory.
    Thread-safety not guaranteed in v0.1.
    """

    def __init__(self) -> None:
        self._records: Dict[str, IntelligenceRecord] = {}

    def save(self, record: IntelligenceRecord) -> None:
        """Append a new record. Never overwrites existing records."""
        if record.record_id not in self._records:
            self._records[record.record_id] = record

    def get(self, record_id: str) -> Optional[IntelligenceRecord]:
        return self._records.get(record_id)

    def all(self) -> List[IntelligenceRecord]:
        return list(self._records.values())

    def by_classification(self, classification: str) -> List[IntelligenceRecord]:
        return [r for r in self._records.values() if r.classification == classification]

    def by_source(self, source: str) -> List[IntelligenceRecord]:
        return [
            r for r in self._records.values()
            if r.metadata.get("source") == source
        ]

    def by_domain(self, domain: str) -> List[IntelligenceRecord]:
        return [
            r for r in self._records.values()
            if domain in r.metadata.get("domains", [])
        ]

    def high_confidence(self, threshold: float = 0.70) -> List[IntelligenceRecord]:
        return [r for r in self._records.values() if r.confidence >= threshold]

    def summary(self) -> Dict[str, int]:
        """Count records by classification."""
        counts: Dict[str, int] = {}
        for r in self._records.values():
            counts[r.classification] = counts.get(r.classification, 0) + 1
        return counts

    def __len__(self) -> int:
        return len(self._records)
