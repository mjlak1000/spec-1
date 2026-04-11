"""Tests for core engine — pipeline logic, gate scoring, IDs."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest

from spec1_engine.core.ids import (
    new_uuid,
    deterministic_id,
    run_id,
    signal_id,
    opportunity_id,
    investigation_id,
    outcome_id,
    record_id,
)
from spec1_engine.core.engine import Engine, EngineConfig
from spec1_engine.schemas.models import (
    Signal,
    ParsedSignal,
    Opportunity,
    Investigation,
    Outcome,
    IntelligenceRecord,
)
from spec1_engine.signal.parser import parse_signal, _clean_html, _extract_keywords, _extract_entities
from spec1_engine.signal.scorer import (
    score_signal,
    score_batch,
    _score_credibility,
    _score_volume,
    _score_velocity,
    _score_novelty,
    _priority,
    SOURCE_CREDIBILITY,
)
from spec1_engine.investigation.generator import generate_investigation
from spec1_engine.investigation.verifier import verify_investigation
from spec1_engine.intelligence.analyzer import analyze


# ─── Helpers ─────────────────────────────────────────────────────────────────

def make_signal(
    source: str = "rand",
    author: str = "",
    text: str = "",
    velocity: float = 0.5,
    signal_id_val: str = "sig-001",
) -> Signal:
    return Signal(
        signal_id=signal_id_val,
        source=source,
        source_type="rss",
        text=text or "Military intelligence analysis of Russian armed forces deployment in Ukraine region. NATO alliance response expected.",
        url="https://example.com/test",
        author=author,
        published_at=datetime.now(timezone.utc),
        velocity=velocity,
        engagement=0.0,
        run_id="run-test",
        environment="test",
        metadata={},
    )


def make_parsed(
    word_count: int = 120,
    keywords: list[str] | None = None,
    cleaned_text: str = "",
) -> ParsedSignal:
    text = cleaned_text or "Military intelligence analysis of Russian armed forces deployment in Ukraine. NATO coalition response expected. Defense strategy."
    return ParsedSignal(
        signal_id="sig-001",
        cleaned_text=text,
        keywords=keywords or ["military", "intelligence", "russia", "ukraine", "nato", "defense"],
        entities=["Ukraine", "NATO", "Russia"],
        language="en",
        word_count=word_count,
    )


def make_opportunity(signal_id: str = "sig-001") -> Opportunity:
    return Opportunity(
        opportunity_id="opp-test001",
        signal_id=signal_id,
        score=0.72,
        priority="ELEVATED",
        gate_results={
            "credibility": True,
            "volume": True,
            "velocity": True,
            "novelty": True,
        },
        run_id="run-test",
    )


# ─── ID generation ────────────────────────────────────────────────────────────

def test_new_uuid_is_valid():
    uid = new_uuid()
    parsed = uuid.UUID(uid)
    assert str(parsed) == uid


def test_deterministic_id_is_16_chars():
    did = deterministic_id("test-content")
    assert len(did) == 16


def test_deterministic_id_is_stable():
    assert deterministic_id("abc") == deterministic_id("abc")


def test_deterministic_id_differs_for_different_input():
    assert deterministic_id("abc") != deterministic_id("xyz")


def test_run_id_format():
    rid = run_id()
    assert rid.startswith("run-")


def test_run_id_unique():
    ids = {run_id() for _ in range(10)}
    assert len(ids) == 10


def test_signal_id_deterministic():
    sid1 = signal_id("https://example.com/a", "Title A")
    sid2 = signal_id("https://example.com/a", "Title A")
    assert sid1 == sid2


def test_signal_id_different_for_different_inputs():
    sid1 = signal_id("https://example.com/a", "Title A")
    sid2 = signal_id("https://example.com/b", "Title B")
    assert sid1 != sid2


def test_opportunity_id_format():
    oid = opportunity_id("sig-001")
    assert oid.startswith("opp-")


def test_investigation_id_format():
    iid = investigation_id()
    assert iid.startswith("inv-")


def test_outcome_id_format():
    oid = outcome_id()
    assert oid.startswith("out-")


def test_record_id_format():
    rid = record_id()
    assert rid.startswith("rec-")


# ─── Parser tests ─────────────────────────────────────────────────────────────

def test_clean_html_removes_tags():
    result = _clean_html("<p>Hello <b>world</b></p>")
    assert "<" not in result
    assert "Hello" in result
    assert "world" in result


def test_clean_html_handles_empty():
    assert _clean_html("") == ""


def test_clean_html_plain_text_unchanged():
    result = _clean_html("plain text here")
    assert "plain text here" in result


def test_extract_keywords_filters_stopwords():
    kws = _extract_keywords("the analysis of military intelligence operations")
    assert "the" not in kws
    assert "of" not in kws
    assert "military" in kws or "intelligence" in kws


def test_extract_keywords_max_count():
    text = "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu nu xi omicron"
    kws = _extract_keywords(text, max_kw=5)
    assert len(kws) <= 5


def test_extract_entities_finds_proper_nouns():
    entities = _extract_entities("Ukraine and Russia signed a ceasefire. NATO responded.")
    assert len(entities) >= 1


def test_parse_signal_returns_parsed_signal():
    sig = make_signal()
    ps = parse_signal(sig)
    assert isinstance(ps, ParsedSignal)
    assert ps.signal_id == sig.signal_id


def test_parse_signal_word_count_positive():
    sig = make_signal(text="This is a test with several words in the content here.")
    ps = parse_signal(sig)
    assert ps.word_count > 0


def test_parse_signal_language_is_en():
    sig = make_signal()
    ps = parse_signal(sig)
    assert ps.language == "en"


def test_parse_signal_keywords_is_list():
    sig = make_signal()
    ps = parse_signal(sig)
    assert isinstance(ps.keywords, list)


def test_parse_signal_entities_is_list():
    sig = make_signal()
    ps = parse_signal(sig)
    assert isinstance(ps.entities, list)


# ─── Scorer / Gate tests ──────────────────────────────────────────────────────

def test_score_credibility_known_source():
    assert _score_credibility("rand") == pytest.approx(0.90)


def test_score_credibility_unknown_source():
    score = _score_credibility("unknown_source_xyz")
    assert score == 0.60


def test_score_credibility_all_known_sources():
    for source in SOURCE_CREDIBILITY:
        score = _score_credibility(source)
        assert 0 < score <= 1.0


def test_score_volume_high_word_count():
    assert _score_volume(600) == 1.0


def test_score_volume_medium_word_count():
    assert _score_volume(300) >= 0.5


def test_score_volume_low_word_count():
    assert _score_volume(10) <= 0.30


def test_score_velocity_from_signal():
    sig = make_signal(velocity=0.8)
    v = _score_velocity(sig)
    assert v == pytest.approx(0.8)


def test_score_velocity_fresh_signal():
    sig = make_signal(velocity=0.0)
    # Published now — should be fresh
    v = _score_velocity(sig)
    assert v >= 0.5


def test_score_novelty_with_intel_term():
    score, hits = _score_novelty("military intelligence operations in ukraine", ["military", "ukraine"])
    assert hits >= 1
    assert score > 0


def test_score_novelty_no_terms():
    score, hits = _score_novelty("the quick brown fox jumps over the lazy dog", [])
    assert hits == 0
    assert score == 0.0


def test_priority_elevated():
    assert _priority(0.80) == "ELEVATED"


def test_priority_standard():
    assert _priority(0.60) == "STANDARD"


def test_priority_monitor():
    assert _priority(0.40) == "MONITOR"


def test_score_signal_all_gates_pass_returns_opportunity():
    sig = make_signal(source="rand")
    ps = make_parsed(word_count=200)
    opp = score_signal(sig, ps, run_id="run-001")
    assert opp is not None
    assert isinstance(opp, Opportunity)


def test_score_signal_low_word_count_blocked():
    sig = make_signal(source="rand")
    ps = make_parsed(word_count=5, keywords=[], cleaned_text="short text")
    opp = score_signal(sig, ps, run_id="run-001")
    # Should be blocked (volume gate or novelty gate fails)
    assert opp is None


def test_score_signal_opportunity_has_all_4_gates():
    sig = make_signal(source="rand")
    ps = make_parsed(word_count=200)
    opp = score_signal(sig, ps)
    if opp is not None:
        assert "credibility" in opp.gate_results
        assert "volume" in opp.gate_results
        assert "velocity" in opp.gate_results
        assert "novelty" in opp.gate_results


def test_score_signal_opportunity_id_format():
    sig = make_signal(source="rand")
    ps = make_parsed(word_count=200)
    opp = score_signal(sig, ps, run_id="run-test")
    if opp:
        assert opp.opportunity_id.startswith("opp-")


def test_score_batch_returns_dict():
    signals = [make_signal(source="rand") for _ in range(3)]
    parsed = [make_parsed(word_count=200) for _ in range(3)]
    result = score_batch(signals, parsed, run_id="run-test")
    assert "opportunities" in result
    assert "blocked" in result


# ─── Engine initialization ───────────────────────────────────────────────────

def test_engine_config_has_run_id():
    cfg = EngineConfig()
    assert cfg.run_id.startswith("run-")


def test_engine_config_default_environment():
    cfg = EngineConfig()
    assert cfg.environment == "production"


def test_engine_init_custom_config(tmp_path):
    cfg = EngineConfig(
        run_id="run-custom-001",
        environment="test",
        store_path=tmp_path / "test.jsonl",
    )
    engine = Engine(cfg)
    assert engine.config.run_id == "run-custom-001"
    assert engine.config.environment == "test"


def test_engine_default_init(tmp_path):
    cfg = EngineConfig(store_path=tmp_path / "engine_test.jsonl")
    engine = Engine(cfg)
    assert engine is not None
    assert engine.store is not None


# ─── Investigation + Verify + Analyze ────────────────────────────────────────

def test_generate_investigation_returns_investigation():
    opp = make_opportunity()
    sig = make_signal()
    ps = make_parsed()
    inv = generate_investigation(opp, sig, ps)
    assert isinstance(inv, Investigation)
    assert inv.investigation_id.startswith("inv-")


def test_generate_investigation_has_hypothesis():
    opp = make_opportunity()
    sig = make_signal()
    ps = make_parsed()
    inv = generate_investigation(opp, sig, ps)
    assert len(inv.hypothesis) > 20


def test_generate_investigation_has_queries():
    opp = make_opportunity()
    sig = make_signal()
    ps = make_parsed()
    inv = generate_investigation(opp, sig, ps)
    assert isinstance(inv.queries, list)
    assert len(inv.queries) > 0


def test_verify_investigation_returns_outcome():
    opp = make_opportunity()
    sig = make_signal()
    ps = make_parsed()
    inv = generate_investigation(opp, sig, ps)
    outcome = verify_investigation(inv)
    assert isinstance(outcome, Outcome)


def test_verify_outcome_confidence_range():
    opp = make_opportunity()
    sig = make_signal()
    ps = make_parsed()
    inv = generate_investigation(opp, sig, ps)
    outcome = verify_investigation(inv)
    assert 0.0 <= outcome.confidence <= 1.0


def test_verify_outcome_valid_classification():
    valid = {"Corroborated", "Escalate", "Investigate", "Monitor", "Conflicted", "Archive"}
    opp = make_opportunity()
    sig = make_signal()
    ps = make_parsed()
    inv = generate_investigation(opp, sig, ps)
    outcome = verify_investigation(inv)
    assert outcome.classification in valid


def test_analyze_returns_intelligence_record():
    opp = make_opportunity()
    sig = make_signal()
    ps = make_parsed()
    inv = generate_investigation(opp, sig, ps)
    outcome = verify_investigation(inv)
    record = analyze(opp, inv, outcome, sig)
    assert isinstance(record, IntelligenceRecord)
    assert record.record_id.startswith("rec-")


def test_analyze_record_confidence_range():
    opp = make_opportunity()
    sig = make_signal()
    ps = make_parsed()
    inv = generate_investigation(opp, sig, ps)
    outcome = verify_investigation(inv)
    record = analyze(opp, inv, outcome, sig)
    assert 0.0 <= record.confidence <= 1.0


def test_record_to_dict_complete():
    opp = make_opportunity()
    sig = make_signal()
    ps = make_parsed()
    inv = generate_investigation(opp, sig, ps)
    outcome = verify_investigation(inv)
    record = analyze(opp, inv, outcome, sig)
    d = record.to_dict()
    assert "record_id" in d
    assert "pattern" in d
    assert "classification" in d
    assert "confidence" in d
    assert "source_weight" in d
    assert "analyst_weight" in d
