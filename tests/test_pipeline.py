"""Tests for cls_osint.pipeline — full OSINT processing pipeline."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from cls_osint.schemas import FaraRecord, CongressRecord, NarrativeRecord, OSINTRecord
from cls_osint.pipeline import OsintPipeline, PipelineStats, run_pipeline
from datetime import datetime, timezone


def _make_osint_record(record_id="rec_001", source_type="RSS", content="Defense spending increased"):
    return OSINTRecord(
        record_id=record_id,
        source_type=source_type,
        source_name="war_on_the_rocks",
        content=content,
        url="https://example.com/article",
    )


def _make_fara_record():
    return FaraRecord(
        record_id="fara_001",
        registrant="Acme Consulting",
        foreign_principal="Ministry of Foreign Affairs",
        country="Russia",
        activities=["Lobbying", "Public relations"],
        filed_at=datetime(2024, 1, 10, tzinfo=timezone.utc),
        doc_url="https://fara.gov/docs/001",
    )


def _make_congress_record():
    return CongressRecord(
        record_id="congress_001",
        record_type="BILL",
        bill_id="H.R.1234",
        title="National Defense Authorization Act",
        sponsor="Rep. Smith",
        chamber="HOUSE",
        status="INTRODUCED",
        date=datetime(2024, 1, 5, tzinfo=timezone.utc),
        summary="Authorizes defense spending for FY2025.",
        url="https://congress.gov/bill/1234",
        tags=["defense", "budget"],
    )


class TestPipelineStats:
    def test_to_dict_has_all_fields(self):
        stats = PipelineStats(run_id="r1", started_at="2024-01-01T00:00:00Z")
        d = stats.to_dict()
        assert "run_id" in d
        assert "rss_records" in d
        assert "fara_records" in d
        assert "congress_records" in d
        assert "narrative_records" in d
        assert "stored" in d
        assert "errors" in d

    def test_finish_sets_finished_at(self):
        stats = PipelineStats(run_id="r1", started_at="2024-01-01T00:00:00Z")
        assert stats.finished_at is None
        stats.finish()
        assert stats.finished_at is not None


class TestOsintPipeline:
    def test_run_stores_records(self, tmp_path):
        store_path = tmp_path / "osint.jsonl"
        pipeline = OsintPipeline(store_path=store_path, run_id="test_run")

        rss_records = [_make_osint_record("rec1"), _make_osint_record("rec2")]
        fara_records = [_make_fara_record()]
        congress_records = [_make_congress_record()]

        with patch("cls_osint.pipeline.fetch_all_rss") as mock_rss, \
             patch("cls_osint.pipeline.fara_adapter.collect") as mock_fara, \
             patch("cls_osint.pipeline.congressional_adapter.collect") as mock_congress, \
             patch("cls_osint.pipeline.narrative_adapter.detect_narratives") as mock_narrative:

            mock_rss.return_value = {"records": rss_records, "errors": {}}
            mock_fara.return_value = fara_records
            mock_congress.return_value = congress_records
            mock_narrative.return_value = []

            stats = pipeline.run()

        assert stats.rss_records == 2
        assert stats.fara_records == 1
        assert stats.congress_records == 1
        assert stats.stored > 0
        assert store_path.exists()

    def test_run_captures_rss_errors(self, tmp_path):
        store_path = tmp_path / "osint.jsonl"
        pipeline = OsintPipeline(store_path=store_path)

        with patch("cls_osint.pipeline.fetch_all_rss") as mock_rss, \
             patch("cls_osint.pipeline.fara_adapter.collect", return_value=[]), \
             patch("cls_osint.pipeline.congressional_adapter.collect", return_value=[]), \
             patch("cls_osint.pipeline.narrative_adapter.detect_narratives", return_value=[]):

            mock_rss.return_value = {
                "records": [_make_osint_record()],
                "errors": {"bad_source": "Connection refused"},
            }
            stats = pipeline.run()

        assert any("bad_source" in e for e in stats.errors)

    def test_narrative_detection_runs_on_records(self, tmp_path):
        store_path = tmp_path / "osint.jsonl"
        pipeline = OsintPipeline(store_path=store_path)

        records = [_make_osint_record(f"rec_{i}", content="Ukraine invasion russia") for i in range(3)]

        with patch("cls_osint.pipeline.fetch_all_rss") as mock_rss, \
             patch("cls_osint.pipeline.fara_adapter.collect", return_value=[]), \
             patch("cls_osint.pipeline.congressional_adapter.collect", return_value=[]), \
             patch("cls_osint.pipeline.narrative_adapter.detect_narratives") as mock_narrative:

            mock_rss.return_value = {"records": records, "errors": {}}
            mock_narrative.return_value = []

            stats = pipeline.run(detect_narratives=True)

        mock_narrative.assert_called_once()

    def test_run_skip_flags(self, tmp_path):
        store_path = tmp_path / "osint.jsonl"
        pipeline = OsintPipeline(store_path=store_path)

        with patch("cls_osint.pipeline.fetch_all_rss") as mock_rss, \
             patch("cls_osint.pipeline.fara_adapter.collect") as mock_fara, \
             patch("cls_osint.pipeline.congressional_adapter.collect") as mock_congress:

            stats = pipeline.run(
                collect_rss=False,
                collect_fara=False,
                collect_congress=False,
                detect_narratives=False,
            )

        mock_rss.assert_not_called()
        mock_fara.assert_not_called()
        mock_congress.assert_not_called()
        assert stats.rss_records == 0

    def test_get_recent_returns_records(self, tmp_path):
        store_path = tmp_path / "osint.jsonl"
        pipeline = OsintPipeline(store_path=store_path)

        records = [_make_osint_record(f"r{i}") for i in range(5)]
        pipeline.store.append_batch([r.to_dict() for r in records])

        recent = pipeline.get_recent(3)
        assert len(recent) == 3

    def test_get_by_type_filters(self, tmp_path):
        store_path = tmp_path / "osint.jsonl"
        pipeline = OsintPipeline(store_path=store_path)

        pipeline.store.append({"record_id": "r1", "source_type": "FARA", "content": "x"})
        pipeline.store.append({"record_id": "r2", "source_type": "rss", "content": "y"})
        pipeline.store.append({"record_id": "r3", "source_type": "FARA", "content": "z"})

        fara_records = pipeline.get_by_type("FARA")
        assert len(fara_records) == 2
        assert all(r["source_type"] == "FARA" for r in fara_records)


class TestRunPipeline:
    def test_convenience_function(self, tmp_path):
        store_path = tmp_path / "osint.jsonl"

        with patch("cls_osint.pipeline.fetch_all_rss") as mock_rss, \
             patch("cls_osint.pipeline.fara_adapter.collect", return_value=[]), \
             patch("cls_osint.pipeline.congressional_adapter.collect", return_value=[]), \
             patch("cls_osint.pipeline.narrative_adapter.detect_narratives", return_value=[]):

            mock_rss.return_value = {"records": [], "errors": {}}
            stats = run_pipeline(store_path=store_path)

        assert isinstance(stats, PipelineStats)
        assert stats.finished_at is not None
