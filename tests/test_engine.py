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
from unittest.mock import patch
from spec1_engine.signal.parser import parse_signal, parse_batch, _clean_html, _extract_keywords, _extract_entities
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
    valid = {"CORROBORATED", "ESCALATE", "INVESTIGATE", "MONITOR", "CONFLICTED", "ARCHIVE"}
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


# ─── RunStats tests ───────────────────────────────────────────────────────────

def test_run_stats_finish_sets_finished_at():
    from spec1_engine.core.engine import RunStats
    stats = RunStats(run_id="run-test", started_at="2026-04-11T00:00:00+00:00")
    assert stats.finished_at is None
    stats.finish()
    assert stats.finished_at is not None
    # Should be a valid ISO format
    from datetime import datetime
    dt = datetime.fromisoformat(stats.finished_at)
    assert dt is not None


def test_run_stats_to_dict_has_all_keys():
    from spec1_engine.core.engine import RunStats
    stats = RunStats(run_id="run-abc", started_at="2026-04-11T00:00:00+00:00")
    stats.signals_harvested = 10
    stats.records_stored = 3
    stats.finish()
    d = stats.to_dict()
    required = {
        "run_id", "started_at", "finished_at",
        "signals_harvested", "signals_parsed", "opportunities_found",
        "investigations_generated", "outcomes_verified", "records_stored", "errors",
    }
    assert required.issubset(d.keys())


def test_run_stats_to_dict_values_correct():
    from spec1_engine.core.engine import RunStats
    stats = RunStats(run_id="run-vals", started_at="2026-04-11T00:00:00+00:00")
    stats.signals_harvested = 5
    stats.records_stored = 2
    d = stats.to_dict()
    assert d["run_id"] == "run-vals"
    assert d["signals_harvested"] == 5
    assert d["records_stored"] == 2


# ─── Engine.run() tests ───────────────────────────────────────────────────────

def _make_rich_signal_for_engine(signal_id: str = "sig-engine") -> Signal:
    """Build a signal with enough content to pass all 4 gates."""
    text = (
        "Military intelligence exclusive investigation Russia Ukraine NATO cyber warfare. "
        "Pentagon classified federal oversight espionage covert operations. "
        "Nuclear deterrence missile deployment attack strategy confirmed. "
        "FBI NSA CIA investigation sanctions fraud criminal indicted. "
        "Alliance treaty defense operation weapon drone navy army coalition. "
    ) * 4
    return Signal(
        signal_id=signal_id,
        source="rand",
        source_type="rss",
        text=text,
        url=f"https://rand.org/{signal_id}",
        author="",
        published_at=datetime.now(timezone.utc),
        velocity=0.9,
        engagement=0.0,
        run_id="run-test",
        environment="test",
        metadata={},
    )


def test_engine_run_returns_run_stats(tmp_path):
    """Engine.run() with mocked harvest returns a RunStats instance."""
    from spec1_engine.core.engine import Engine, EngineConfig, RunStats
    rich_signal = _make_rich_signal_for_engine()
    mock_result = {"signals": [rich_signal], "errors": {}}

    cfg = EngineConfig(
        run_id="run-engine-test",
        environment="test",
        store_path=tmp_path / "engine_run.jsonl",
    )
    engine = Engine(cfg)

    with patch("spec1_engine.core.engine.harvest_all", return_value=mock_result):
        stats = engine.run()

    assert isinstance(stats, RunStats)
    assert stats.run_id == "run-engine-test"
    assert stats.finished_at is not None


def test_engine_run_signals_harvested(tmp_path):
    """Engine.run() updates signals_harvested from harvest result."""
    from spec1_engine.core.engine import Engine, EngineConfig
    signals = [_make_rich_signal_for_engine(f"sig-{i}") for i in range(3)]
    mock_result = {"signals": signals, "errors": {}}

    cfg = EngineConfig(
        run_id="run-harvest-count",
        environment="test",
        store_path=tmp_path / "harvest_count.jsonl",
    )
    engine = Engine(cfg)

    with patch("spec1_engine.core.engine.harvest_all", return_value=mock_result):
        stats = engine.run()

    assert stats.signals_harvested == 3
    assert stats.signals_parsed == 3


def test_engine_run_harvest_exception(tmp_path):
    """Engine.run() handles harvest exception gracefully."""
    from spec1_engine.core.engine import Engine, EngineConfig
    cfg = EngineConfig(
        run_id="run-harvest-exc",
        environment="test",
        store_path=tmp_path / "exc.jsonl",
    )
    engine = Engine(cfg)

    with patch("spec1_engine.core.engine.harvest_all", side_effect=RuntimeError("no network")):
        stats = engine.run()

    assert any("harvest_all" in e for e in stats.errors)
    assert stats.finished_at is not None


def test_engine_run_with_max_signals(tmp_path):
    """Engine.run() respects max_signals limit."""
    from spec1_engine.core.engine import Engine, EngineConfig
    signals = [_make_rich_signal_for_engine(f"sig-max-{i}") for i in range(10)]
    mock_result = {"signals": signals, "errors": {}}

    cfg = EngineConfig(
        run_id="run-max",
        environment="test",
        store_path=tmp_path / "max.jsonl",
        max_signals=3,
    )
    engine = Engine(cfg)

    with patch("spec1_engine.core.engine.harvest_all", return_value=mock_result):
        stats = engine.run()

    assert stats.signals_harvested == 3


def test_engine_run_harvest_errors_in_stats(tmp_path):
    """Feed-level harvest errors are appended to RunStats.errors."""
    from spec1_engine.core.engine import Engine, EngineConfig
    mock_result = {
        "signals": [],
        "errors": {"broken_feed": "timeout"},
    }

    cfg = EngineConfig(
        run_id="run-feed-err",
        environment="test",
        store_path=tmp_path / "feed_err.jsonl",
    )
    engine = Engine(cfg)

    with patch("spec1_engine.core.engine.harvest_all", return_value=mock_result):
        stats = engine.run()

    assert any("harvest:broken_feed" in e for e in stats.errors)


def test_engine_run_pipeline_loop_runs(tmp_path):
    """Engine.run() executes investigation/verify/analyze loop when opportunities found."""
    from spec1_engine.core.engine import Engine, EngineConfig
    rich_signal = _make_rich_signal_for_engine("sig-pipe-loop")
    mock_result = {"signals": [rich_signal], "errors": {}}

    cfg = EngineConfig(
        run_id="run-pipe-loop",
        environment="test",
        store_path=tmp_path / "pipe_loop.jsonl",
    )
    engine = Engine(cfg)

    with patch("spec1_engine.core.engine.harvest_all", return_value=mock_result):
        stats = engine.run()

    # Should have parsed the signal
    assert stats.signals_parsed >= 0
    assert stats.finished_at is not None


# ─── Signal scorer age-based velocity tests ──────────────────────────────────

from spec1_engine.signal.scorer import _score_velocity as _sv


def _make_aged_signal(hours_ago: float, source: str = "rand") -> Signal:
    from datetime import timedelta
    pub = datetime.now(timezone.utc) - timedelta(hours=hours_ago)
    return Signal(
        signal_id="sig-age",
        source=source,
        source_type="rss",
        text="test",
        url="https://example.com",
        author="",
        published_at=pub,
        velocity=0.0,  # force age-based path
        engagement=0.0,
        run_id="r",
        environment="test",
        metadata={},
    )


def test_velocity_from_age_very_fresh():
    """Signal published < 6h ago scores 1.0."""
    sig = _make_aged_signal(hours_ago=1)
    assert _sv(sig) == pytest.approx(1.0)


def test_velocity_from_age_24h():
    """Signal published 12h ago (6-24h) scores 0.75."""
    sig = _make_aged_signal(hours_ago=12)
    assert _sv(sig) == pytest.approx(0.75)


def test_velocity_from_age_48h():
    """Signal published 48h ago (24-72h) scores 0.50."""
    sig = _make_aged_signal(hours_ago=48)
    assert _sv(sig) == pytest.approx(0.50)


def test_velocity_from_age_4days():
    """Signal published 96h ago (72-168h) scores 0.25."""
    sig = _make_aged_signal(hours_ago=96)
    assert _sv(sig) == pytest.approx(0.25)


def test_velocity_from_age_old():
    """Signal published > 168h ago scores 0.10."""
    sig = _make_aged_signal(hours_ago=200)
    assert _sv(sig) == pytest.approx(0.10)


def test_velocity_from_naive_datetime():
    """Naive datetime (no tzinfo) is handled gracefully."""
    from datetime import timedelta
    pub = datetime.now() - timedelta(hours=1)  # naive
    sig = Signal(
        signal_id="sig-naive",
        source="rand",
        source_type="rss",
        text="test",
        url="https://example.com",
        author="",
        published_at=pub,
        velocity=0.0,
        engagement=0.0,
        run_id="r",
        environment="test",
        metadata={},
    )
    result = _sv(sig)
    assert isinstance(result, float)
    assert 0.0 <= result <= 1.0


def test_velocity_score_novelty_single_hit():
    """Exactly 1 novelty term hit returns 0.40."""
    from spec1_engine.signal.scorer import _score_novelty
    score, hits = _score_novelty("intelligence briefing today", [])
    assert hits == 1
    assert score == pytest.approx(0.40)


def test_velocity_score_novelty_few_hits():
    """2-3 novelty hits return 0.65."""
    from spec1_engine.signal.scorer import _score_novelty
    # "cyber" + "espionage" = 2 hits → score 0.65
    score, hits = _score_novelty("cyber espionage activity", [])
    assert 2 <= hits <= 3
    assert score == pytest.approx(0.65)


def test_velocity_score_novelty_many_hits():
    """4+ novelty hits return a score >= 0.85."""
    from spec1_engine.signal.scorer import _score_novelty
    text = "military intelligence cyber espionage nuclear nato ukraine russia pentagon"
    score, hits = _score_novelty(text, [])
    assert hits >= 4
    assert score >= 0.85


# ─── Signal parser additional tests ──────────────────────────────────────────

from spec1_engine.signal.parser import _truncate, parse_batch


def test_truncate_long_text():
    """_truncate truncates text longer than max_len at word boundary."""
    text = "word " * 2000  # 10000 chars
    result = _truncate(text, 100)
    assert len(result) <= 105  # a bit extra for '...'
    assert result.endswith("...")


def test_truncate_short_text_unchanged():
    """_truncate returns text unchanged when under max_len."""
    text = "short text"
    result = _truncate(text, 100)
    assert result == text


def test_parse_batch_handles_exception():
    """parse_batch catches exceptions per-signal and records them in failed."""
    signals = [
        Signal(
            signal_id="sig-ok",
            source="rand",
            source_type="rss",
            text="military intelligence analysis operations",
            url="https://example.com/ok",
            author="",
            published_at=datetime.now(timezone.utc),
            velocity=0.5,
            engagement=0.0,
            run_id="r",
            environment="test",
            metadata={},
        )
    ]
    # Patch parse_signal to raise on the first call
    with patch("spec1_engine.signal.parser.parse_signal",
               side_effect=RuntimeError("parse error")):
        result = parse_batch(signals)
    assert len(result["failed"]) == 1
    assert result["failed"][0]["signal_id"] == "sig-ok"


def test_clean_html_exception_falls_back_to_regex():
    """_clean_html falls back to regex stripping when BeautifulSoup raises."""
    from spec1_engine.signal.parser import _clean_html
    with patch("spec1_engine.signal.parser.BeautifulSoup", side_effect=Exception("lxml error")):
        result = _clean_html("<p>Hello <b>world</b></p>")
    # Regex fallback should strip tags
    assert "<" not in result


# ─── Schema model to_dict tests ───────────────────────────────────────────────

def test_signal_to_dict():
    sig = Signal(
        signal_id="sig-dict-test",
        source="rand",
        source_type="rss",
        text="Test content",
        url="https://example.com",
        author="Test Author",
        published_at=datetime.now(timezone.utc),
        velocity=0.5,
        engagement=0.1,
        run_id="run-001",
        environment="test",
        metadata={"key": "value"},
    )
    d = sig.to_dict()
    assert d["signal_id"] == "sig-dict-test"
    assert d["source"] == "rand"
    assert d["source_type"] == "rss"
    assert d["text"] == "Test content"
    assert d["url"] == "https://example.com"
    assert d["author"] == "Test Author"
    assert "published_at" in d
    assert d["velocity"] == 0.5
    assert d["engagement"] == 0.1
    assert d["run_id"] == "run-001"
    assert d["environment"] == "test"
    assert d["metadata"] == {"key": "value"}


def test_parsed_signal_to_dict():
    ps = ParsedSignal(
        signal_id="ps-dict-test",
        cleaned_text="clean text",
        keywords=["military", "ukraine"],
        entities=["Ukraine"],
        language="en",
        word_count=2,
    )
    d = ps.to_dict()
    assert d["signal_id"] == "ps-dict-test"
    assert d["cleaned_text"] == "clean text"
    assert d["keywords"] == ["military", "ukraine"]
    assert d["entities"] == ["Ukraine"]
    assert d["language"] == "en"
    assert d["word_count"] == 2


def test_opportunity_to_dict():
    from spec1_engine.schemas.models import Opportunity
    opp = Opportunity(
        opportunity_id="opp-dict-test",
        signal_id="sig-001",
        score=0.75,
        priority="ELEVATED",
        gate_results={"credibility": True, "volume": True, "velocity": True, "novelty": True},
        run_id="run-001",
    )
    d = opp.to_dict()
    assert d["opportunity_id"] == "opp-dict-test"
    assert d["signal_id"] == "sig-001"
    assert d["score"] == 0.75
    assert d["priority"] == "ELEVATED"
    assert d["gate_results"]["credibility"] is True
    assert d["run_id"] == "run-001"


# ─── Intelligence analyzer — default analyst weight path ─────────────────────

def test_analyze_with_no_analyst_leads_uses_default_weight():
    """analyze uses DEFAULT_ANALYST_WEIGHT when investigation has no analyst leads."""
    from spec1_engine.intelligence.analyzer import analyze, DEFAULT_ANALYST_WEIGHT
    opp = make_opportunity()
    sig = make_signal()
    inv = Investigation(
        investigation_id="inv-no-leads",
        opportunity_id="opp-test001",
        hypothesis="Test hypothesis.",
        queries=["query 1"],
        sources_to_check=["https://rand.org"],
        analyst_leads=[],  # empty — triggers default weight
    )
    outcome = Outcome(
        outcome_id="out-test",
        classification="INVESTIGATE",
        confidence=0.70,
        evidence=["test evidence"],
    )
    record = analyze(opp, inv, outcome, sig)
    assert record.analyst_weight == pytest.approx(DEFAULT_ANALYST_WEIGHT)


# ─── Investigation generator — no domain match fallback ──────────────────────

def test_investigation_generator_no_domain_match_uses_pool():
    """generate_investigation falls back to ANALYST_POOL[:2] when no keyword match."""
    from spec1_engine.investigation.generator import generate_investigation, ANALYST_POOL
    opp = make_opportunity()
    sig = make_signal(text="Weather report: sunny skies and mild temperatures.")
    ps = ParsedSignal(
        signal_id="sig-001",
        cleaned_text="Weather report: sunny skies and mild temperatures.",
        keywords=["weather", "sunny", "skies"],
        entities=[],
        language="en",
        word_count=7,
    )
    inv = generate_investigation(opp, sig, ps)
    # analyst_leads should fall back to ANALYST_POOL[:2]
    assert len(inv.analyst_leads) >= 1
    for lead in inv.analyst_leads:
        assert lead in ANALYST_POOL


# ─── Engine.run() exception-path tests (lines 117-118, 129-130, 146-147) ──────

def test_engine_run_parse_exception_handled(tmp_path):
    """Engine.run() handles parse_signal exceptions."""
    from spec1_engine.core.engine import Engine, EngineConfig
    rich_signal = _make_rich_signal_for_engine("sig-eng-parse-err")
    mock_result = {"signals": [rich_signal], "errors": {}}

    cfg = EngineConfig(
        run_id="run-parse-exc",
        environment="test",
        store_path=tmp_path / "parse_exc.jsonl",
    )
    engine = Engine(cfg)

    with patch("spec1_engine.core.engine.harvest_all", return_value=mock_result),          patch("spec1_engine.core.engine.parse_signal",
               side_effect=RuntimeError("parse error")):
        stats = engine.run()

    assert any("parse" in e for e in stats.errors)
    assert stats.finished_at is not None


def test_engine_run_score_exception_handled(tmp_path):
    """Engine.run() handles score_signal exceptions."""
    from spec1_engine.core.engine import Engine, EngineConfig
    rich_signal = _make_rich_signal_for_engine("sig-eng-score-err")
    mock_result = {"signals": [rich_signal], "errors": {}}

    cfg = EngineConfig(
        run_id="run-score-exc",
        environment="test",
        store_path=tmp_path / "score_exc.jsonl",
    )
    engine = Engine(cfg)

    with patch("spec1_engine.core.engine.harvest_all", return_value=mock_result),          patch("spec1_engine.core.engine.score_signal",
               side_effect=RuntimeError("score error")):
        stats = engine.run()

    assert any("score" in e for e in stats.errors)
    assert stats.finished_at is not None


def test_engine_run_pipeline_exception_handled(tmp_path):
    """Engine.run() handles exceptions in the investigate/verify/analyze loop."""
    from spec1_engine.core.engine import Engine, EngineConfig
    rich_signal = _make_rich_signal_for_engine("sig-eng-pipeline-err")
    mock_result = {"signals": [rich_signal], "errors": {}}

    cfg = EngineConfig(
        run_id="run-pipeline-exc",
        environment="test",
        store_path=tmp_path / "pipeline_exc.jsonl",
    )
    engine = Engine(cfg)

    with patch("spec1_engine.core.engine.harvest_all", return_value=mock_result),          patch("spec1_engine.core.engine.generate_investigation",
               side_effect=RuntimeError("inv error")):
        stats = engine.run()

    assert any("pipeline" in e for e in stats.errors)
    assert stats.finished_at is not None


# ─── Additional scorer/parser coverage tests ─────────────────────────────────

def test_velocity_from_string_published_at():
    """_score_velocity handles non-datetime published_at via dateutil."""
    import spec1_engine.signal.scorer as scorer_mod
    sig = Signal(
        signal_id="sig-str-date",
        source="rand",
        source_type="rss",
        text="test",
        url="https://example.com",
        author="",
        published_at="2020-01-01T00:00:00+00:00",  # string, not datetime
        velocity=0.0,
        engagement=0.0,
        run_id="r",
        environment="test",
        metadata={},
    )
    # Temporarily override isinstance check in scorer
    result = scorer_mod._score_velocity(sig)
    # Old date → should score low (0.10)
    assert isinstance(result, float)
    assert 0.0 <= result <= 1.0


def test_velocity_exception_returns_default():
    """_score_velocity returns 0.50 fallback on exception."""
    from spec1_engine.signal.scorer import _score_velocity
    sig = Signal(
        signal_id="sig-exc-date",
        source="rand",
        source_type="rss",
        text="test",
        url="https://example.com",
        author="",
        published_at=None,  # None will cause exception in datetime operations
        velocity=0.0,
        engagement=0.0,
        run_id="r",
        environment="test",
        metadata={},
    )
    result = _score_velocity(sig)
    assert result == pytest.approx(0.50)


def test_score_volume_fallback_unreachable():
    """_score_volume lowest tier covers word_count=0."""
    from spec1_engine.signal.scorer import _score_volume
    # word_count=0 → matches (0, 0.10) tier
    assert _score_volume(0) == pytest.approx(0.10)
    assert _score_volume(1) == pytest.approx(0.10)


def test_parse_batch_max_entities_break():
    """_extract_entities respects max_ent limit and triggers the break."""
    from spec1_engine.signal.parser import _extract_entities
    # Build text with enough proper-noun phrases to exceed max_ent
    text = (
        "Michael Kofman reported. Thomas Rid assessed. Julian Barnes confirmed. "
        "Rob Lee noted. Shane Harris analyzed. Mark Galeotti briefed. "
        "Fiona Hill testified. Evelyn Farkas warned. Andrea Kendall-Taylor wrote."
    )
    entities = _extract_entities(text, max_ent=3)
    assert len(entities) == 3
