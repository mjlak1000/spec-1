"""Psyop detection pipeline — end-to-end processing."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Sequence

from cls_psyop.patterns import PATTERNS
from cls_psyop.scorer import filter_risky, score_records, score_text
from cls_psyop.schemas import PsyopScore
from cls_psyop.store import PsyopStore


@dataclass
class PsyopPipelineStats:
    run_id: str
    started_at: str
    records_analysed: int = 0
    risky_detected: int = 0
    high_risk: int = 0
    medium_risk: int = 0
    low_risk: int = 0
    stored: int = 0
    errors: list[str] = field(default_factory=list)
    finished_at: Optional[str] = None

    def finish(self) -> None:
        self.finished_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "records_analysed": self.records_analysed,
            "risky_detected": self.risky_detected,
            "high_risk": self.high_risk,
            "medium_risk": self.medium_risk,
            "low_risk": self.low_risk,
            "stored": self.stored,
            "errors": self.errors,
        }


class PsyopPipeline:
    """End-to-end psyop detection pipeline."""

    def __init__(
        self,
        store_path: Path = Path("psyop_scores.jsonl"),
        run_id: str = "",
        min_classification: str = "LOW_RISK",
    ) -> None:
        self.store = PsyopStore(store_path)
        self.run_id = run_id or datetime.now(timezone.utc).strftime("run_%Y%m%d_%H%M%S")
        self.min_classification = min_classification

    def run(self, records: Sequence[dict]) -> PsyopPipelineStats:
        """Score all records for psyop indicators, persist risky ones."""
        stats = PsyopPipelineStats(
            run_id=self.run_id,
            started_at=datetime.now(timezone.utc).isoformat(),
        )

        records_list = list(records)
        stats.records_analysed = len(records_list)

        try:
            all_scores = score_records(records_list)
            risky = filter_risky(all_scores, self.min_classification)
            stats.risky_detected = len(risky)
            stats.high_risk = sum(1 for s in risky if s.classification == "HIGH_RISK")
            stats.medium_risk = sum(1 for s in risky if s.classification == "MEDIUM_RISK")
            stats.low_risk = sum(1 for s in risky if s.classification == "LOW_RISK")

            if risky:
                written = self.store.save_batch(risky)
                stats.stored = len(written)
        except Exception as exc:
            stats.errors.append(str(exc))

        stats.finish()
        return stats

    def analyse_text(self, text: str) -> PsyopScore:
        """Score a single piece of text and return the PsyopScore."""
        return score_text(text, PATTERNS)

    def get_high_risk(self) -> list[dict]:
        """Return stored HIGH_RISK scores."""
        return list(self.store.by_classification("HIGH_RISK"))


def run_pipeline(
    records: Sequence[dict],
    store_path: Path = Path("psyop_scores.jsonl"),
) -> PsyopPipelineStats:
    """Convenience function — run psyop pipeline on records."""
    pipeline = PsyopPipeline(store_path=store_path)
    return pipeline.run(records)
