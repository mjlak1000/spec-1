"""Tests for the calibration proposer, formatter, CLI, and /calibration/proposals."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from cls_calibration.aggregator import produce_report
from cls_calibration.formatter import to_markdown
from cls_calibration.proposer import (
    CLASSIFICATION_WEIGHTS,
    _bucket_midpoint,
    _severity,
    propose_adjustments,
)
from cls_calibration.schemas import (
    Bucket,
    CalibrationReport,
    ProposalReport,
)
from cls_verdicts.schemas import Verdict
from cls_verdicts.store import VerdictStore
from spec1_api.dependencies import get_intel_store, get_verdict_store
from spec1_api.main import app
from spec1_engine.intelligence.store import JsonlStore


# ── helpers ────────────────────────────────────────────────────────────────


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


# ── unit-level helpers ─────────────────────────────────────────────────────


def test_bucket_midpoint_parses_label():
    assert _bucket_midpoint("0.0-0.2") == pytest.approx(0.1)
    assert _bucket_midpoint("0.8-1.0") == pytest.approx(0.9)
    assert _bucket_midpoint("not-a-bucket") is None
    assert _bucket_midpoint("") is None


def test_severity_thresholds():
    # Small: |delta| < 0.10 OR sample size < 10
    assert _severity(0.05, 100) == "small"
    assert _severity(0.50, 5) == "small"
    # Moderate: |delta| in [0.10, 0.25) and sample >= 10
    assert _severity(0.15, 12) == "moderate"
    assert _severity(-0.20, 30) == "moderate"
    # Large: |delta| >= 0.25 and sample >= 10
    assert _severity(0.30, 10) == "large"
    assert _severity(-0.50, 100) == "large"


# ── propose_adjustments ────────────────────────────────────────────────────


def _build_report(by_classification=None, by_confidence=None) -> CalibrationReport:
    rep = CalibrationReport(generated_at="2026-04-25T00:00:00+00:00")
    rep.by_classification = by_classification or {}
    rep.by_confidence_bucket = by_confidence or {}
    return rep


def test_proposer_skips_buckets_below_sample_floor():
    rep = _build_report(by_classification={
        "CORROBORATED": Bucket(label="CORROBORATED", count=3, correct=0, incorrect=3, partial=0),
    })
    out = propose_adjustments(rep, sample_floor=5, delta_floor=0.10)
    assert out.adjustments == []


def test_proposer_skips_buckets_below_delta_floor():
    # CORROBORATED expected = 1.0; observed = 0.95 → delta = -0.05 < 0.15 floor
    rep = _build_report(by_classification={
        "CORROBORATED": Bucket(label="CORROBORATED", count=20, correct=19, incorrect=1, partial=0),
    })
    out = propose_adjustments(rep, sample_floor=5, delta_floor=0.15)
    assert out.adjustments == []


def test_proposer_emits_classification_drift():
    # CORROBORATED expected 1.0; observed 0.5 (10 correct of 20) → delta = -0.5
    rep = _build_report(by_classification={
        "CORROBORATED": Bucket(label="CORROBORATED", count=20, correct=10, incorrect=10, partial=0),
    })
    out = propose_adjustments(rep, sample_floor=5, delta_floor=0.15)
    assert len(out.adjustments) == 1
    a = out.adjustments[0]
    assert a.target_kind == "classification"
    assert a.target_id == "CORROBORATED"
    assert a.expected == 1.0
    assert a.observed == 0.5
    assert a.delta == pytest.approx(-0.5)
    assert a.severity == "large"
    assert "overconfident" in a.rationale


def test_proposer_emits_confidence_bucket_drift():
    # bucket 0.8-1.0 (mid 0.9); observed 0.5 → delta = -0.4
    rep = _build_report(by_confidence={
        "0.8-1.0": Bucket(label="0.8-1.0", count=20, correct=10, incorrect=10),
    })
    out = propose_adjustments(rep, sample_floor=5, delta_floor=0.15)
    assert len(out.adjustments) == 1
    a = out.adjustments[0]
    assert a.target_kind == "confidence_bucket"
    assert a.target_id == "0.8-1.0"
    assert a.expected == pytest.approx(0.9)


def test_proposer_skips_classifications_without_known_weight():
    rep = _build_report(by_classification={
        "MYSTERIOUS": Bucket(label="MYSTERIOUS", count=20, correct=0, incorrect=20),
    })
    out = propose_adjustments(rep, sample_floor=5, delta_floor=0.15)
    assert out.adjustments == []


def test_proposer_sorts_largest_delta_first():
    rep = _build_report(by_classification={
        "CORROBORATED": Bucket(label="CORROBORATED", count=20, correct=10, incorrect=10),  # delta -0.5
        "ESCALATE": Bucket(label="ESCALATE", count=20, correct=14, incorrect=6),          # delta -0.15
    })
    out = propose_adjustments(rep, sample_floor=5, delta_floor=0.10)
    assert [a.target_id for a in out.adjustments] == ["CORROBORATED", "ESCALATE"]


def test_proposer_includes_floors_in_output():
    rep = _build_report()
    out = propose_adjustments(rep, sample_floor=7, delta_floor=0.22)
    assert out.sample_floor == 7
    assert out.delta_floor == pytest.approx(0.22)


def test_classification_weights_match_analyzer():
    """Sanity check — the proposer's weight table must agree with analyzer.py."""
    from spec1_engine.intelligence.analyzer import (
        CLASSIFICATION_WEIGHTS as ANALYZER_WEIGHTS,
    )
    assert CLASSIFICATION_WEIGHTS == ANALYZER_WEIGHTS


# ── formatter ──────────────────────────────────────────────────────────────


def test_formatter_renders_empty_report():
    rep = ProposalReport(
        generated_at="2026-04-25T00:00:00+00:00",
        sample_floor=5,
        delta_floor=0.15,
    )
    md = to_markdown(rep)
    assert "# SPEC-1 Calibration Proposal" in md
    assert "No drift signals" in md


def test_formatter_groups_by_severity():
    rep = ProposalReport(
        generated_at="2026-04-25T00:00:00+00:00",
        sample_floor=5,
        delta_floor=0.15,
        adjustments=[],
    )
    cal = _build_report(by_classification={
        "CORROBORATED": Bucket(label="CORROBORATED", count=20, correct=10, incorrect=10),
        "ESCALATE": Bucket(label="ESCALATE", count=20, correct=14, incorrect=6),
    })
    rep = propose_adjustments(cal, sample_floor=5, delta_floor=0.10)
    md = to_markdown(rep)
    assert "Large drift" in md
    assert "Moderate drift" in md
    assert "CORROBORATED" in md
    assert "ESCALATE" in md
    assert "| target_kind |" in md  # table header
    assert "Apply changes by editing" in md  # governance pointer


# ── CLI ────────────────────────────────────────────────────────────────────


def test_cli_writes_markdown_and_jsonl(tmp_path: Path):
    intel = tmp_path / "intel.jsonl"
    verdicts = tmp_path / "verdicts.jsonl"
    intel.write_text("\n".join(json.dumps(_record(f"r{i}", "CORROBORATED", 0.9))
                               for i in range(10)) + "\n", encoding="utf-8")
    verdicts.write_text("\n".join(json.dumps(_verdict(f"r{i}",
                                  "correct" if i < 4 else "incorrect"))
                                  for i in range(10)) + "\n", encoding="utf-8")
    out_dir = tmp_path / "out"

    result = subprocess.run(
        [sys.executable, "-m", "spec1_engine.tools.calibration_propose",
         "--intel", str(intel),
         "--verdicts", str(verdicts),
         "--out-dir", str(out_dir),
         "--sample-floor", "5",
         "--delta-floor", "0.15"],
        capture_output=True, text=True, timeout=20,
    )
    assert result.returncode == 0, result.stderr

    md = out_dir / "calibration_report.md"
    audit = out_dir / "calibration_report.jsonl"
    assert md.exists()
    assert audit.exists()

    text = md.read_text(encoding="utf-8")
    assert "CORROBORATED" in text  # 4/10 = 0.4 vs expected 1.0 → large drift

    audit_entry = json.loads(audit.read_text(encoding="utf-8").splitlines()[-1])
    assert audit_entry["calibration"]["total_records"] == 10
    assert audit_entry["calibration"]["total_verdicts"] == 10
    assert len(audit_entry["proposal"]["adjustments"]) >= 1


def test_cli_help_returns_zero():
    result = subprocess.run(
        [sys.executable, "-m", "spec1_engine.tools.calibration_propose", "--help"],
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0
    assert "--intel" in result.stdout
    assert "--out-dir" in result.stdout


# ── /calibration/proposals endpoint ────────────────────────────────────────


def test_proposals_endpoint(tmp_path: Path):
    intel = JsonlStore(tmp_path / "intel.jsonl")
    for i in range(20):
        intel.append(_record(f"r{i}", "CORROBORATED", 0.9))

    verdicts = VerdictStore(tmp_path / "verdicts.jsonl")
    for i in range(20):
        verdicts.save(Verdict(
            verdict_id=f"v{i}",
            record_id=f"r{i}",
            verdict="correct" if i < 8 else "incorrect",  # 8/20 → 0.4 vs 1.0 expected
        ))

    app.dependency_overrides[get_intel_store] = lambda: intel
    app.dependency_overrides[get_verdict_store] = lambda: verdicts
    try:
        c = TestClient(app)
        r = c.get("/calibration/proposals")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["sample_floor"] == 5
        assert body["delta_floor"] == 0.15
        kinds = [a["target_kind"] for a in body["adjustments"]]
        assert "classification" in kinds
        assert any(a["target_id"] == "CORROBORATED" for a in body["adjustments"])

        # Tighten the floors and verify they get echoed back
        r2 = c.get("/calibration/proposals", params={"sample_floor": 100, "delta_floor": 0.9})
        assert r2.status_code == 200
        assert r2.json()["adjustments"] == []
    finally:
        app.dependency_overrides.pop(get_intel_store, None)
        app.dependency_overrides.pop(get_verdict_store, None)
