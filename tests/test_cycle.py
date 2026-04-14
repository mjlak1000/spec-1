"""
Tests for one full end-to-end OSINT cycle.
"""

import pytest
from spec1_engine.app.cycle import run_cycle
from spec1_engine.core.engine import OSINTEngine
from spec1_engine.signal.harvester import OSINTHarvester
from spec1_engine.schemas.models import OUTCOME_CLASSES


def test_cycle_runs_without_error():
    results = run_cycle()
    assert len(results) > 0


def test_cycle_produces_ok_results():
    results = run_cycle()
    ok = [r for r in results if r.status == "ok"]
    assert len(ok) > 0, "Expected at least one signal to pass all gates"


def test_all_outcomes_are_valid_classifications():
    results = run_cycle()
    for r in results:
        if r.outcome:
            assert r.outcome.classification in OUTCOME_CLASSES, (
                f"Unknown classification: {r.outcome.classification}"
            )


def test_run_id_propagates_through_cycle():
    engine    = OSINTEngine()
    harvester = OSINTHarvester()
    signals   = harvester.collect(run_id=engine.run_id)
    results   = engine.run_batch(signals)
    for r in results:
        assert r.signal.run_id == engine.run_id
        if r.outcome:
            assert r.outcome.run_id == engine.run_id
        if r.intelligence:
            assert r.intelligence.run_id == engine.run_id


def test_intelligence_stored_for_ok_results():
    results = run_cycle()
    for r in results:
        if r.status == "ok":
            assert r.intelligence is not None
            assert r.intelligence.record_id.startswith("intel_")
