"""
Tests for the core engine and individual loop components.
"""

import os
import pytest
from spec1_engine.core.engine import OSINTEngine
from spec1_engine.core import ids
from spec1_engine.schemas.models import Signal, OUTCOME_CLASSES
from spec1_engine.signal.scorer import SignalScorer, VELOCITY_FLOOR, VOLUME_FLOOR
from spec1_engine.signal.harvester import OSINTHarvester


# ── IDs ───────────────────────────────────────────────────────────────────────

def test_run_id_format():
    rid = ids.run_id("osint")
    assert rid.startswith("osint:")
    assert len(rid) > 10


def test_signal_id_is_deterministic():
    sid1 = ids.signal_id("war_on_the_rocks", "some signal text here")
    sid2 = ids.signal_id("war_on_the_rocks", "some signal text here")
    assert sid1 == sid2


def test_signal_id_differs_by_source():
    sid1 = ids.signal_id("war_on_the_rocks", "same text")
    sid2 = ids.signal_id("cipher_brief", "same text")
    assert sid1 != sid2


# ── Harvester ─────────────────────────────────────────────────────────────────

def test_harvester_returns_signals():
    h = OSINTHarvester()
    signals = h.collect(run_id="osint:2026-01-01")
    assert len(signals) > 0


def test_harvester_signals_have_run_id():
    h = OSINTHarvester()
    signals = h.collect(run_id="osint:test")
    for s in signals:
        assert s.run_id == "osint:test"


def test_harvester_signals_have_valid_source_types():
    h = OSINTHarvester()
    valid_types = {"publication", "think_tank", "journalist", "platform"}
    for s in h.collect():
        assert s.source_type in valid_types


# ── Scorer ────────────────────────────────────────────────────────────────────

def test_high_credibility_signal_passes_gates():
    scorer = SignalScorer()
    signal = Signal(
        signal_id="test_sig_001",
        source="war_on_the_rocks",
        source_type="publication",
        text="Test signal from trusted source.",
        velocity=0.80,
        engagement=0.75,
    )
    opp = scorer.score(signal)
    assert opp is not None
    assert opp.score > 0


def test_unknown_source_is_rejected():
    scorer = SignalScorer()
    signal = Signal(
        signal_id="test_sig_002",
        source="unknown_random_blog",
        source_type="unknown",
        text="Unverified claim.",
        velocity=0.90,
        engagement=0.90,
    )
    opp = scorer.score(signal)
    assert opp is None


def test_low_velocity_signal_is_rejected():
    scorer = SignalScorer()
    signal = Signal(
        signal_id="test_sig_003",
        source="war_on_the_rocks",
        source_type="publication",
        text="Old stale signal.",
        velocity=0.20,
        engagement=0.80,
    )
    opp = scorer.score(signal)
    assert opp is None


def test_opportunity_priority_bands():
    scorer = SignalScorer()
    signal = Signal(
        signal_id="test_sig_004",
        source="cipher_brief",
        source_type="publication",
        text="High velocity cyber signal.",
        velocity=0.95,
        engagement=0.90,
    )
    opp = scorer.score(signal)
    assert opp is not None
    assert opp.priority == "ELEVATED"


# ── Engine ────────────────────────────────────────────────────────────────────

def test_engine_run_cycle_returns_result():
    engine = OSINTEngine()
    h = OSINTHarvester()
    signals = h.collect(run_id=engine.run_id)
    assert len(signals) > 0
    result = engine.run_cycle(signals[0])
    assert result.status in ("ok", "filtered", "failed")


def test_engine_batch_handles_mixed_signals():
    engine = OSINTEngine()
    h = OSINTHarvester()
    signals = h.collect(run_id=engine.run_id)
    results = engine.run_batch(signals)
    assert len(results) == len(signals)


def test_engine_ok_results_have_full_chain():
    engine = OSINTEngine()
    h = OSINTHarvester()
    signals = h.collect(run_id=engine.run_id)
    results = engine.run_batch(signals)
    for r in results:
        if r.status == "ok":
            assert r.opportunity is not None
            assert r.investigation is not None
            assert r.outcome is not None
            assert r.intelligence is not None


def test_engine_outcome_classifications_are_valid():
    engine = OSINTEngine()
    h = OSINTHarvester()
    signals = h.collect(run_id=engine.run_id)
    results = engine.run_batch(signals)
    for r in results:
        if r.outcome:
            assert r.outcome.classification in OUTCOME_CLASSES


# ── Boundary conditions ───────────────────────────────────────────────────────

def _sig(signal_id, velocity, engagement, source="war_on_the_rocks"):
    return Signal(
        signal_id=signal_id,
        source=source,
        source_type="publication",
        text="Boundary test signal.",
        velocity=velocity,
        engagement=engagement,
    )


def test_velocity_at_floor_passes():
    scorer = SignalScorer()
    opp = scorer.score(_sig("vel_at_floor", velocity=VELOCITY_FLOOR, engagement=0.50))
    assert opp is not None


def test_velocity_below_floor_rejected():
    scorer = SignalScorer()
    opp = scorer.score(_sig("vel_below_floor", velocity=round(VELOCITY_FLOOR - 0.01, 4), engagement=0.50))
    assert opp is None


def test_engagement_at_floor_passes():
    scorer = SignalScorer()
    opp = scorer.score(_sig("eng_at_floor", velocity=0.60, engagement=VOLUME_FLOOR))
    assert opp is not None


def test_engagement_below_floor_rejected():
    scorer = SignalScorer()
    opp = scorer.score(_sig("eng_below_floor", velocity=0.60, engagement=round(VOLUME_FLOOR - 0.01, 4)))
    assert opp is None


def test_signal_with_none_author_does_not_crash():
    engine = OSINTEngine()
    sig = Signal(
        signal_id="no_author_test",
        source="war_on_the_rocks",
        source_type="publication",
        text="Signal with no author.",
        velocity=0.80,
        engagement=0.70,
        author=None,
    )
    result = engine.run_cycle(sig)
    assert result.status in ("ok", "filtered", "failed", "halted")


def test_signal_with_empty_metadata_does_not_crash():
    engine = OSINTEngine()
    sig = Signal(
        signal_id="empty_meta_test",
        source="war_on_the_rocks",
        source_type="publication",
        text="Signal with empty metadata.",
        velocity=0.80,
        engagement=0.70,
        metadata={},
    )
    result = engine.run_cycle(sig)
    assert result.status in ("ok", "filtered", "failed", "halted")


def test_engine_batch_failed_results_are_included():
    """Exceptions in run_cycle must produce a CycleResult(status='failed'), not be swallowed."""
    engine = OSINTEngine()
    # Inject a signal whose scoring will raise by patching the scorer
    original_score = engine._scorer.score

    def boom(signal):
        raise RuntimeError("injected failure")

    engine._scorer.score = boom
    sig = Signal(
        signal_id="fail_test",
        source="war_on_the_rocks",
        source_type="publication",
        text="This signal will cause a failure.",
        velocity=0.80,
        engagement=0.70,
    )
    results = engine.run_batch([sig])
    assert len(results) == 1
    assert results[0].status == "failed"
    assert "injected failure" in results[0].notes
    engine._scorer.score = original_score


def test_kill_switch_halts_batch(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    kill_file = tmp_path / ".cls_kill"
    kill_file.touch()

    engine = OSINTEngine()
    h = OSINTHarvester()
    signals = h.collect(run_id=engine.run_id)
    results = engine.run_batch(signals)
    # Kill switch is active from the start so no cycles should run
    assert results == []


def test_kill_switch_halts_run_cycle(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    kill_file = tmp_path / ".cls_kill"
    kill_file.touch()

    engine = OSINTEngine()
    sig = Signal(
        signal_id="kill_test",
        source="war_on_the_rocks",
        source_type="publication",
        text="Should be halted.",
        velocity=0.80,
        engagement=0.70,
    )
    result = engine.run_cycle(sig)
    assert result.status == "halted"
