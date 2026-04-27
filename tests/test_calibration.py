"""Tests for cls_calibration aggregator and the /calibration/report endpoint."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from cls_calibration.aggregator import _bucket_label, produce_report, score_verdict
from cls_calibration.schemas import Bucket, CalibrationReport
from cls_verdicts.store import VerdictStore
from cls_verdicts.schemas import Verdict
from spec1_engine.intelligence.store import JsonlStore
from spec1_api.dependencies import get_intel_store, get_verdict_store
from spec1_api.main import app


# ── score_verdict / _bucket_label ──────────────────────────────────────────


def test_score_verdict_mapping():
    assert score_verdict("correct") == 1.0
    assert score_verdict("partial") == 0.5
    assert score_verdict("incorrect") == 0.0
    assert score_verdict("unclear") is None
    assert score_verdict("garbage") is None


def test_bucket_label_edges():
    assert _bucket_label(0.0) == "0.0-0.2"
    assert _bucket_label(0.19) == "0.0-0.2"
    assert _bucket_label(0.2) == "0.2-0.4"
    assert _bucket_label(0.79) == "0.6-0.8"
    assert _bucket_label(0.8) == "0.8-1.0"
    assert _bucket_label(1.0) == "0.8-1.0"  # last bucket inclusive
    assert _bucket_label(-0.5) == "0.0-0.2"  # clamped
    assert _bucket_label(2.0) == "0.8-1.0"   # clamped


# ── Bucket math ────────────────────────────────────────────────────────────


def test_bucket_accuracy_excludes_unclear():
    b = Bucket(label="x", count=4, correct=2, incorrect=1, partial=1, unclear=10)
    assert b.scored == 4
    # (2 + 0.5*1) / 4 = 0.625
    assert b.accuracy == pytest.approx(0.625)


def test_bucket_accuracy_none_when_no_scored():
    b = Bucket(label="x", count=2, unclear=2)
    assert b.scored == 0
    assert b.accuracy is None


# ── produce_report ─────────────────────────────────────────────────────────


def _record(record_id: str, classification: str, confidence: float,
            source_weight: float = 0.6, analyst_weight: float = 0.7) -> dict:
    return {
        "record_id": record_id,
        "pattern": "x",
        "classification": classification,
        "confidence": confidence,
        "source_weight": source_weight,
        "analyst_weight": analyst_weight,
    }


def _verdict(record_id: str, kind: str) -> dict:
    return {"record_id": record_id, "verdict": kind, "reviewer": "alice", "notes": ""}


def test_produce_report_overall_accuracy():
    records = [
        _record("r1", "CORROBORATED", 0.9),
        _record("r2", "MONITOR", 0.4),
        _record("r3", "ESCALATE", 0.85),
    ]
    verdicts = [
        _verdict("r1", "correct"),
        _verdict("r2", "incorrect"),
        _verdict("r3", "partial"),
    ]
    report = produce_report(records, verdicts)
    assert report.total_records == 3
    assert report.total_verdicts == 3
    assert report.matched_verdicts == 3
    assert report.unmatched_verdicts == 0
    # (1 + 0 + 0.5) / 3 ≈ 0.5
    assert report.overall.accuracy == pytest.approx(0.5)


def test_produce_report_unmatched_verdicts_counted_separately():
    records = [_record("r1", "CORROBORATED", 0.9)]
    verdicts = [
        _verdict("r1", "correct"),
        _verdict("ghost", "incorrect"),  # no matching record
    ]
    report = produce_report(records, verdicts)
    assert report.matched_verdicts == 1
    assert report.unmatched_verdicts == 1
    # Unmatched verdicts still update overall counts
    assert report.overall.count == 2
    assert report.overall.correct == 1
    assert report.overall.incorrect == 1
    # But not per-classification (the join fails)
    assert "CORROBORATED" in report.by_classification
    assert report.by_classification["CORROBORATED"].count == 1


def test_produce_report_classification_buckets():
    records = [
        _record("r1", "CORROBORATED", 0.9),
        _record("r2", "CORROBORATED", 0.8),
        _record("r3", "MONITOR", 0.4),
    ]
    verdicts = [
        _verdict("r1", "correct"),
        _verdict("r2", "incorrect"),
        _verdict("r3", "correct"),
    ]
    report = produce_report(records, verdicts)
    cb = report.by_classification
    assert cb["CORROBORATED"].count == 2
    assert cb["CORROBORATED"].correct == 1
    assert cb["CORROBORATED"].incorrect == 1
    assert cb["CORROBORATED"].accuracy == pytest.approx(0.5)
    assert cb["MONITOR"].correct == 1
    assert cb["MONITOR"].accuracy == 1.0


def test_produce_report_confidence_buckets():
    records = [
        _record("r1", "CORROBORATED", 0.95),
        _record("r2", "CORROBORATED", 0.05),
    ]
    verdicts = [
        _verdict("r1", "correct"),
        _verdict("r2", "incorrect"),
    ]
    report = produce_report(records, verdicts)
    assert "0.8-1.0" in report.by_confidence_bucket
    assert "0.0-0.2" in report.by_confidence_bucket
    assert report.by_confidence_bucket["0.8-1.0"].accuracy == 1.0
    assert report.by_confidence_bucket["0.0-0.2"].accuracy == 0.0


def test_produce_report_unclear_does_not_count_toward_accuracy():
    records = [_record("r1", "CORROBORATED", 0.9)]
    verdicts = [_verdict("r1", "unclear")]
    report = produce_report(records, verdicts)
    assert report.overall.unclear == 1
    assert report.overall.accuracy is None
    assert report.by_classification["CORROBORATED"].accuracy is None


def test_produce_report_serializes_to_dict():
    records = [_record("r1", "CORROBORATED", 0.9)]
    verdicts = [_verdict("r1", "correct")]
    d = produce_report(records, verdicts).to_dict()
    assert d["total_records"] == 1
    assert d["total_verdicts"] == 1
    assert d["overall"]["accuracy"] == 1.0
    assert d["by_classification"]["CORROBORATED"]["accuracy"] == 1.0


# ── API endpoint ───────────────────────────────────────────────────────────


@pytest.fixture
def calibrated_client(tmp_path: Path):
    intel = JsonlStore(tmp_path / "intel.jsonl")
    intel.append(_record("r1", "CORROBORATED", 0.9))
    intel.append(_record("r2", "MONITOR", 0.3))

    verdicts = VerdictStore(tmp_path / "verdicts.jsonl")
    verdicts.save(Verdict(verdict_id="v1", record_id="r1", verdict="correct"))
    verdicts.save(Verdict(verdict_id="v2", record_id="r2", verdict="incorrect"))

    app.dependency_overrides[get_intel_store] = lambda: intel
    app.dependency_overrides[get_verdict_store] = lambda: verdicts
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_intel_store, None)
        app.dependency_overrides.pop(get_verdict_store, None)


def test_calibration_report_endpoint(calibrated_client):
    r = calibrated_client.get("/calibration/report")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total_records"] == 2
    assert body["total_verdicts"] == 2
    assert body["matched_verdicts"] == 2
    assert body["overall"]["accuracy"] == 0.5
    assert "CORROBORATED" in body["by_classification"]
    assert body["by_classification"]["CORROBORATED"]["accuracy"] == 1.0


def test_calibration_report_with_no_data(tmp_path: Path):
    intel = JsonlStore(tmp_path / "intel.jsonl")
    verdicts = VerdictStore(tmp_path / "verdicts.jsonl")
    app.dependency_overrides[get_intel_store] = lambda: intel
    app.dependency_overrides[get_verdict_store] = lambda: verdicts
    try:
        c = TestClient(app)
        r = c.get("/calibration/report")
        assert r.status_code == 200
        body = r.json()
        assert body["total_records"] == 0
        assert body["total_verdicts"] == 0
        assert body["overall"]["accuracy"] is None
    finally:
        app.dependency_overrides.pop(get_intel_store, None)
        app.dependency_overrides.pop(get_verdict_store, None)
