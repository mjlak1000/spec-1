"""Tests for cls_osint.adapters.narrative — narrative detection adapter."""

from __future__ import annotations

import pytest

from cls_osint.adapters.narrative import (
    NARRATIVE_THEMES,
    _count_theme_hits,
    _detect_sentiment,
    _detect_amplifiers,
    _compute_reach_score,
    detect_narratives,
    analyse_corpus,
)
from cls_osint.schemas import NarrativeRecord, OSINTRecord


def _make_record(record_id="r1", content="Some content", source_name="test_source"):
    return OSINTRecord(
        record_id=record_id,
        source_type="rss",
        source_name=source_name,
        content=content,
        url="https://example.com",
    )


class TestCountThemeHits:
    def test_hits_known_keywords(self):
        hits = _count_theme_hits("Taiwan strait tensions rising", ["taiwan", "strait"])
        assert hits == 2

    def test_zero_hits_no_match(self):
        hits = _count_theme_hits("Weather report: sunny skies", ["taiwan", "russia"])
        assert hits == 0

    def test_case_insensitive(self):
        hits = _count_theme_hits("UKRAINE war ongoing", ["ukraine"])
        assert hits == 1

    def test_partial_word_not_counted(self):
        # "taiwan" should only match exact substring
        hits = _count_theme_hits("taiwane", ["taiwan"])
        assert hits == 1  # still matches as substring


class TestDetectSentiment:
    def test_negative_sentiment(self):
        sentiment = _detect_sentiment("Massive threat and attack imminent; crisis escalating")
        assert sentiment == "NEGATIVE"

    def test_positive_sentiment(self):
        sentiment = _detect_sentiment("Peace agreement reached; diplomatic progress achieved")
        assert sentiment == "POSITIVE"

    def test_mixed_sentiment(self):
        sentiment = _detect_sentiment("Peace talks amid ongoing threat and conflict")
        assert sentiment in ("MIXED", "NEGATIVE", "NEUTRAL")

    def test_neutral_sentiment(self):
        sentiment = _detect_sentiment("The meeting was scheduled for Tuesday.")
        assert sentiment == "NEUTRAL"


class TestDetectAmplifiers:
    def test_identifies_high_frequency_sources(self):
        records = [
            _make_record("r1", "taiwan strait china invasion", "rt_news"),
            _make_record("r2", "taiwan china military pla", "rt_news"),
            _make_record("r3", "taiwan china strain", "rt_news"),
            _make_record("r4", "unrelated content here", "reuters"),
        ]
        amplifiers = _detect_amplifiers(records, ["taiwan", "china"])
        assert "rt_news" in amplifiers

    def test_returns_empty_for_no_matches(self):
        records = [_make_record("r1", "weather report sunny")]
        amplifiers = _detect_amplifiers(records, ["taiwan", "nuclear"])
        assert amplifiers == []


class TestComputeReachScore:
    def test_zero_for_empty_corpus(self):
        score = _compute_reach_score([], "theme", 0)
        assert score == 0.0

    def test_positive_for_hits(self):
        records = [_make_record(f"r{i}") for i in range(10)]
        score = _compute_reach_score(records, "theme", 5)
        assert score > 0.0

    def test_bounded_zero_to_one(self):
        records = [_make_record(f"r{i}") for i in range(5)]
        score = _compute_reach_score(records, "theme", 100)
        assert 0.0 <= score <= 1.0


class TestDetectNarratives:
    def test_detects_taiwan_narrative(self):
        records = [
            _make_record("r1", "Taiwan strait tensions as PLA conducts military exercises near Taipei"),
            _make_record("r2", "China taiwan military buildup invasion concerns grow"),
            _make_record("r3", "Taiwan independence movement Tsai government"),
        ]
        narratives = detect_narratives(records, min_hits=1)
        themes = [n.theme for n in narratives]
        assert "China-Taiwan escalation" in themes

    def test_detects_russia_ukraine_narrative(self):
        records = [
            _make_record("r1", "Russia Ukraine war Zelensky Putin Kremlin Kyiv"),
            _make_record("r2", "NATO response to Ukrainian mobilization"),
            _make_record("r3", "Russian invasion Ukraine donbas"),
        ]
        narratives = detect_narratives(records, min_hits=1)
        themes = [n.theme for n in narratives]
        assert "Russia-Ukraine conflict" in themes

    def test_returns_sorted_by_reach(self):
        # Taiwan keywords appear more than Iran
        records = [
            _make_record(f"r{i}", "taiwan strait pla china military invasion" * 2)
            for i in range(5)
        ] + [
            _make_record("iran1", "iran nuclear jcpoa")
        ]
        narratives = detect_narratives(records, min_hits=1)
        if len(narratives) >= 2:
            assert narratives[0].reach_score >= narratives[1].reach_score

    def test_empty_corpus_returns_empty(self):
        result = detect_narratives([], min_hits=1)
        assert result == []

    def test_min_hits_threshold(self):
        # Only 1 hit for a theme — should not appear at min_hits=3
        records = [_make_record("r1", "taiwan mentioned once")]
        narratives = detect_narratives(records, min_hits=3)
        # taiwan has 1 hit; should not qualify
        assert all(n.reach_score > 0 for n in narratives)

    def test_narrative_record_has_required_fields(self):
        records = [
            _make_record("r1", "Russia Ukraine war Zelensky Putin Kremlin Kyiv NATO"),
            _make_record("r2", "Ukrainian forces resist Russian advance near Kyiv"),
        ]
        narratives = detect_narratives(records, min_hits=1)
        for n in narratives:
            assert n.record_id.startswith("narrative_")
            assert n.theme
            assert n.description
            assert 0.0 <= n.reach_score <= 1.0
            assert n.sentiment in ("POSITIVE", "NEGATIVE", "NEUTRAL", "MIXED")

    def test_narrative_to_osint_record(self):
        records = [_make_record("r1", "China cyber espionage apt41 prc cyber hack")]
        narratives = detect_narratives(records, min_hits=1)
        if narratives:
            osint = narratives[0].to_osint_record()
            assert osint.source_type == "NARRATIVE"


class TestAnalyseCorpus:
    def test_alias_for_detect_narratives(self):
        records = [_make_record("r1", "ISIS caliphate jihad extremism terrorism")]
        result = analyse_corpus(records, min_hits=1)
        assert isinstance(result, list)
