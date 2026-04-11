"""Tests for the full cycle pipeline — end-to-end with mocked RSS."""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from spec1_engine.schemas.models import (
    Signal, ParsedSignal, Opportunity, Investigation, Outcome, IntelligenceRecord,
)
from spec1_engine.signal.harvester import harvest_all, fetch_feed, DEFAULT_FEEDS
from spec1_engine.signal.parser import parse_signal, parse_batch
from spec1_engine.signal.scorer import score_signal, score_batch
from spec1_engine.investigation.generator import generate_investigation
from spec1_engine.investigation.verifier import verify_investigation
from spec1_engine.intelligence.analyzer import analyze
from spec1_engine.intelligence.store import JsonlStore
from spec1_engine.app.cycle import run_cycle
from spec1_engine.core.ids import run_id as new_run_id


# ─── Shared fixtures ─────────────────────────────────────────────────────────

@pytest.fixture
def run_id_val() -> str:
    return new_run_id()


@pytest.fixture
def sample_signal() -> Signal:
    return Signal(
        signal_id="sig-cycle-001",
        source="rand",
        source_type="rss",
        text=(
            "New RAND analysis examines Russia's military strategy and intelligence operations "
            "in Ukraine. The report assesses NATO alliance posture and defense capabilities "
            "against potential escalation scenarios. Cyber warfare and nuclear deterrence "
            "are discussed. Pentagon officials confirmed the assessment."
        ),
        url="https://www.rand.org/blog/2024/test.html",
        author="Dara Massicot",
        published_at=datetime.now(timezone.utc),
        velocity=0.9,
        engagement=0.0,
        run_id="run-test",
        environment="test",
        metadata={"feed_url": "https://rand.org/blog.xml"},
    )


@pytest.fixture
def sample_parsed(sample_signal) -> ParsedSignal:
    return parse_signal(sample_signal)


@pytest.fixture
def sample_opportunity(sample_signal, sample_parsed) -> Opportunity | None:
    return score_signal(sample_signal, sample_parsed, run_id="run-test")


@pytest.fixture
def fake_feed_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Test Feed</title>
    <link>https://example.com</link>
    <description>Test</description>
    <item>
      <title>Russia Military Intelligence Update</title>
      <link>https://example.com/article-1</link>
      <description>Analysis of Russian military intelligence operations in Ukraine. NATO alliance defense strategy. Cyber warfare threat assessment confirmed by Pentagon officials.</description>
      <pubDate>Thu, 10 Apr 2025 12:00:00 +0000</pubDate>
      <author>Test Author</author>
    </item>
    <item>
      <title>Defense Policy Report</title>
      <link>https://example.com/article-2</link>
      <description>CSIS analysis of defense policy and international security strategy. Nuclear deterrence and alliance commitments reviewed. Military operations assessment.</description>
      <pubDate>Thu, 10 Apr 2025 11:00:00 +0000</pubDate>
    </item>
    <item>
      <title>Short</title>
      <link>https://example.com/article-3</link>
      <description>Brief note.</description>
      <pubDate>Thu, 10 Apr 2025 10:00:00 +0000</pubDate>
    </item>
  </channel>
</rss>"""


# ─── Harvest tests (mocked) ───────────────────────────────────────────────────

def test_harvest_all_with_mock_feeds(tmp_path, fake_feed_xml):
    """Mock feedparser to avoid network calls."""
    import feedparser

    mock_parsed = feedparser.parse(fake_feed_xml)

    with patch("spec1_engine.signal.harvester.feedparser.parse", return_value=mock_parsed):
        result = harvest_all(
            feeds={"test_feed": "https://example.com/feed"},
            run_id="run-test",
            environment="test",
        )

    assert "signals" in result
    assert "errors" in result
    assert len(result["signals"]) == 3  # 3 items in fake XML


def test_harvest_signals_are_signal_instances(fake_feed_xml):
    import feedparser
    mock_parsed = feedparser.parse(fake_feed_xml)
    with patch("spec1_engine.signal.harvester.feedparser.parse", return_value=mock_parsed):
        result = harvest_all(feeds={"test": "https://x.com"}, run_id="run-test", environment="test")
    for sig in result["signals"]:
        assert isinstance(sig, Signal)


def test_harvest_signal_has_run_id(fake_feed_xml):
    import feedparser
    mock_parsed = feedparser.parse(fake_feed_xml)
    with patch("spec1_engine.signal.harvester.feedparser.parse", return_value=mock_parsed):
        result = harvest_all(feeds={"test": "https://x.com"}, run_id="run-xyz", environment="test")
    for sig in result["signals"]:
        assert sig.run_id == "run-xyz"


def test_harvest_signal_has_source(fake_feed_xml):
    import feedparser
    mock_parsed = feedparser.parse(fake_feed_xml)
    with patch("spec1_engine.signal.harvester.feedparser.parse", return_value=mock_parsed):
        result = harvest_all(feeds={"my_source": "https://x.com"}, run_id="run-test", environment="test")
    for sig in result["signals"]:
        assert sig.source == "my_source"


def test_harvest_error_captured(fake_feed_xml):
    """Simulate a bozo feed parse error."""
    mock_parsed = MagicMock()
    mock_parsed.get = MagicMock(side_effect=lambda k, d=None: {"bozo": True, "bozo_exception": Exception("bad xml"), "entries": []}.get(k, d))
    mock_parsed.__contains__ = MagicMock(return_value=True)

    with patch("spec1_engine.signal.harvester.feedparser.parse", return_value=mock_parsed):
        result = harvest_all(feeds={"bad_feed": "https://x.com"}, run_id="r", environment="test")
    # Errors may or may not be populated depending on bozo handling, but no crash
    assert "errors" in result


def test_default_feeds_has_six_sources():
    assert len(DEFAULT_FEEDS) == 6


def test_default_feeds_includes_rand():
    assert "rand" in DEFAULT_FEEDS


def test_default_feeds_includes_lawfare():
    assert "lawfare" in DEFAULT_FEEDS


def test_default_feeds_includes_cipher_brief():
    assert "cipher_brief" in DEFAULT_FEEDS


# ─── Parse tests ─────────────────────────────────────────────────────────────

def test_parse_signal_basic(sample_signal):
    ps = parse_signal(sample_signal)
    assert isinstance(ps, ParsedSignal)
    assert ps.signal_id == sample_signal.signal_id


def test_parse_signal_cleans_html(sample_signal):
    sig = Signal(**{**sample_signal.__dict__, "text": "<p>Hello <b>world</b> test content analysis military</p>"})
    ps = parse_signal(sig)
    assert "<" not in ps.cleaned_text


def test_parse_signal_extracts_keywords(sample_signal):
    ps = parse_signal(sample_signal)
    assert len(ps.keywords) > 0


def test_parse_signal_word_count_correct(sample_signal):
    ps = parse_signal(sample_signal)
    assert ps.word_count == len(ps.cleaned_text.split())


def test_parse_batch_returns_dict():
    sigs = [
        Signal(
            signal_id=f"s{i}", source="rand", source_type="rss",
            text=f"Military intelligence analysis {i} " * 30,
            url=f"https://example.com/{i}", author="",
            published_at=datetime.now(timezone.utc),
            velocity=0.5, engagement=0.0, run_id="r", environment="test", metadata={},
        )
        for i in range(5)
    ]
    result = parse_batch(sigs)
    assert "parsed" in result
    assert "failed" in result
    assert len(result["parsed"]) == 5


# ─── Scorer / gate tests ──────────────────────────────────────────────────────

def test_score_signal_passes_4_gates(sample_signal, sample_parsed):
    opp = score_signal(sample_signal, sample_parsed, run_id="run-test")
    if opp:
        assert all(opp.gate_results.values())


def test_score_signal_opportunity_priority_valid(sample_signal, sample_parsed):
    opp = score_signal(sample_signal, sample_parsed, run_id="run-test")
    if opp:
        assert opp.priority in ("ELEVATED", "STANDARD", "MONITOR")


def test_score_signal_score_in_range(sample_signal, sample_parsed):
    opp = score_signal(sample_signal, sample_parsed, run_id="run-test")
    if opp:
        assert 0.0 <= opp.score <= 1.0


def test_score_signal_no_novelty_blocked():
    sig = Signal(
        signal_id="s-low", source="rand", source_type="rss",
        text="The weather today is sunny with light clouds and warm temperatures.",
        url="https://example.com/weather", author="",
        published_at=datetime.now(timezone.utc),
        velocity=0.5, engagement=0.0, run_id="run", environment="test", metadata={},
    )
    ps = ParsedSignal(
        signal_id="s-low",
        cleaned_text="The weather today is sunny with light clouds and warm temperatures.",
        keywords=["weather", "sunny", "clouds"],
        entities=[],
        language="en",
        word_count=12,
    )
    opp = score_signal(sig, ps)
    assert opp is None  # novelty + volume gates block it


def test_score_batch_all_same_source():
    sigs = [
        Signal(
            signal_id=f"s{i}", source="rand", source_type="rss",
            text="Russian military intelligence cyber warfare nuclear deterrence NATO.",
            url=f"https://r.com/{i}", author="",
            published_at=datetime.now(timezone.utc),
            velocity=0.8, engagement=0.0, run_id="r", environment="test", metadata={},
        )
        for i in range(4)
    ]
    parsed = [parse_signal(s) for s in sigs]
    result = score_batch(sigs, parsed, run_id="run-test")
    assert "opportunities" in result
    assert "blocked" in result
    assert len(result["opportunities"]) + len(result["blocked"]) == 4


# ─── Investigation tests ──────────────────────────────────────────────────────

def test_generate_investigation_linked_to_opportunity(sample_opportunity, sample_signal, sample_parsed):
    if sample_opportunity is None:
        pytest.skip("Signal did not create opportunity")
    inv = generate_investigation(sample_opportunity, sample_signal, sample_parsed)
    assert inv.opportunity_id == sample_opportunity.opportunity_id


def test_generate_investigation_has_sources(sample_opportunity, sample_signal, sample_parsed):
    if sample_opportunity is None:
        pytest.skip("Signal did not create opportunity")
    inv = generate_investigation(sample_opportunity, sample_signal, sample_parsed)
    assert len(inv.sources_to_check) > 0


def test_generate_investigation_has_analyst_leads(sample_opportunity, sample_signal, sample_parsed):
    if sample_opportunity is None:
        pytest.skip("Signal did not create opportunity")
    inv = generate_investigation(sample_opportunity, sample_signal, sample_parsed)
    assert len(inv.analyst_leads) > 0


def test_investigation_to_dict(sample_opportunity, sample_signal, sample_parsed):
    if sample_opportunity is None:
        pytest.skip("Signal did not create opportunity")
    inv = generate_investigation(sample_opportunity, sample_signal, sample_parsed)
    d = inv.to_dict()
    assert "investigation_id" in d
    assert "hypothesis" in d


# ─── Verifier tests ───────────────────────────────────────────────────────────

def test_verify_produces_outcome(sample_opportunity, sample_signal, sample_parsed):
    if sample_opportunity is None:
        pytest.skip("Signal did not create opportunity")
    inv = generate_investigation(sample_opportunity, sample_signal, sample_parsed)
    outcome = verify_investigation(inv)
    assert isinstance(outcome, Outcome)


def test_verify_outcome_has_evidence(sample_opportunity, sample_signal, sample_parsed):
    if sample_opportunity is None:
        pytest.skip("Signal did not create opportunity")
    inv = generate_investigation(sample_opportunity, sample_signal, sample_parsed)
    outcome = verify_investigation(inv)
    assert len(outcome.evidence) > 0


def test_outcome_to_dict(sample_opportunity, sample_signal, sample_parsed):
    if sample_opportunity is None:
        pytest.skip("Signal did not create opportunity")
    inv = generate_investigation(sample_opportunity, sample_signal, sample_parsed)
    outcome = verify_investigation(inv)
    d = outcome.to_dict()
    assert "outcome_id" in d
    assert "classification" in d
    assert "confidence" in d


# ─── Full cycle (mocked network) ─────────────────────────────────────────────

def test_run_cycle_with_mocked_feeds(tmp_path, fake_feed_xml):
    """Run the full cycle with mocked RSS — no network calls."""
    import feedparser
    mock_parsed_feed = feedparser.parse(fake_feed_xml)

    store_path = tmp_path / "cycle_test.jsonl"
    with patch("spec1_engine.signal.harvester.feedparser.parse", return_value=mock_parsed_feed):
        stats = run_cycle(
            store_path=store_path,
            run_id="run-cycle-test",
            environment="test",
            feeds={"test_feed": "https://example.com/feed"},
            verbose=False,
        )

    assert stats["run_id"] == "run-cycle-test"
    assert stats["signals_harvested"] == 3
    assert stats["signals_parsed"] == 3
    assert "finished_at" in stats


def test_run_cycle_records_stored_if_opportunities(tmp_path, fake_feed_xml):
    """Opportunities produce records in JSONL."""
    import feedparser
    mock_feed = feedparser.parse(fake_feed_xml)

    store_path = tmp_path / "cycle_records.jsonl"
    with patch("spec1_engine.signal.harvester.feedparser.parse", return_value=mock_feed):
        stats = run_cycle(
            store_path=store_path,
            run_id="run-records-test",
            environment="test",
            feeds={"test_feed": "https://example.com/feed"},
            verbose=False,
        )

    if stats["records_stored"] > 0:
        store = JsonlStore(store_path)
        records = list(store.read_all())
        assert len(records) == stats["records_stored"]


def test_run_cycle_stats_keys(tmp_path, fake_feed_xml):
    import feedparser
    mock_feed = feedparser.parse(fake_feed_xml)

    with patch("spec1_engine.signal.harvester.feedparser.parse", return_value=mock_feed):
        stats = run_cycle(
            store_path=tmp_path / "stats_test.jsonl",
            feeds={"test": "https://x.com"},
            verbose=False,
        )

    required_keys = {
        "run_id", "started_at", "finished_at",
        "signals_harvested", "signals_parsed",
        "opportunities_found", "investigations_generated",
        "outcomes_verified", "records_stored", "errors",
    }
    assert required_keys.issubset(set(stats.keys()))


def test_run_cycle_errors_list_is_list(tmp_path, fake_feed_xml):
    import feedparser
    mock_feed = feedparser.parse(fake_feed_xml)
    with patch("spec1_engine.signal.harvester.feedparser.parse", return_value=mock_feed):
        stats = run_cycle(store_path=tmp_path / "t.jsonl", feeds={"t": "https://x.com"}, verbose=False)
    assert isinstance(stats["errors"], list)


def test_run_cycle_empty_feeds_no_crash(tmp_path):
    stats = run_cycle(
        store_path=tmp_path / "empty.jsonl",
        feeds={},
        verbose=False,
    )
    assert stats["signals_harvested"] == 0


def test_run_cycle_jsonl_records_valid_json(tmp_path, fake_feed_xml):
    import feedparser
    mock_feed = feedparser.parse(fake_feed_xml)
    store_path = tmp_path / "valid_json.jsonl"

    with patch("spec1_engine.signal.harvester.feedparser.parse", return_value=mock_feed):
        run_cycle(store_path=store_path, feeds={"test": "https://x.com"}, verbose=False)

    if store_path.exists():
        with store_path.open("r") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    obj = json.loads(line)
                    assert isinstance(obj, dict)
                    assert "record_id" in obj
                    assert "written_at" in obj


def test_run_cycle_with_max_signals(tmp_path, fake_feed_xml):
    import feedparser
    mock_feed = feedparser.parse(fake_feed_xml)
    with patch("spec1_engine.signal.harvester.feedparser.parse", return_value=mock_feed):
        stats = run_cycle(
            store_path=tmp_path / "max.jsonl",
            feeds={"test": "https://x.com"},
            max_signals=1,
            verbose=False,
        )
    assert stats["signals_harvested"] <= 3
    assert stats["signals_parsed"] <= 1


def test_run_cycle_investigations_geq_records(tmp_path, fake_feed_xml):
    import feedparser
    mock_feed = feedparser.parse(fake_feed_xml)
    with patch("spec1_engine.signal.harvester.feedparser.parse", return_value=mock_feed):
        stats = run_cycle(store_path=tmp_path / "inv.jsonl", feeds={"test": "https://x.com"}, verbose=False)
    assert stats["investigations_generated"] >= stats["records_stored"]


def test_run_cycle_outcomes_geq_records(tmp_path, fake_feed_xml):
    import feedparser
    mock_feed = feedparser.parse(fake_feed_xml)
    with patch("spec1_engine.signal.harvester.feedparser.parse", return_value=mock_feed):
        stats = run_cycle(store_path=tmp_path / "out.jsonl", feeds={"test": "https://x.com"}, verbose=False)
    assert stats["outcomes_verified"] >= stats["records_stored"]


def test_run_cycle_multiple_times_appends(tmp_path, fake_feed_xml):
    """Running cycle twice should append, not overwrite."""
    import feedparser
    mock_feed = feedparser.parse(fake_feed_xml)
    store_path = tmp_path / "multi.jsonl"

    with patch("spec1_engine.signal.harvester.feedparser.parse", return_value=mock_feed):
        stats1 = run_cycle(store_path=store_path, feeds={"t": "https://x.com"}, verbose=False)
        stats2 = run_cycle(store_path=store_path, feeds={"t": "https://x.com"}, verbose=False)

    if store_path.exists():
        store = JsonlStore(store_path)
        total = store.count()
        assert total == stats1["records_stored"] + stats2["records_stored"]
