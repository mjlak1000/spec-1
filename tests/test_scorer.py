"""Tests for cls_psyop/scorer.py — psyop pattern scoring."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from spec1_engine.cls_psyop.scorer import (
    NARRATIVE_CLUSTER,
    FARA_ACTIVE,
    MODEL_LEGISLATION,
    CONSENSUS_SPIKE,
    NO_ORGANIC_ORIGIN,
    REQUIRED_FIELDS,
    THRESHOLD_CANDIDATE,
    THRESHOLD_CONFIRMED,
    score_psyop,
)


# ─── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def base_signal() -> dict:
    """Minimal signal that fires no patterns — all checks evaluate to False."""
    return {
        "topic": "test-topic",
        "entities": ["EntityA"],
        "sources": ["source_a"],
        "fara_matches": [],             # empty → FARA_ACTIVE = False
        "legislation_matches": [],      # empty → MODEL_LEGISLATION = False
        "narrative_markets": ["mkt1", "mkt2"],  # only 2 → NARRATIVE_CLUSTER = False
        "consensus_velocity": 0.0,     # zero → CONSENSUS_SPIKE = False
        "origin_traceable": True,      # traceable → NO_ORGANIC_ORIGIN = False
    }


@pytest.fixture
def store_path(tmp_path: Path) -> Path:
    return tmp_path / "psyop_signals.jsonl"


# ─── Individual pattern tests ─────────────────────────────────────────────────

def test_narrative_cluster_fires_at_three_markets(base_signal, store_path):
    """NARRATIVE_CLUSTER fires when narrative_markets has 3+ entries."""
    sig = {**base_signal, "narrative_markets": ["mkt1", "mkt2", "mkt3"]}
    result = score_psyop(sig, store_path=store_path)
    assert "NARRATIVE_CLUSTER" in result["patterns_fired"]
    assert result["score"] == 2


def test_narrative_cluster_does_not_fire_at_two_markets(base_signal, store_path):
    """NARRATIVE_CLUSTER requires 3+ markets; 2 is not enough."""
    result = score_psyop(base_signal, store_path=store_path)
    assert "NARRATIVE_CLUSTER" not in result["patterns_fired"]


def test_fara_active_fires_on_non_empty_list(base_signal, store_path):
    """FARA_ACTIVE fires when fara_matches is a non-empty list."""
    sig = {**base_signal, "fara_matches": ["FARA-Registrant-Corp"]}
    result = score_psyop(sig, store_path=store_path)
    assert "FARA_ACTIVE" in result["patterns_fired"]
    assert result["score"] == 2


def test_fara_active_fires_on_bool_true(base_signal, store_path):
    """FARA_ACTIVE fires when fara_matches is boolean True."""
    sig = {**base_signal, "fara_matches": True}
    result = score_psyop(sig, store_path=store_path)
    assert "FARA_ACTIVE" in result["patterns_fired"]


def test_fara_active_does_not_fire_on_empty_list(base_signal, store_path):
    """FARA_ACTIVE does not fire when fara_matches is an empty list."""
    result = score_psyop(base_signal, store_path=store_path)
    assert "FARA_ACTIVE" not in result["patterns_fired"]


def test_fara_active_does_not_fire_on_bool_false(base_signal, store_path):
    """FARA_ACTIVE does not fire when fara_matches is boolean False."""
    sig = {**base_signal, "fara_matches": False}
    result = score_psyop(sig, store_path=store_path)
    assert "FARA_ACTIVE" not in result["patterns_fired"]


def test_model_legislation_fires_on_non_empty_list(base_signal, store_path):
    """MODEL_LEGISLATION fires when legislation_matches is non-empty."""
    sig = {**base_signal, "legislation_matches": ["HB-101", "SB-202"]}
    result = score_psyop(sig, store_path=store_path)
    assert "MODEL_LEGISLATION" in result["patterns_fired"]
    assert result["score"] == 3


def test_model_legislation_fires_on_bool_true(base_signal, store_path):
    """MODEL_LEGISLATION fires when legislation_matches is boolean True."""
    sig = {**base_signal, "legislation_matches": True}
    result = score_psyop(sig, store_path=store_path)
    assert "MODEL_LEGISLATION" in result["patterns_fired"]


def test_model_legislation_does_not_fire_on_empty_list(base_signal, store_path):
    """MODEL_LEGISLATION does not fire when legislation_matches is empty."""
    result = score_psyop(base_signal, store_path=store_path)
    assert "MODEL_LEGISLATION" not in result["patterns_fired"]


def test_consensus_spike_fires_on_positive_velocity(base_signal, store_path):
    """CONSENSUS_SPIKE fires when consensus_velocity > 0.0."""
    sig = {**base_signal, "consensus_velocity": 0.75}
    result = score_psyop(sig, store_path=store_path)
    assert "CONSENSUS_SPIKE" in result["patterns_fired"]
    assert result["score"] == 1


def test_consensus_spike_does_not_fire_at_zero(base_signal, store_path):
    """CONSENSUS_SPIKE does not fire when consensus_velocity == 0.0."""
    result = score_psyop(base_signal, store_path=store_path)
    assert "CONSENSUS_SPIKE" not in result["patterns_fired"]


def test_consensus_spike_does_not_fire_on_none(base_signal, store_path):
    """CONSENSUS_SPIKE does not fire when consensus_velocity is None."""
    sig = {**base_signal, "consensus_velocity": None}
    result = score_psyop(sig, store_path=store_path)
    assert "CONSENSUS_SPIKE" not in result["patterns_fired"]


def test_no_organic_origin_fires_when_not_traceable(base_signal, store_path):
    """NO_ORGANIC_ORIGIN fires when origin_traceable is falsy."""
    sig = {**base_signal, "origin_traceable": False}
    result = score_psyop(sig, store_path=store_path)
    assert "NO_ORGANIC_ORIGIN" in result["patterns_fired"]
    assert result["score"] == 2


def test_no_organic_origin_fires_on_none(base_signal, store_path):
    """NO_ORGANIC_ORIGIN fires when origin_traceable is None."""
    sig = {**base_signal, "origin_traceable": None}
    result = score_psyop(sig, store_path=store_path)
    assert "NO_ORGANIC_ORIGIN" in result["patterns_fired"]


def test_no_organic_origin_does_not_fire_when_traceable(base_signal, store_path):
    """NO_ORGANIC_ORIGIN does not fire when origin_traceable is truthy."""
    result = score_psyop(base_signal, store_path=store_path)
    assert "NO_ORGANIC_ORIGIN" not in result["patterns_fired"]


# ─── Threshold boundary tests ─────────────────────────────────────────────────

def test_score_zero_is_clean(base_signal, store_path):
    """A signal firing no patterns scores 0 and classifies as CLEAN."""
    result = score_psyop(base_signal, store_path=store_path)
    assert result["score"] == 0
    assert result["classification"] == "CLEAN"


def test_score_4_is_noise(store_path):
    """Score 4 (FARA_ACTIVE + NO_ORGANIC_ORIGIN) is still NOISE (< 5)."""
    sig = {
        "topic": "boundary-test",
        "entities": [],
        "sources": ["s"],
        "fara_matches": True,              # +2
        "legislation_matches": [],
        "narrative_markets": ["m1", "m2"],
        "consensus_velocity": 0.0,
        "origin_traceable": False,          # +2
    }
    result = score_psyop(sig, store_path=store_path)
    assert result["score"] == 4
    assert result["classification"] == "NOISE"


def test_score_5_is_psyop_candidate(store_path):
    """Score 5 (NARRATIVE_CLUSTER + MODEL_LEGISLATION) is PSYOP_CANDIDATE."""
    sig = {
        "topic": "boundary-test",
        "entities": [],
        "sources": ["s"],
        "fara_matches": [],
        "legislation_matches": True,        # +3
        "narrative_markets": ["m1", "m2", "m3"],  # +2
        "consensus_velocity": 0.0,
        "origin_traceable": True,
    }
    result = score_psyop(sig, store_path=store_path)
    assert result["score"] == 5
    assert result["classification"] == "PSYOP_CANDIDATE"


def test_score_7_is_psyop_candidate(store_path):
    """Score 7 is PSYOP_CANDIDATE (>= 5 but < 8)."""
    sig = {
        "topic": "boundary-test",
        "entities": [],
        "sources": ["s"],
        "fara_matches": True,               # +2
        "legislation_matches": True,        # +3
        "narrative_markets": ["m1", "m2"],
        "consensus_velocity": 0.0,
        "origin_traceable": False,          # +2
    }
    result = score_psyop(sig, store_path=store_path)
    assert result["score"] == 7
    assert result["classification"] == "PSYOP_CANDIDATE"


def test_score_8_is_psyop_confirmed(store_path):
    """Score 8 (NARRATIVE_CLUSTER + FARA_ACTIVE + MODEL_LEGISLATION + CONSENSUS_SPIKE) is PSYOP_CONFIRMED."""
    sig = {
        "topic": "confirmed-test",
        "entities": [],
        "sources": ["s"],
        "fara_matches": True,               # +2
        "legislation_matches": True,        # +3
        "narrative_markets": ["m1", "m2", "m3"],  # +2
        "consensus_velocity": 0.5,          # +1
        "origin_traceable": True,
    }
    result = score_psyop(sig, store_path=store_path)
    assert result["score"] == 8
    assert result["classification"] == "PSYOP_CONFIRMED"


def test_score_10_max_all_patterns(store_path):
    """Score 10 when all five patterns fire; classification is PSYOP_CONFIRMED."""
    sig = {
        "topic": "all-patterns",
        "entities": ["EntityX"],
        "sources": ["s1", "s2", "s3"],
        "fara_matches": ["RegistrantA"],    # +2
        "legislation_matches": ["HB-1"],   # +3
        "narrative_markets": ["m1", "m2", "m3"],  # +2
        "consensus_velocity": 1.0,         # +1
        "origin_traceable": False,         # +2
    }
    result = score_psyop(sig, store_path=store_path)
    assert result["score"] == 10
    assert result["classification"] == "PSYOP_CONFIRMED"
    assert len(result["patterns_fired"]) == 5


# ─── Combined scoring tests ───────────────────────────────────────────────────

def test_multiple_patterns_accumulate_score(store_path):
    """Score is the sum of all fired pattern weights."""
    sig = {
        "topic": "multi-pattern",
        "entities": [],
        "sources": ["s"],
        "fara_matches": ["reg-1"],          # +2
        "legislation_matches": [],
        "narrative_markets": ["m1", "m2", "m3"],  # +2
        "consensus_velocity": 0.5,          # +1
        "origin_traceable": True,
    }
    result = score_psyop(sig, store_path=store_path)
    assert result["score"] == 2 + 2 + 1
    assert set(result["patterns_fired"]) == {
        "NARRATIVE_CLUSTER", "FARA_ACTIVE", "CONSENSUS_SPIKE"
    }


def test_patterns_fired_order_is_consistent(store_path):
    """patterns_fired list follows the declared check order."""
    sig = {
        "topic": "order-test",
        "entities": [],
        "sources": ["s"],
        "fara_matches": True,
        "legislation_matches": True,
        "narrative_markets": ["m1", "m2", "m3"],
        "consensus_velocity": 0.9,
        "origin_traceable": False,
    }
    result = score_psyop(sig, store_path=store_path)
    expected_order = [
        "NARRATIVE_CLUSTER",
        "FARA_ACTIVE",
        "MODEL_LEGISLATION",
        "CONSENSUS_SPIKE",
        "NO_ORGANIC_ORIGIN",
    ]
    assert result["patterns_fired"] == expected_order


def test_empty_patterns_fired_when_no_match(base_signal, store_path):
    """patterns_fired is an empty list when no pattern fires."""
    result = score_psyop(base_signal, store_path=store_path)
    assert result["patterns_fired"] == []


# ─── Output schema tests ──────────────────────────────────────────────────────

def test_result_contains_all_required_output_fields(base_signal, store_path):
    """Result dict contains exactly the six specified output fields."""
    result = score_psyop(base_signal, run_id="run-test-001", store_path=store_path)
    for field in ("topic", "score", "classification", "patterns_fired", "timestamp", "run_id"):
        assert field in result, f"Missing field: {field}"


def test_topic_passthrough(base_signal, store_path):
    """topic in result matches topic in input signal."""
    result = score_psyop(base_signal, store_path=store_path)
    assert result["topic"] == base_signal["topic"]


def test_run_id_passthrough(base_signal, store_path):
    """run_id in result matches the run_id argument."""
    result = score_psyop(base_signal, run_id="run-abc123", store_path=store_path)
    assert result["run_id"] == "run-abc123"


def test_timestamp_is_iso_format(base_signal, store_path):
    """timestamp in result is a valid ISO 8601 string."""
    from datetime import datetime
    result = score_psyop(base_signal, store_path=store_path)
    dt = datetime.fromisoformat(result["timestamp"])
    assert dt is not None


# ─── JSONL output tests ───────────────────────────────────────────────────────

def test_result_written_to_jsonl(base_signal, store_path):
    """score_psyop appends a record to the JSONL store."""
    assert not store_path.exists()
    score_psyop(base_signal, store_path=store_path)
    assert store_path.exists()
    lines = [l for l in store_path.read_text().splitlines() if l.strip()]
    assert len(lines) == 1


def test_jsonl_record_is_valid_json(base_signal, store_path):
    """Each JSONL line is valid JSON."""
    score_psyop(base_signal, store_path=store_path)
    for line in store_path.read_text().splitlines():
        if line.strip():
            obj = json.loads(line)
            assert isinstance(obj, dict)


def test_jsonl_record_contains_output_fields(base_signal, store_path):
    """JSONL record contains all six output fields."""
    score_psyop(base_signal, run_id="run-x", store_path=store_path)
    record = json.loads(store_path.read_text().strip())
    for field in ("topic", "score", "classification", "patterns_fired", "timestamp", "run_id"):
        assert field in record


def test_jsonl_append_does_not_overwrite(base_signal, store_path):
    """Multiple calls append; previous records are not overwritten."""
    score_psyop({**base_signal, "topic": "first"}, store_path=store_path)
    score_psyop({**base_signal, "topic": "second"}, store_path=store_path)
    lines = [l for l in store_path.read_text().splitlines() if l.strip()]
    assert len(lines) == 2
    topics = [json.loads(l)["topic"] for l in lines]
    assert "first" in topics
    assert "second" in topics


def test_jsonl_parent_dir_created_if_missing(base_signal, tmp_path):
    """JSONL parent directory is created automatically if it does not exist."""
    deep_path = tmp_path / "deep" / "nested" / "psyop.jsonl"
    score_psyop(base_signal, store_path=deep_path)
    assert deep_path.exists()


# ─── Failure-first tests ──────────────────────────────────────────────────────

def test_raises_type_error_on_non_dict(store_path):
    """score_psyop raises TypeError when signal is not a dict."""
    with pytest.raises(TypeError, match="signal must be dict"):
        score_psyop("not a dict", store_path=store_path)


def test_raises_type_error_on_list(store_path):
    """score_psyop raises TypeError when signal is a list."""
    with pytest.raises(TypeError):
        score_psyop(["topic", "value"], store_path=store_path)


def test_raises_type_error_on_none(store_path):
    """score_psyop raises TypeError when signal is None."""
    with pytest.raises(TypeError):
        score_psyop(None, store_path=store_path)


def test_raises_value_error_on_missing_all_fields(store_path):
    """score_psyop raises ValueError when signal is an empty dict."""
    with pytest.raises(ValueError, match="missing required fields"):
        score_psyop({}, store_path=store_path)


def test_raises_value_error_on_single_missing_field(base_signal, store_path):
    """score_psyop raises ValueError when exactly one required field is absent."""
    for field in REQUIRED_FIELDS:
        incomplete = {k: v for k, v in base_signal.items() if k != field}
        with pytest.raises(ValueError, match="missing required fields"):
            score_psyop(incomplete, store_path=store_path)


def test_no_jsonl_written_on_validation_failure(store_path):
    """JSONL store is not written when validation raises."""
    with pytest.raises(TypeError):
        score_psyop("bad input", store_path=store_path)
    assert not store_path.exists()


# ─── Narrative market edge cases ──────────────────────────────────────────────

def test_narrative_cluster_fires_on_set(base_signal, store_path):
    """NARRATIVE_CLUSTER fires when narrative_markets is a set with 3+ elements."""
    sig = {**base_signal, "narrative_markets": {"m1", "m2", "m3"}}
    result = score_psyop(sig, store_path=store_path)
    assert "NARRATIVE_CLUSTER" in result["patterns_fired"]


def test_narrative_cluster_does_not_fire_on_non_sequence(base_signal, store_path):
    """NARRATIVE_CLUSTER does not fire when narrative_markets is not a sequence."""
    sig = {**base_signal, "narrative_markets": "three-markets-string"}
    result = score_psyop(sig, store_path=store_path)
    assert "NARRATIVE_CLUSTER" not in result["patterns_fired"]
