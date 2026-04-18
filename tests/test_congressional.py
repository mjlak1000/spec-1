"""Tests for spec1_engine.congressional — mock all HTTP calls."""

from __future__ import annotations

import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ─── Fixtures ─────────────────────────────────────────────────────────────────

def _days_ago(n: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=n)).strftime("%Y-%m-%d")


@pytest.fixture
def sample_raw_trade() -> dict:
    return {
        "politician": "Sen. Alice Test",
        "ticker": "LMT",
        "amount": 50000,
        "trade_type": "Purchase",
        "trade_date": _days_ago(3),
        "committee": "Armed Services",
        "source": "quiver",
    }


@pytest.fixture
def old_raw_trade() -> dict:
    return {
        "politician": "Rep. Bob Old",
        "ticker": "PANW",
        "amount": 300000,
        "trade_type": "Purchase",
        "trade_date": _days_ago(45),   # outside 30-day recency gate
        "committee": "Intelligence",
        "source": "capitol_trades",
    }


@pytest.fixture
def store_path(tmp_path: Path) -> Path:
    return tmp_path / "congressional_test.jsonl"


# ═══════════════════════════════════════════════════════════════════════════════
# collector.py
# ═══════════════════════════════════════════════════════════════════════════════

class TestParseAmount:
    def test_plain_integer(self):
        from spec1_engine.congressional.collector import _parse_amount
        assert _parse_amount("15001") == 15001

    def test_currency_with_commas(self):
        from spec1_engine.congressional.collector import _parse_amount
        assert _parse_amount("$50,000") == 50000

    def test_range_returns_midpoint(self):
        from spec1_engine.congressional.collector import _parse_amount
        result = _parse_amount("$1,001 - $15,000")
        assert result == (1001 + 15000) // 2

    def test_empty_string_returns_zero(self):
        from spec1_engine.congressional.collector import _parse_amount
        assert _parse_amount("") == 0

    def test_non_numeric_returns_zero(self):
        from spec1_engine.congressional.collector import _parse_amount
        assert _parse_amount("N/A") == 0


class TestFetchQuiver:
    def test_raises_when_api_key_missing(self):
        from spec1_engine.congressional.collector import _fetch_quiver
        with patch.dict("os.environ", {}, clear=True):
            # Remove QUIVER_API_KEY if present
            import os
            os.environ.pop("QUIVER_API_KEY", None)
            with pytest.raises(EnvironmentError, match="QUIVER_API_KEY"):
                _fetch_quiver()

    def test_returns_normalized_records(self):
        from spec1_engine.congressional.collector import _fetch_quiver
        mock_data = [
            {
                "Representative": "Sen. Test",
                "Ticker": "lmt",
                "Amount": "50000",
                "Transaction": "Purchase",
                "TransactionDate": "2026-04-10",
                "Committee": "Armed Services",
            }
        ]
        mock_resp = MagicMock()
        mock_resp.json.return_value = mock_data
        mock_resp.raise_for_status = MagicMock()

        with patch.dict("os.environ", {"QUIVER_API_KEY": "test-key"}):
            with patch("requests.get", return_value=mock_resp):
                result = _fetch_quiver()

        assert len(result) == 1
        assert result[0]["ticker"] == "LMT"
        assert result[0]["source"] == "quiver"
        assert result[0]["politician"] == "Sen. Test"

    def test_http_error_propagates(self):
        import requests as req
        from spec1_engine.congressional.collector import _fetch_quiver
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = req.HTTPError("403")
        with patch.dict("os.environ", {"QUIVER_API_KEY": "key"}):
            with patch("requests.get", return_value=mock_resp):
                with pytest.raises(req.HTTPError):
                    _fetch_quiver()


class TestFetchCapitolTrades:
    def test_parses_html_table(self):
        from spec1_engine.congressional.collector import _fetch_capitol_trades
        html = """
        <table>
          <tr><th>Politician</th><th>Ticker</th><th>Amount</th><th>Type</th><th>Date</th><th>Committee</th></tr>
          <tr>
            <td>Sen. Alice</td><td>lmt</td><td>$50,000</td>
            <td>Purchase</td><td>2026-04-10</td><td>Armed Services</td>
          </tr>
        </table>"""
        mock_resp = MagicMock()
        mock_resp.text = html
        mock_resp.raise_for_status = MagicMock()
        with patch("requests.get", return_value=mock_resp):
            result = _fetch_capitol_trades()
        assert len(result) == 1
        assert result[0]["ticker"] == "LMT"
        assert result[0]["source"] == "capitol_trades"

    def test_skips_incomplete_rows(self):
        from spec1_engine.congressional.collector import _fetch_capitol_trades
        html = "<table><tr><td>only one cell</td></tr></table>"
        mock_resp = MagicMock()
        mock_resp.text = html
        mock_resp.raise_for_status = MagicMock()
        with patch("requests.get", return_value=mock_resp):
            result = _fetch_capitol_trades()
        assert result == []

    def test_http_error_propagates(self):
        import requests as req
        from spec1_engine.congressional.collector import _fetch_capitol_trades
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = req.HTTPError("503")
        with patch("requests.get", return_value=mock_resp):
            with pytest.raises(req.HTTPError):
                _fetch_capitol_trades()


class TestFetchTrades:
    def test_returns_quiver_when_successful(self):
        from spec1_engine.congressional.collector import fetch_trades
        mock_data = [{"Representative": "Sen. X", "Ticker": "RTX",
                      "Amount": "25000", "Transaction": "Purchase",
                      "TransactionDate": "2026-04-10", "Committee": "Armed Services"}]
        mock_resp = MagicMock()
        mock_resp.json.return_value = mock_data
        mock_resp.raise_for_status = MagicMock()
        with patch.dict("os.environ", {"QUIVER_API_KEY": "key"}):
            with patch("requests.get", return_value=mock_resp):
                result = fetch_trades()
        assert len(result) == 1
        assert result[0]["source"] == "quiver"

    def test_falls_back_to_capitol_trades_on_quiver_error(self):
        from spec1_engine.congressional.collector import fetch_trades
        html = """<table>
          <tr><th>h</th><th>h</th><th>h</th><th>h</th><th>h</th></tr>
          <tr><td>Sen. Y</td><td>NOC</td><td>30000</td><td>Purchase</td><td>2026-04-12</td></tr>
        </table>"""
        mock_resp = MagicMock()
        mock_resp.text = html
        mock_resp.raise_for_status = MagicMock()
        with patch.dict("os.environ", {}, clear=True):
            import os; os.environ.pop("QUIVER_API_KEY", None)
            with patch("requests.get", return_value=mock_resp):
                result = fetch_trades()
        assert len(result) == 1
        assert result[0]["source"] == "capitol_trades"

    def test_falls_back_to_sample_when_both_fail(self):
        from spec1_engine.congressional.collector import fetch_trades, SAMPLE_TRADES
        import requests as req
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = req.ConnectionError("down")
        with patch.dict("os.environ", {}, clear=True):
            import os; os.environ.pop("QUIVER_API_KEY", None)
            with patch("requests.get", side_effect=req.ConnectionError("down")):
                result = fetch_trades()
        assert result == list(SAMPLE_TRADES)

    def test_never_raises(self):
        from spec1_engine.congressional.collector import fetch_trades
        with patch("requests.get", side_effect=RuntimeError("unexpected")):
            result = fetch_trades()  # must not raise
        assert isinstance(result, list)


# ═══════════════════════════════════════════════════════════════════════════════
# parser.py
# ═══════════════════════════════════════════════════════════════════════════════

class TestParseDate:
    def test_iso_format(self):
        from spec1_engine.congressional.parser import _parse_date
        dt = _parse_date("2026-04-10")
        assert dt is not None
        assert dt.year == 2026 and dt.month == 4 and dt.day == 10

    def test_us_format(self):
        from spec1_engine.congressional.parser import _parse_date
        dt = _parse_date("04/10/2026")
        assert dt is not None and dt.month == 4

    def test_unknown_format_returns_none(self):
        from spec1_engine.congressional.parser import _parse_date
        assert _parse_date("not-a-date") is None


class TestVelocity:
    def test_recent_trade_is_one(self):
        from spec1_engine.congressional.parser import _velocity
        dt = datetime.now(timezone.utc) - timedelta(days=3)
        assert _velocity(dt) == 1.0

    def test_old_trade_is_half(self):
        from spec1_engine.congressional.parser import _velocity
        dt = datetime.now(timezone.utc) - timedelta(days=20)
        assert _velocity(dt) == 0.5


class TestEngagement:
    def test_zero_amount_returns_fallback(self):
        from spec1_engine.congressional.parser import _engagement
        assert _engagement(0) == 0.1

    def test_negative_returns_fallback(self):
        from spec1_engine.congressional.parser import _engagement
        assert _engagement(-100) == 0.1

    def test_known_amount(self):
        from spec1_engine.congressional.parser import _engagement
        result = _engagement(10_000_000)   # log10(10M) = 7.0 → 7/7 = 1.0
        assert abs(result - 1.0) < 0.001

    def test_midrange_amount(self):
        from spec1_engine.congressional.parser import _engagement
        result = _engagement(100_000)      # log10(100000) ≈ 5/7 ≈ 0.714
        assert 0.7 < result < 0.75


class TestParseTrade:
    def test_returns_signal(self, sample_raw_trade):
        from spec1_engine.congressional.parser import parse_trade
        sig = parse_trade(sample_raw_trade)
        assert sig is not None
        assert sig.source_type == "congressional_trade"
        assert sig.environment == "congressional"

    def test_ticker_uppercased(self, sample_raw_trade):
        from spec1_engine.congressional.parser import parse_trade
        raw = {**sample_raw_trade, "ticker": "lmt"}
        sig = parse_trade(raw)
        assert sig.metadata["ticker"] == "LMT"

    def test_velocity_set_correctly_recent(self, sample_raw_trade):
        from spec1_engine.congressional.parser import parse_trade
        sig = parse_trade(sample_raw_trade)  # trade_date = 3 days ago
        assert sig.velocity == 1.0

    def test_velocity_set_correctly_old(self, old_raw_trade):
        from spec1_engine.congressional.parser import parse_trade
        sig = parse_trade(old_raw_trade)  # trade_date = 45 days ago
        assert sig.velocity == 0.5

    def test_engagement_is_log_normalized(self, sample_raw_trade):
        from spec1_engine.congressional.parser import parse_trade
        sig = parse_trade(sample_raw_trade)  # amount=50000
        expected = round(math.log10(50000) / 7.0, 4)
        assert sig.engagement == expected

    def test_missing_politician_returns_none(self, sample_raw_trade):
        from spec1_engine.congressional.parser import parse_trade
        raw = {**sample_raw_trade, "politician": ""}
        assert parse_trade(raw) is None

    def test_missing_ticker_returns_none(self, sample_raw_trade):
        from spec1_engine.congressional.parser import parse_trade
        raw = {**sample_raw_trade, "ticker": ""}
        assert parse_trade(raw) is None

    def test_metadata_preserved(self, sample_raw_trade):
        from spec1_engine.congressional.parser import parse_trade
        sig = parse_trade(sample_raw_trade)
        assert sig.metadata["politician"] == "Sen. Alice Test"
        assert sig.metadata["committee"] == "Armed Services"
        assert sig.metadata["amount"] == 50000

    def test_signal_id_deterministic(self, sample_raw_trade):
        from spec1_engine.congressional.parser import parse_trade
        s1 = parse_trade(sample_raw_trade)
        s2 = parse_trade(sample_raw_trade)
        assert s1.signal_id == s2.signal_id

    def test_run_id_passthrough(self, sample_raw_trade):
        from spec1_engine.congressional.parser import parse_trade
        sig = parse_trade(sample_raw_trade, run_id="run-test-123")
        assert sig.run_id == "run-test-123"


class TestParseBatch:
    def test_returns_list_of_signals(self, sample_raw_trade):
        from spec1_engine.congressional.parser import parse_batch
        result = parse_batch([sample_raw_trade, sample_raw_trade])
        assert len(result) == 2

    def test_skips_invalid_records(self, sample_raw_trade):
        from spec1_engine.congressional.parser import parse_batch
        bad = {"politician": "", "ticker": ""}
        result = parse_batch([sample_raw_trade, bad, sample_raw_trade])
        assert len(result) == 2

    def test_empty_input_returns_empty(self):
        from spec1_engine.congressional.parser import parse_batch
        assert parse_batch([]) == []


# ═══════════════════════════════════════════════════════════════════════════════
# scorer.py
# ═══════════════════════════════════════════════════════════════════════════════

def _make_signal(
    politician="Sen. Test",
    ticker="LMT",
    amount=50_000,
    days_ago=3,
    source="quiver",
    committee="Armed Services",
    trade_type="Purchase",
) -> "Signal":
    from spec1_engine.congressional.parser import parse_trade
    raw = {
        "politician": politician,
        "ticker": ticker,
        "amount": amount,
        "trade_type": trade_type,
        "trade_date": _days_ago(days_ago),
        "committee": committee,
        "source": source,
    }
    return parse_trade(raw)


class TestGates:
    def setup_method(self):
        from spec1_engine.congressional.scorer import clear_novelty_cache
        clear_novelty_cache()

    def test_all_gates_pass_returns_opportunity(self):
        from spec1_engine.congressional.scorer import score_signal
        sig = _make_signal(amount=50_000, days_ago=3)
        opp = score_signal(sig, run_id="run-1")
        assert opp is not None

    def test_gate_amount_blocks_small_trade(self):
        from spec1_engine.congressional.scorer import score_signal
        sig = _make_signal(amount=5_000)   # below $15,000
        assert score_signal(sig, run_id="run-1") is None

    def test_gate_amount_passes_at_threshold_plus_one(self):
        from spec1_engine.congressional.scorer import score_signal
        sig = _make_signal(amount=15_001)
        assert score_signal(sig, run_id="run-1") is not None

    def test_gate_recency_blocks_old_trade(self):
        from spec1_engine.congressional.scorer import score_signal
        sig = _make_signal(amount=50_000, days_ago=35)  # 35 days > 30
        assert score_signal(sig, run_id="run-1") is None

    def test_gate_recency_passes_within_30_days(self):
        from spec1_engine.congressional.scorer import score_signal
        sig = _make_signal(amount=50_000, days_ago=29)
        assert score_signal(sig, run_id="run-1") is not None

    def test_gate_novelty_blocks_repeat_run(self):
        from spec1_engine.congressional.scorer import score_signal
        sig = _make_signal(amount=50_000, days_ago=3)
        # same run_id = already seen
        score_signal(sig, run_id="run-dup")
        assert score_signal(sig, run_id="run-dup") is None

    def test_gate_novelty_passes_new_run(self):
        from spec1_engine.congressional.scorer import score_signal
        sig = _make_signal(amount=50_000, days_ago=3)
        score_signal(sig, run_id="run-A")
        assert score_signal(sig, run_id="run-B") is not None

    def test_gate_credibility_always_passes(self):
        from spec1_engine.congressional.scorer import score_signal
        sig = _make_signal(amount=50_000, days_ago=3, source="unknown_source")
        opp = score_signal(sig, run_id="run-1")
        assert opp is not None
        assert opp.gate_results["credibility"] is True


class TestPriority:
    def setup_method(self):
        from spec1_engine.congressional.scorer import clear_novelty_cache
        clear_novelty_cache()

    def test_elevated_for_large_recent_trade(self):
        from spec1_engine.congressional.scorer import score_signal
        sig = _make_signal(amount=300_000, days_ago=2)
        opp = score_signal(sig, run_id="run-1")
        assert opp.priority == "ELEVATED"

    def test_not_elevated_for_large_old_trade(self):
        from spec1_engine.congressional.scorer import score_signal
        sig = _make_signal(amount=300_000, days_ago=15)  # > 7 days
        opp = score_signal(sig, run_id="run-1")
        assert opp.priority != "ELEVATED"

    def test_not_elevated_for_small_recent_trade(self):
        from spec1_engine.congressional.scorer import score_signal
        sig = _make_signal(amount=20_000, days_ago=2)
        opp = score_signal(sig, run_id="run-1")
        assert opp.priority != "ELEVATED"


class TestNoveltyWindow:
    def test_window_of_five_cycles(self):
        from spec1_engine.congressional.scorer import score_signal, clear_novelty_cache
        clear_novelty_cache()
        sig = _make_signal(amount=50_000, days_ago=3)
        # 5 different run_ids all see it (should pass each)
        for i in range(5):
            clear_novelty_cache()
            opp = score_signal(sig, run_id=f"run-{i}")
            assert opp is not None

    def test_same_run_id_blocked_second_time(self):
        from spec1_engine.congressional.scorer import score_signal, clear_novelty_cache
        clear_novelty_cache()
        sig = _make_signal(amount=50_000, days_ago=3)
        score_signal(sig, run_id="run-x")
        assert score_signal(sig, run_id="run-x") is None


class TestScoreBatch:
    def setup_method(self):
        from spec1_engine.congressional.scorer import clear_novelty_cache
        clear_novelty_cache()

    def test_returns_opportunities_and_blocked(self):
        from spec1_engine.congressional.scorer import score_batch
        good = _make_signal(amount=50_000, days_ago=3)
        bad  = _make_signal(amount=1_000, days_ago=3, politician="Rep. Cheap", ticker="XYZ")
        result = score_batch([good, bad], run_id="run-batch")
        assert len(result["opportunities"]) == 1
        assert len(result["blocked"]) == 1


# ═══════════════════════════════════════════════════════════════════════════════
# analyzer.py
# ═══════════════════════════════════════════════════════════════════════════════

def _make_pipeline_objects(
    politician="Sen. Test",
    ticker="LMT",
    amount=50_000,
    trade_type="Purchase",
    committee="Armed Services",
    days_ago=3,
    outcome_classification="Investigate",
):
    """Return (opportunity, investigation, outcome, signal) for analyzer tests."""
    from spec1_engine.congressional.scorer import clear_novelty_cache, score_signal
    from spec1_engine.investigation.generator import generate_investigation
    from spec1_engine.schemas.models import Outcome, ParsedSignal
    import uuid

    clear_novelty_cache()
    sig = _make_signal(politician=politician, ticker=ticker, amount=amount,
                       trade_type=trade_type, committee=committee, days_ago=days_ago)
    opp = score_signal(sig, run_id="run-az")

    parsed = ParsedSignal(
        signal_id=sig.signal_id,
        cleaned_text=sig.text,
        keywords=["purchase", "lmt", "defense"],
        entities=[politician, ticker],
        language="en",
        word_count=len(sig.text.split()),
    )
    inv = generate_investigation(opp, sig, parsed)
    outcome = Outcome(
        outcome_id=f"out-{uuid.uuid4().hex[:8]}",
        classification=outcome_classification,
        confidence=0.70,
        evidence=[],
    )
    return opp, inv, outcome, sig


class TestCommitteeOverlap:
    def test_direct_overlap_scores_one(self):
        from spec1_engine.congressional.analyzer import _committee_overlap
        sig = _make_signal(ticker="LMT", committee="Armed Services", amount=50000)
        assert _committee_overlap(sig) == 1.0

    def test_known_committee_no_ticker_match_scores_partial(self):
        from spec1_engine.congressional.analyzer import _committee_overlap
        sig = _make_signal(ticker="TSLA", committee="Armed Services", amount=50000)
        assert _committee_overlap(sig) == 0.35

    def test_unknown_committee_scores_low(self):
        from spec1_engine.congressional.analyzer import _committee_overlap
        sig = _make_signal(ticker="LMT", committee="Unknown Committee", amount=50000)
        assert _committee_overlap(sig) == 0.10


class TestClassify:
    def test_high_score_is_corroborated(self):
        from spec1_engine.congressional.analyzer import _classify
        assert _classify(0.85) == "Corroborated"

    def test_mid_high_is_escalate(self):
        from spec1_engine.congressional.analyzer import _classify
        assert _classify(0.70) == "Escalate"

    def test_mid_is_investigate(self):
        from spec1_engine.congressional.analyzer import _classify
        assert _classify(0.50) == "Investigate"

    def test_low_is_monitor(self):
        from spec1_engine.congressional.analyzer import _classify
        assert _classify(0.30) == "Monitor"

    def test_boundary_corroborated(self):
        from spec1_engine.congressional.analyzer import _classify
        assert _classify(0.80) == "Corroborated"

    def test_boundary_escalate(self):
        from spec1_engine.congressional.analyzer import _classify
        assert _classify(0.65) == "Escalate"

    def test_boundary_investigate(self):
        from spec1_engine.congressional.analyzer import _classify
        assert _classify(0.45) == "Investigate"


class TestAnalyze:
    def test_returns_intelligence_record(self):
        from spec1_engine.congressional.analyzer import analyze
        from spec1_engine.schemas.models import IntelligenceRecord
        opp, inv, outcome, sig = _make_pipeline_objects()
        record = analyze(opp, inv, outcome, sig)
        assert isinstance(record, IntelligenceRecord)

    def test_record_id_prefixed_correctly(self):
        from spec1_engine.congressional.analyzer import analyze
        opp, inv, outcome, sig = _make_pipeline_objects()
        record = analyze(opp, inv, outcome, sig)
        assert record.record_id.startswith("rec-c-")

    def test_confidence_between_zero_and_one(self):
        from spec1_engine.congressional.analyzer import analyze
        opp, inv, outcome, sig = _make_pipeline_objects()
        record = analyze(opp, inv, outcome, sig)
        assert 0.0 <= record.confidence <= 0.99

    def test_high_overlap_high_amount_escalates(self):
        from spec1_engine.congressional.analyzer import analyze
        opp, inv, outcome, sig = _make_pipeline_objects(
            ticker="LMT", committee="Armed Services",
            amount=300_000, trade_type="Purchase", days_ago=2,
            outcome_classification="Corroborated",
        )
        record = analyze(opp, inv, outcome, sig)
        assert record.classification in ("Corroborated", "Escalate", "Investigate")

    def test_pattern_contains_politician_and_ticker(self):
        from spec1_engine.congressional.analyzer import analyze
        opp, inv, outcome, sig = _make_pipeline_objects(
            politician="Sen. Alice Test", ticker="LMT"
        )
        record = analyze(opp, inv, outcome, sig)
        assert "Sen. Alice Test" in record.pattern
        assert "LMT" in record.pattern

    def test_purchase_direction_scores_higher_than_sale(self):
        from spec1_engine.congressional.analyzer import _trade_direction
        from spec1_engine.congressional.parser import parse_trade
        buy_sig = parse_trade({
            "politician": "Sen. X", "ticker": "LMT", "amount": 50000,
            "trade_type": "Purchase", "trade_date": _days_ago(3),
            "committee": "Armed Services", "source": "sample",
        })
        sell_sig = parse_trade({
            "politician": "Sen. X", "ticker": "LMT", "amount": 50000,
            "trade_type": "Sale", "trade_date": _days_ago(3),
            "committee": "Armed Services", "source": "sample",
        })
        assert _trade_direction(buy_sig) > _trade_direction(sell_sig)


# ═══════════════════════════════════════════════════════════════════════════════
# cycle.py — sample mode (no HTTP, no Claude API needed for cycle to complete)
# ═══════════════════════════════════════════════════════════════════════════════

class TestRunCongressionalCycle:
    def test_sample_mode_returns_stats_dict(self, store_path):
        from spec1_engine.congressional.cycle import run_congressional_cycle
        stats = run_congressional_cycle(store_path=store_path, sample=True, verbose=False)
        assert isinstance(stats, dict)
        assert stats["domain"] == "congressional"
        assert stats["mode"] == "sample"

    def test_sample_mode_fetches_3_trades(self, store_path):
        from spec1_engine.congressional.cycle import run_congressional_cycle
        stats = run_congressional_cycle(store_path=store_path, sample=True, verbose=False)
        assert stats["trades_fetched"] == 3

    def test_sample_mode_parses_3_signals(self, store_path):
        from spec1_engine.congressional.cycle import run_congressional_cycle
        stats = run_congressional_cycle(store_path=store_path, sample=True, verbose=False)
        assert stats["signals_parsed"] == 3

    def test_sample_mode_writes_jsonl(self, store_path):
        from spec1_engine.congressional.cycle import run_congressional_cycle
        stats = run_congressional_cycle(store_path=store_path, sample=True, verbose=False)
        assert stats["records_stored"] >= 1
        assert store_path.exists()
        lines = [l for l in store_path.read_text().splitlines() if l.strip()]
        assert len(lines) == stats["records_stored"]

    def test_jsonl_records_have_required_fields(self, store_path):
        from spec1_engine.congressional.cycle import run_congressional_cycle
        run_congressional_cycle(store_path=store_path, sample=True, verbose=False)
        lines = [l for l in store_path.read_text().splitlines() if l.strip()]
        for line in lines:
            rec = json.loads(line)
            for field in ("run_id", "domain", "politician", "ticker", "amount",
                          "trade_date", "opportunity_priority", "gate_results"):
                assert field in rec, f"Missing field: {field}"

    def test_kill_switch_aborts_cycle(self, store_path, tmp_path):
        from spec1_engine.congressional import cycle as cycle_mod
        kill_file = tmp_path / ".cls_kill"
        kill_file.touch()
        original = cycle_mod.KILL_FILE
        cycle_mod.KILL_FILE = kill_file
        try:
            stats = cycle_mod.run_congressional_cycle(
                store_path=store_path, sample=True, verbose=False
            )
            assert stats.get("status") == "killed"
        finally:
            cycle_mod.KILL_FILE = original

    def test_no_errors_in_sample_mode(self, store_path):
        from spec1_engine.congressional.cycle import run_congressional_cycle
        stats = run_congressional_cycle(store_path=store_path, sample=True, verbose=False)
        assert stats["errors"] == []

    def test_last_run_state_updated(self, store_path):
        from spec1_engine.congressional.cycle import run_congressional_cycle, last_run_state
        stats = run_congressional_cycle(store_path=store_path, sample=True, verbose=False)
        assert last_run_state["run_id"] == stats["run_id"]
        assert last_run_state["domain"] == "congressional"

    def test_run_id_appears_in_records(self, store_path):
        from spec1_engine.congressional.cycle import run_congressional_cycle
        stats = run_congressional_cycle(
            store_path=store_path, run_id="run-pytest-001",
            sample=True, verbose=False,
        )
        lines = [l for l in store_path.read_text().splitlines() if l.strip()]
        for line in lines:
            rec = json.loads(line)
            assert rec["run_id"] == "run-pytest-001"

    def test_live_mode_with_mocked_fetch(self, store_path):
        from spec1_engine.congressional.cycle import run_congressional_cycle
        from spec1_engine.congressional.collector import SAMPLE_TRADES
        with patch("spec1_engine.congressional.cycle.fetch_trades", return_value=list(SAMPLE_TRADES)):
            stats = run_congressional_cycle(store_path=store_path, sample=False, verbose=False)
        assert stats["trades_fetched"] == 3
