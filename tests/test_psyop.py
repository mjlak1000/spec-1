"""Tests for cls_psyop — psyop detection pipeline."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from cls_psyop.schemas import PsyopPattern, PsyopScore
from cls_psyop.patterns import PATTERNS, PATTERN_INDEX, get_pattern, get_patterns_by_category
from cls_psyop.scorer import score_text, score_records, filter_risky, _classify_score
from cls_psyop.pipeline import PsyopPipeline, PsyopPipelineStats, run_pipeline
from cls_psyop.store import PsyopStore


class TestPsyopPatternRegistry:
    def test_patterns_list_is_non_empty(self):
        assert len(PATTERNS) > 5

    def test_all_patterns_have_required_fields(self):
        for p in PATTERNS:
            assert p.pattern_id
            assert p.name
            assert p.indicators
            assert p.threat_level in ("HIGH", "MEDIUM", "LOW")
            assert p.category

    def test_get_pattern_by_id(self):
        p = get_pattern("P001")
        assert p is not None
        assert p.name == "Fear Amplification"

    def test_get_pattern_returns_none_for_unknown(self):
        assert get_pattern("P999") is None

    def test_get_patterns_by_category(self):
        fear_patterns = get_patterns_by_category("fear")
        assert len(fear_patterns) >= 1
        assert all(p.category == "fear" for p in fear_patterns)

    def test_disinformation_category_exists(self):
        patterns = get_patterns_by_category("disinformation")
        assert len(patterns) >= 1

    def test_wedge_category_exists(self):
        patterns = get_patterns_by_category("wedge")
        assert len(patterns) >= 1


class TestPsyopScore:
    def test_make_id(self):
        score_id = PsyopScore.make_id("abc123")
        assert score_id.startswith("psyop_")

    def test_to_dict_has_required_fields(self):
        score = PsyopScore(
            score_id="psyop_001",
            text_hash="hash123",
            text_excerpt="Test text",
            patterns_matched=["P001"],
            pattern_names=["Fear Amplification"],
            score=0.75,
            classification="HIGH_RISK",
            threat_categories=["fear"],
        )
        d = score.to_dict()
        assert d["score_id"] == "psyop_001"
        assert d["classification"] == "HIGH_RISK"
        assert d["score"] == 0.75


class TestClassifyScore:
    def test_high_score_high_count_is_high_risk(self):
        assert _classify_score(0.8, 4) == "HIGH_RISK"

    def test_medium_score_is_medium_risk(self):
        assert _classify_score(0.5, 2) == "MEDIUM_RISK"

    def test_low_score_is_low_risk(self):
        assert _classify_score(0.1, 1) == "LOW_RISK"

    def test_zero_score_is_clean(self):
        assert _classify_score(0.0, 0) == "CLEAN"


class TestScoreText:
    def test_fear_amplification_detected(self):
        text = "This is a catastrophic existential threat and inevitable doom approaching"
        result = score_text(text)
        assert result.score > 0
        assert "P001" in result.patterns_matched or result.classification != "CLEAN"

    def test_false_flag_detected(self):
        text = "This is a false flag staged by deep state inside job government orchestrated"
        result = score_text(text)
        assert "P002" in result.patterns_matched

    def test_social_wedge_detected(self):
        text = "They hate you, it's us vs them, patriots vs traitors take our country back"
        result = score_text(text)
        assert "P003" in result.patterns_matched

    def test_dehumanization_detected(self):
        text = "These vermin cockroaches are an infestation parasites destroying society"
        result = score_text(text)
        assert "P011" in result.patterns_matched
        assert result.classification in ("HIGH_RISK", "MEDIUM_RISK")

    def test_clean_text_is_clean(self):
        text = "The weather forecast for tomorrow shows sunny skies and mild temperatures."
        result = score_text(text)
        assert result.classification == "CLEAN"
        assert result.score == 0.0

    def test_score_is_bounded_zero_to_one(self):
        text = " ".join(
            ["catastrophic", "imminent threat", "false flag", "inside job",
             "they hate you", "vermin", "cockroaches", "deep state", "staged"]
        )
        result = score_text(text)
        assert 0.0 <= result.score <= 1.0

    def test_result_has_text_hash(self):
        result = score_text("Test content")
        assert len(result.text_hash) == 64  # SHA-256 hex

    def test_result_has_text_excerpt(self):
        text = "A" * 300
        result = score_text(text)
        assert len(result.text_excerpt) <= 200


class TestScoreRecords:
    def test_scores_multiple_records(self):
        records = [
            {"record_id": "r1", "content": "Catastrophic existential threat imminent doom"},
            {"record_id": "r2", "content": "Normal news report about budget."},
        ]
        scores = score_records(records)
        assert len(scores) == 2

    def test_skips_records_without_text(self):
        records = [
            {"record_id": "r1", "confidence": 0.9},
            {"record_id": "r2", "content": "Fear threat catastrophic"},
        ]
        scores = score_records(records)
        assert len(scores) == 1

    def test_metadata_includes_source_record_id(self):
        records = [{"record_id": "my_record", "content": "Test content"}]
        scores = score_records(records)
        assert scores[0].metadata.get("source_record_id") == "my_record"


class TestFilterRisky:
    def test_filters_by_low_risk_threshold(self):
        scores = [
            PsyopScore("s1", "h1", "t1", ["P001"], ["Fear"], 0.8, "HIGH_RISK", ["fear"]),
            PsyopScore("s2", "h2", "t2", [], [], 0.0, "CLEAN", []),
        ]
        risky = filter_risky(scores, "LOW_RISK")
        assert len(risky) == 1
        assert risky[0].classification == "HIGH_RISK"

    def test_filters_by_medium_risk_threshold(self):
        scores = [
            PsyopScore("s1", "h1", "t1", ["P001"], ["Fear"], 0.8, "HIGH_RISK", ["fear"]),
            PsyopScore("s2", "h2", "t2", ["P009"], ["Whataboutism"], 0.3, "MEDIUM_RISK", ["framing"]),
            PsyopScore("s3", "h3", "t3", [], [], 0.05, "LOW_RISK", []),
        ]
        risky = filter_risky(scores, "MEDIUM_RISK")
        assert len(risky) == 2

    def test_all_clean_returns_empty_for_low_risk(self):
        scores = [PsyopScore("s1", "h1", "t1", [], [], 0.0, "CLEAN", [])]
        risky = filter_risky(scores, "LOW_RISK")
        assert risky == []


class TestPsyopStore:
    def test_save_and_read_back(self, tmp_path):
        store = PsyopStore(tmp_path / "psyop.jsonl")
        score = PsyopScore(
            score_id="psyop_001",
            text_hash="h1",
            text_excerpt="Test",
            patterns_matched=["P001"],
            pattern_names=["Fear"],
            score=0.8,
            classification="HIGH_RISK",
            threat_categories=["fear"],
        )
        store.save(score)

        records = list(store.read_all())
        assert len(records) == 1
        assert records[0]["classification"] == "HIGH_RISK"

    def test_save_batch(self, tmp_path):
        store = PsyopStore(tmp_path / "psyop.jsonl")
        scores = [
            PsyopScore(f"s{i}", f"h{i}", "t", [], [], 0.5, "MEDIUM_RISK", [])
            for i in range(5)
        ]
        store.save_batch(scores)
        assert store.count() == 5

    def test_by_classification(self, tmp_path):
        store = PsyopStore(tmp_path / "psyop.jsonl")
        store.save(PsyopScore("s1", "h1", "t", ["P001"], ["Fear"], 0.9, "HIGH_RISK", ["fear"]))
        store.save(PsyopScore("s2", "h2", "t", [], [], 0.0, "CLEAN", []))

        high = list(store.by_classification("HIGH_RISK"))
        assert len(high) == 1

    def test_clear(self, tmp_path):
        store = PsyopStore(tmp_path / "psyop.jsonl")
        store.save(PsyopScore("s1", "h1", "t", [], [], 0.0, "CLEAN", []))
        store.clear()
        assert store.count() == 0


class TestPsyopPipeline:
    def test_run_scores_records(self, tmp_path):
        store_path = tmp_path / "psyop.jsonl"
        pipeline = PsyopPipeline(store_path=store_path, run_id="test_run")

        records = [
            {"record_id": "r1", "content": "Catastrophic existential threat imminent doom false flag"},
            {"record_id": "r2", "content": "Normal weather report today."},
        ]
        stats = pipeline.run(records)

        assert stats.records_analysed == 2
        assert stats.finished_at is not None

    def test_analyse_text(self, tmp_path):
        pipeline = PsyopPipeline(store_path=tmp_path / "psyop.jsonl")
        result = pipeline.analyse_text("This is a false flag staged inside job")
        assert isinstance(result, PsyopScore)

    def test_stats_to_dict(self):
        stats = PsyopPipelineStats(run_id="r1", started_at="2024-01-01T00:00:00Z")
        stats.finish()
        d = stats.to_dict()
        assert "records_analysed" in d
        assert "risky_detected" in d
        assert "finished_at" in d


class TestRunPipelineConvenience:
    def test_convenience_function(self, tmp_path):
        records = [{"record_id": "r1", "content": "Test content"}]
        stats = run_pipeline(records=records, store_path=tmp_path / "p.jsonl")
        assert isinstance(stats, PsyopPipelineStats)
