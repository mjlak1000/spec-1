"""Full OSINT processing pipeline.

Orchestrates: feed collection → narrative detection → FARA/Congressional
collection → cross-verification → store.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from cls_osint.adapters import fara as fara_adapter
from cls_osint.adapters import congressional as congressional_adapter
from cls_osint.adapters import narrative as narrative_adapter
from cls_osint.adapters import verifier as verifier_adapter
from cls_osint.feed import fetch_all_rss
from cls_osint.schemas import (
    CongressRecord,
    FaraRecord,
    NarrativeRecord,
    OSINTRecord,
)
from cls_osint.sources import get_sources_by_type
from cls_osint.store import OsintStore


@dataclass
class PipelineStats:
    """Statistics for a single pipeline run."""

    run_id: str
    started_at: str
    rss_records: int = 0
    fara_records: int = 0
    congress_records: int = 0
    narrative_records: int = 0
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
            "rss_records": self.rss_records,
            "fara_records": self.fara_records,
            "congress_records": self.congress_records,
            "narrative_records": self.narrative_records,
            "stored": self.stored,
            "errors": self.errors,
        }


class OsintPipeline:
    """End-to-end OSINT collection and analysis pipeline."""

    def __init__(
        self,
        store_path: Path = Path("osint_records.jsonl"),
        feed_timeout: int = 15,
        run_id: str = "",
    ) -> None:
        self.store = OsintStore(store_path)
        self.feed_timeout = feed_timeout
        self.run_id = run_id or datetime.now(timezone.utc).strftime("run_%Y%m%d_%H%M%S")

    def run(
        self,
        collect_rss: bool = True,
        collect_fara: bool = True,
        collect_congress: bool = True,
        detect_narratives: bool = True,
    ) -> PipelineStats:
        """Execute the full OSINT pipeline."""
        stats = PipelineStats(
            run_id=self.run_id,
            started_at=datetime.now(timezone.utc).isoformat(),
        )

        all_osint: list[OSINTRecord] = []
        batch: list[dict] = []

        # 1. RSS feed collection
        if collect_rss:
            try:
                rss_sources = get_sources_by_type("RSS")
                result = fetch_all_rss(rss_sources, timeout=self.feed_timeout)
                rss_records: list[OSINTRecord] = result["records"]
                all_osint.extend(rss_records)
                stats.rss_records = len(rss_records)
                for src, err in result.get("errors", {}).items():
                    stats.errors.append(f"rss:{src}:{err}")
                batch.extend(r.to_dict() for r in rss_records)
            except Exception as exc:
                stats.errors.append(f"rss_collection:{exc}")

        # 2. FARA collection
        if collect_fara:
            try:
                fara_records: list[FaraRecord] = fara_adapter.collect(
                    timeout=self.feed_timeout
                )
                stats.fara_records = len(fara_records)
                for fr in fara_records:
                    osint_r = fr.to_osint_record()
                    all_osint.append(osint_r)
                    batch.append(osint_r.to_dict())
            except Exception as exc:
                stats.errors.append(f"fara_collection:{exc}")

        # 3. Congressional collection
        if collect_congress:
            try:
                congress_records: list[CongressRecord] = congressional_adapter.collect(
                    timeout=self.feed_timeout
                )
                stats.congress_records = len(congress_records)
                for cr in congress_records:
                    osint_r = cr.to_osint_record()
                    all_osint.append(osint_r)
                    batch.append(osint_r.to_dict())
            except Exception as exc:
                stats.errors.append(f"congress_collection:{exc}")

        # 4. Narrative detection
        if detect_narratives and all_osint:
            try:
                narrative_records: list[NarrativeRecord] = narrative_adapter.detect_narratives(
                    all_osint, min_hits=2
                )
                stats.narrative_records = len(narrative_records)
                for nr in narrative_records:
                    osint_r = nr.to_osint_record()
                    batch.append(osint_r.to_dict())
            except Exception as exc:
                stats.errors.append(f"narrative_detection:{exc}")

        # 5. Store all records
        if batch:
            try:
                written = self.store.append_batch(batch)
                stats.stored = len(written)
            except Exception as exc:
                stats.errors.append(f"store:{exc}")

        stats.finish()
        return stats

    def get_recent(self, n: int = 20) -> list[dict]:
        """Return the n most recent stored OSINT records."""
        return self.store.latest(n)

    def get_by_type(self, source_type: str) -> list[dict]:
        """Return all records of a given source_type."""
        return list(self.store.filter_by("source_type", source_type))


def run_pipeline(
    store_path: Path = Path("osint_records.jsonl"),
    feed_timeout: int = 15,
) -> PipelineStats:
    """Convenience function — run the full pipeline and return stats."""
    pipeline = OsintPipeline(store_path=store_path, feed_timeout=feed_timeout)
    return pipeline.run()
