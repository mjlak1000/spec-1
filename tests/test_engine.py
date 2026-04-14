"""
Tests for the core engine and individual loop components.
"""

import pytest
from spec1_engine.core.engine import OSINTEngine
from spec1_engine.core import ids
from spec1_engine.schemas.models import Signal, OUTCOME_CLASSES
from spec1_engine.signal.scorer import SignalScorer
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
