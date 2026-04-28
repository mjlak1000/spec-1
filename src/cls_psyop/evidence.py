"""Evidence chains for psyop pattern detection."""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class EvidenceChain:
    """Structured evidence for a single psyop pattern that fired."""

    pattern_name: str
    confidence: float
    supporting_signals: list   # signal_ids that triggered this pattern
    raw_excerpts: list         # {signal_id, source, text_snippet, url}
    source_metadata: list      # {source, credibility_score, signal_count, first_seen, last_seen}
    cross_references: list     # signal_ids appearing in 2+ sources on same topic
    summary: str               # one-sentence human-readable description
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict:
        return {
            "pattern_name": self.pattern_name,
            "confidence": self.confidence,
            "supporting_signals": self.supporting_signals,
            "raw_excerpts": self.raw_excerpts,
            "source_metadata": self.source_metadata,
            "cross_references": self.cross_references,
            "summary": self.summary,
            "created_at": self.created_at,
        }


class EvidenceStore:
    """Thread-safe append-only JSONL store for EvidenceChain records."""

    def __init__(self, path: Path = Path("spec1_psyop_evidence.jsonl")) -> None:
        self.path = Path(path)
        self._lock = threading.Lock()

    def append(self, chain: EvidenceChain, run_id: str = "") -> dict:
        entry = {**chain.to_dict(), "run_id": run_id}
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry) + "\n")
        return entry

    def append_batch(self, chains: list[EvidenceChain], run_id: str = "") -> list[dict]:
        if not chains:
            return []
        written: list[dict] = []
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as fh:
                for chain in chains:
                    entry = {**chain.to_dict(), "run_id": run_id}
                    fh.write(json.dumps(entry) + "\n")
                    written.append(entry)
        return written

    def read_all(self):
        if not self.path.exists():
            return
        with self.path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue

    def count(self) -> int:
        return sum(1 for _ in self.read_all())
