"""Tests for the SPEC-1 quant domain."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from spec1_engine.schemas.models import Opportunity, ParsedSignal, Signal


# ─── Helpers ──────────────────────────────────────────────────────────────────

def make_df(
    closes: list[float],
    volumes: list[float] | None = None,
    start: str = "2024-01-01",
) -> pd.DataFrame:
    """Build a minimal OHLCV DataFrame."""
    n = len(closes)
    if volumes is None:
        volumes = [1_000_000.0] * n
    index = pd.date_range(start, periods=n, freq="B", tz="UTC")
    df = pd.DataFrame(
        {
            "Open":   [c * 0.99 for c in closes],
            "High":   [c * 1.01 for c in closes],
            "Low":    [c * 0.98 for c in closes],
            "Close":  closes,
            "Volume": volumes,
        },
        index=index,
    )
    return df


def make_signal(
    ticker: str = "LMT",
    daily_return: float = 0.02,
    rel_volume: float = 1.5,
    run_id: str = "run-test",
) -> Signal:
    return Signal(
        signal_id=f"q-{ticker}-test",
        source=ticker,
        source_type="market_data",
        text=f"{ticker} — close=450.00, vol=1,000,000, date=2024-01-15",
        url=f"https://finance.yahoo.com/quote/{ticker}",
        author="yfinance",
        published_at=datetime(2024, 1, 15, tzinfo=timezone.utc),
        velocity=daily_return,
        engagement=rel_volume,
        run_id=run_id,
        environment="quant",
        metadata={
            "ticker": ticker,
            "sector": "defense",
            "open": 445.0, "high": 455.0, "low": 443.0,
            "close": 450.0, "volume": 1_000_000,
            "daily_return": daily_return,
            "relative_volume": rel_volume,
        },
    )


# ─── collector.py ─────────────────────────────────────────────────────────────

def test_all_tickers_not_empty():
    from spec1_engine.quant.collector import ALL_TICKERS
    assert len(ALL_TICKERS) > 0


def test_watchlist_has_all_sectors():
    from spec1_engine.quant.collector import WATCHLIST
    assert "defense" in WATCHLIST
    assert "cyber" in WATCHLIST
    assert "energy" in WATCHLIST
    assert "macro" in WATCHLIST


def test_defense_tickers_present():
    from spec1_engine.quant.collector import WATCHLIST
    for t in ["LMT", "RTX", "NOC", "GD", "BA"]:
        assert t in WATCHLIST["defense"]


def test_cyber_tickers_present():
    from spec1_engine.quant.collector import WATCHLIST
    for t in ["PANW", "CRWD", "S", "FTNT"]:
        assert t in WATCHLIST["cyber"]


def test_energy_tickers_present():
    from spec1_engine.quant.collector import WATCHLIST
    for t in ["XOM", "CVX", "SLB"]:
        assert t in WATCHLIST["energy"]


def test_macro_tickers_present():
    from spec1_engine.quant.collector import WATCHLIST
    for t in ["SPY", "GLD", "TLT"]:
        assert t in WATCHLIST["macro"]


def test_ticker_sector_maps_all():
    from spec1_engine.quant.collector import TICKER_SECTOR, ALL_TICKERS
    for ticker in ALL_TICKERS:
        assert ticker in TICKER_SECTOR


def test_fetch_ohlcv_returns_dataframe_on_success():
    from spec1_engine.quant.collector import fetch_ohlcv
    df = make_df([100.0, 102.0, 101.0])
    with patch("yfinance.download", return_value=df):
        result = fetch_ohlcv("LMT")
    assert isinstance(result, pd.DataFrame)
    assert not result.empty


def test_fetch_ohlcv_returns_empty_on_failure():
    from spec1_engine.quant.collector import fetch_ohlcv
    with patch("yfinance.download", side_effect=Exception("network error")):
        result = fetch_ohlcv("LMT")
    assert isinstance(result, pd.DataFrame)
    assert result.empty


def test_fetch_ohlcv_does_not_raise():
    from spec1_engine.quant.collector import fetch_ohlcv
    with patch("yfinance.download", side_effect=RuntimeError("timeout")):
        try:
            fetch_ohlcv("BAD")
        except Exception as exc:
            pytest.fail(f"fetch_ohlcv raised: {exc}")


def test_fetch_all_returns_dict():
    from spec1_engine.quant.collector import fetch_all
    df = make_df([100.0, 102.0])
    with patch("spec1_engine.quant.collector.fetch_ohlcv", return_value=df):
        result = fetch_all(tickers=["LMT", "RTX"])
    assert isinstance(result, dict)


def test_fetch_all_skips_empty_tickers():
    from spec1_engine.quant.collector import fetch_all
    good_df = make_df([100.0, 102.0])

    def mock_fetch(ticker, **_):
        return good_df if ticker == "LMT" else pd.DataFrame()

    with patch("spec1_engine.quant.collector.fetch_ohlcv", side_effect=mock_fetch):
        result = fetch_all(tickers=["LMT", "RTX"])
    assert "LMT" in result
    assert "RTX" not in result


# ─── parser.py ────────────────────────────────────────────────────────────────

def test_parse_row_returns_signal():
    from spec1_engine.quant.parser import parse_row
    df = make_df([100.0, 102.0, 104.0], volumes=[1e6, 1e6, 2e6])
    sig = parse_row("LMT", df, 2, run_id="run-test")
    assert isinstance(sig, Signal)


def test_parse_row_source_type_is_market_data():
    from spec1_engine.quant.parser import parse_row
    df = make_df([100.0, 102.0])
    sig = parse_row("RTX", df, 1)
    assert sig.source_type == "market_data"


def test_parse_row_source_is_ticker():
    from spec1_engine.quant.parser import parse_row
    df = make_df([100.0, 102.0])
    sig = parse_row("NOC", df, 1)
    assert sig.source == "NOC"


def test_parse_row_environment_is_quant():
    from spec1_engine.quant.parser import parse_row
    df = make_df([100.0, 102.0])
    sig = parse_row("GD", df, 1)
    assert sig.environment == "quant"


def test_parse_row_author_is_yfinance():
    from spec1_engine.quant.parser import parse_row
    df = make_df([100.0, 102.0])
    sig = parse_row("BA", df, 1)
    assert sig.author == "yfinance"


def test_parse_row_url_contains_ticker():
    from spec1_engine.quant.parser import parse_row
    df = make_df([100.0, 102.0])
    sig = parse_row("PANW", df, 1)
    assert "PANW" in sig.url


def test_parse_row_velocity_is_daily_return():
    from spec1_engine.quant.parser import parse_row
    closes = [100.0, 110.0]  # +10%
    df = make_df(closes)
    sig = parse_row("LMT", df, 1)
    assert abs(sig.velocity - 0.10) < 0.001


def test_parse_row_engagement_is_relative_volume():
    from spec1_engine.quant.parser import parse_row
    # avg of first 30 days = 1e6, last day = 2e6 → rel_vol ≈ 2.0
    vols = [1_000_000.0] * 31
    vols[-1] = 2_000_000.0
    closes = [100.0] * 31
    df = make_df(closes, volumes=vols)
    sig = parse_row("LMT", df, 30)
    assert sig.engagement > 1.5


def test_parse_row_metadata_has_ohlcv():
    from spec1_engine.quant.parser import parse_row
    df = make_df([100.0, 102.0])
    sig = parse_row("LMT", df, 1)
    for key in ["open", "high", "low", "close", "volume", "ticker"]:
        assert key in sig.metadata


def test_parse_row_text_contains_ticker():
    from spec1_engine.quant.parser import parse_row
    df = make_df([100.0, 102.0])
    sig = parse_row("SPY", df, 1)
    assert "SPY" in sig.text


def test_parse_dataframe_latest_only():
    from spec1_engine.quant.parser import parse_dataframe
    df = make_df([100.0, 101.0, 102.0, 103.0, 104.0])
    sigs = parse_dataframe("LMT", df, latest_only=True)
    assert len(sigs) == 1


def test_parse_dataframe_all_rows():
    from spec1_engine.quant.parser import parse_dataframe
    df = make_df([100.0, 101.0, 102.0, 103.0, 104.0])
    sigs = parse_dataframe("LMT", df, latest_only=False)
    assert len(sigs) == 5


def test_parse_dataframe_empty_df():
    from spec1_engine.quant.parser import parse_dataframe
    sigs = parse_dataframe("LMT", pd.DataFrame())
    assert sigs == []


def test_parse_row_signal_id_is_deterministic():
    from spec1_engine.quant.parser import parse_row
    df = make_df([100.0, 102.0])
    sig1 = parse_row("LMT", df, 1)
    sig2 = parse_row("LMT", df, 1)
    assert sig1.signal_id == sig2.signal_id


def test_parse_row_different_ticker_different_id():
    from spec1_engine.quant.parser import parse_row
    df = make_df([100.0, 102.0])
    sig_lmt = parse_row("LMT", df, 1)
    sig_rtx = parse_row("RTX", df, 1)
    assert sig_lmt.signal_id != sig_rtx.signal_id


# ─── scorer.py ────────────────────────────────────────────────────────────────

def test_score_signal_passes_all_gates():
    from spec1_engine.quant.scorer import score_signal, clear_seen
    clear_seen()
    sig = make_signal("LMT", daily_return=0.02, rel_volume=1.5, run_id="run-s1")
    opp = score_signal(sig, run_id="run-s1")
    assert opp is not None


def test_score_signal_returns_opportunity():
    from spec1_engine.quant.scorer import score_signal, clear_seen
    clear_seen()
    sig = make_signal("RTX", daily_return=0.015, rel_volume=1.8, run_id="run-s2")
    opp = score_signal(sig, run_id="run-s2")
    assert isinstance(opp, Opportunity)


def test_gate_credibility_unknown_ticker_blocked():
    from spec1_engine.quant.scorer import score_signal, clear_seen
    clear_seen()
    sig = make_signal("AAPL", daily_return=0.05, rel_volume=2.0, run_id="run-s3")
    opp = score_signal(sig, run_id="run-s3")
    assert opp is None


def test_gate_volume_low_blocks():
    from spec1_engine.quant.scorer import score_signal, clear_seen
    clear_seen()
    sig = make_signal("LMT", daily_return=0.02, rel_volume=0.9, run_id="run-s4")
    opp = score_signal(sig, run_id="run-s4")
    assert opp is None


def test_gate_velocity_low_blocks():
    from spec1_engine.quant.scorer import score_signal, clear_seen
    clear_seen()
    sig = make_signal("LMT", daily_return=0.001, rel_volume=2.0, run_id="run-s5")
    opp = score_signal(sig, run_id="run-s5")
    assert opp is None


def test_gate_novelty_dedup_blocks_second():
    from spec1_engine.quant.scorer import score_signal, clear_seen
    clear_seen()
    run = "run-dedup"
    sig1 = make_signal("LMT", daily_return=0.02, rel_volume=1.5, run_id=run)
    sig2 = make_signal("LMT", daily_return=0.02, rel_volume=1.5, run_id=run)
    # Same ticker+date → second call should be blocked
    score_signal(sig1, run_id=run)
    opp2 = score_signal(sig2, run_id=run)
    assert opp2 is None


def test_gate_novelty_different_run_passes():
    from spec1_engine.quant.scorer import score_signal, clear_seen
    clear_seen()
    sig1 = make_signal("LMT", daily_return=0.02, rel_volume=1.5, run_id="run-a")
    sig2 = make_signal("LMT", daily_return=0.02, rel_volume=1.5, run_id="run-b")
    score_signal(sig1, run_id="run-a")
    opp2 = score_signal(sig2, run_id="run-b")
    assert opp2 is not None


def test_opportunity_id_starts_with_opp_q():
    from spec1_engine.quant.scorer import score_signal, clear_seen
    clear_seen()
    sig = make_signal("NOC", daily_return=0.02, rel_volume=1.5, run_id="run-s6")
    opp = score_signal(sig, run_id="run-s6")
    assert opp.opportunity_id.startswith("opp-q-")


def test_opportunity_has_valid_priority():
    from spec1_engine.quant.scorer import score_signal, clear_seen
    clear_seen()
    sig = make_signal("GD", daily_return=0.02, rel_volume=1.5, run_id="run-s7")
    opp = score_signal(sig, run_id="run-s7")
    assert opp.priority in {"ELEVATED", "STANDARD", "MONITOR"}


def test_opportunity_score_in_range():
    from spec1_engine.quant.scorer import score_signal, clear_seen
    clear_seen()
    sig = make_signal("BA", daily_return=0.02, rel_volume=1.5, run_id="run-s8")
    opp = score_signal(sig, run_id="run-s8")
    assert 0.0 <= opp.score <= 1.0


def test_opportunity_gate_results_has_all_4():
    from spec1_engine.quant.scorer import score_signal, clear_seen
    clear_seen()
    sig = make_signal("CRWD", daily_return=0.02, rel_volume=1.5, run_id="run-s9")
    opp = score_signal(sig, run_id="run-s9")
    assert set(opp.gate_results.keys()) == {"credibility", "volume", "velocity", "novelty"}


def test_score_batch_returns_dict():
    from spec1_engine.quant.scorer import score_batch, clear_seen
    clear_seen()
    signals = [
        make_signal("LMT", daily_return=0.02, rel_volume=1.5, run_id="run-b1"),
        make_signal("AAPL", daily_return=0.02, rel_volume=1.5, run_id="run-b1"),  # unknown
    ]
    result = score_batch(signals, run_id="run-b1")
    assert "opportunities" in result
    assert "blocked" in result


def test_clear_seen_clears_specific_run():
    from spec1_engine.quant.scorer import score_signal, clear_seen, _seen
    clear_seen()
    run = "run-clear"
    sig = make_signal("LMT", daily_return=0.02, rel_volume=1.5, run_id=run)
    score_signal(sig, run_id=run)
    assert run in _seen
    clear_seen(run)
    assert run not in _seen


# ─── analyzer.py ──────────────────────────────────────────────────────────────

def _make_investigation(opportunity_id: str = "opp-q-test"):
    from spec1_engine.schemas.models import Investigation
    return Investigation(
        investigation_id="inv-q-test",
        opportunity_id=opportunity_id,
        hypothesis="Test hypothesis.",
        queries=[],
        sources_to_check=[],
        analyst_leads=[],
    )


def _make_outcome(classification: str = "Investigate", confidence: float = 0.5):
    from spec1_engine.schemas.models import Outcome
    return Outcome(
        outcome_id="out-q-test",
        classification=classification,
        confidence=confidence,
        evidence=[],
    )


def _make_opportunity(signal_id: str = "q-LMT-test", priority: str = "STANDARD"):
    return Opportunity(
        opportunity_id="opp-q-test",
        signal_id=signal_id,
        score=0.65,
        priority=priority,
        gate_results={"credibility": True, "volume": True, "velocity": True, "novelty": True},
        run_id="run-test",
    )


def test_analyze_returns_intelligence_record():
    from spec1_engine.quant.analyzer import analyze
    from spec1_engine.schemas.models import IntelligenceRecord
    sig  = make_signal("LMT")
    opp  = _make_opportunity()
    inv  = _make_investigation()
    out  = _make_outcome()
    rec  = analyze(opp, inv, out, sig)
    assert isinstance(rec, IntelligenceRecord)


def test_analyze_record_id_starts_with_rec_q():
    from spec1_engine.quant.analyzer import analyze
    sig = make_signal("LMT")
    rec = analyze(_make_opportunity(), _make_investigation(), _make_outcome(), sig)
    assert rec.record_id.startswith("rec-q-")


def test_analyze_pattern_contains_ticker():
    from spec1_engine.quant.analyzer import analyze
    sig = make_signal("RTX")
    rec = analyze(_make_opportunity(), _make_investigation(), _make_outcome(), sig)
    assert "RTX" in rec.pattern


def test_analyze_pattern_contains_sector():
    from spec1_engine.quant.analyzer import analyze
    sig = make_signal("LMT")  # sector=defense
    rec = analyze(_make_opportunity(), _make_investigation(), _make_outcome(), sig)
    assert "DEFENSE" in rec.pattern


def test_analyze_confidence_in_range():
    from spec1_engine.quant.analyzer import analyze
    sig = make_signal("LMT")
    rec = analyze(_make_opportunity(), _make_investigation(), _make_outcome(), sig)
    assert 0.0 <= rec.confidence <= 1.0


def test_analyze_classification_passes_through():
    from spec1_engine.quant.analyzer import analyze
    sig = make_signal("LMT")
    out = _make_outcome(classification="Escalate")
    rec = analyze(_make_opportunity(), _make_investigation(), out, sig)
    assert rec.classification == "Escalate"


def test_analyze_source_weight_is_sector_weight():
    from spec1_engine.quant.analyzer import analyze, SECTOR_WEIGHTS
    sig = make_signal("LMT")  # defense sector
    rec = analyze(_make_opportunity(), _make_investigation(), _make_outcome(), sig)
    assert rec.source_weight == SECTOR_WEIGHTS["defense"]


def test_analyze_high_vol_pattern_detected():
    from spec1_engine.quant.analyzer import analyze
    # daily_return=0.04, rel_volume=2.5 → HIGH_VOL_BREAKOUT
    sig = make_signal("PANW", daily_return=0.04, rel_volume=2.5)
    rec = analyze(_make_opportunity(), _make_investigation(), _make_outcome(), sig)
    assert "HIGH_VOL" in rec.pattern or "MOMENTUM" in rec.pattern


# ─── cycle.py ─────────────────────────────────────────────────────────────────

def _make_mock_ohlcv(ticker: str = "LMT") -> dict:
    """Return a minimal mock ohlcv dict for cycle tests."""
    # 35 rows so relative volume calculation has enough history
    closes  = [100.0 + i * 0.5 for i in range(35)]
    volumes = [1_000_000.0] * 34 + [2_500_000.0]  # spike on last day
    df = make_df(closes, volumes=volumes)
    return {ticker: df}


def test_run_quant_cycle_returns_dict(tmp_path):
    from spec1_engine.quant.cycle import run_quant_cycle
    from spec1_engine.quant.scorer import clear_seen
    clear_seen()

    mock_ohlcv = _make_mock_ohlcv("LMT")
    with patch("spec1_engine.quant.cycle.fetch_all", return_value=mock_ohlcv), \
         patch("spec1_engine.quant.cycle.verify_investigation") as mock_verify:
        from spec1_engine.schemas.models import Outcome
        mock_verify.return_value = Outcome(
            outcome_id="out-test", classification="Investigate",
            confidence=0.5, evidence=[],
        )
        stats = run_quant_cycle(
            store_path=tmp_path / "quant.jsonl",
            tickers=["LMT"],
            verbose=False,
        )

    assert isinstance(stats, dict)


def test_run_quant_cycle_stats_keys(tmp_path):
    from spec1_engine.quant.cycle import run_quant_cycle
    from spec1_engine.quant.scorer import clear_seen
    clear_seen()

    with patch("spec1_engine.quant.cycle.fetch_all", return_value={}):
        stats = run_quant_cycle(store_path=tmp_path / "q.jsonl", verbose=False)

    for key in ["run_id", "domain", "signals_parsed", "records_stored", "errors"]:
        assert key in stats


def test_run_quant_cycle_domain_is_quant(tmp_path):
    from spec1_engine.quant.cycle import run_quant_cycle
    from spec1_engine.quant.scorer import clear_seen
    clear_seen()

    with patch("spec1_engine.quant.cycle.fetch_all", return_value={}):
        stats = run_quant_cycle(store_path=tmp_path / "q.jsonl", verbose=False)

    assert stats["domain"] == "quant"


def test_run_quant_cycle_no_crash_on_empty(tmp_path):
    from spec1_engine.quant.cycle import run_quant_cycle
    from spec1_engine.quant.scorer import clear_seen
    clear_seen()

    with patch("spec1_engine.quant.cycle.fetch_all", return_value={}):
        try:
            run_quant_cycle(store_path=tmp_path / "q.jsonl", verbose=False)
        except Exception as exc:
            pytest.fail(f"cycle raised: {exc}")


def test_run_quant_cycle_writes_jsonl(tmp_path):
    from spec1_engine.quant.cycle import run_quant_cycle
    from spec1_engine.quant.scorer import clear_seen
    from spec1_engine.schemas.models import Outcome
    clear_seen()

    mock_ohlcv = _make_mock_ohlcv("LMT")
    store_path = tmp_path / "quant.jsonl"

    with patch("spec1_engine.quant.cycle.fetch_all", return_value=mock_ohlcv), \
         patch("spec1_engine.quant.cycle.verify_investigation") as mock_verify:
        mock_verify.return_value = Outcome(
            outcome_id="out-t", classification="Monitor",
            confidence=0.4, evidence=[],
        )
        stats = run_quant_cycle(store_path=store_path, tickers=["LMT"], verbose=False)

    if stats["records_stored"] > 0:
        import json
        lines = store_path.read_text().strip().split("\n")
        assert len(lines) == stats["records_stored"]
        rec = json.loads(lines[0])
        assert rec["domain"] == "quant"


def test_run_quant_cycle_updates_last_run_state(tmp_path):
    from spec1_engine.quant.cycle import run_quant_cycle, last_run_state
    from spec1_engine.quant.scorer import clear_seen
    clear_seen()

    with patch("spec1_engine.quant.cycle.fetch_all", return_value={}):
        run_quant_cycle(store_path=tmp_path / "q.jsonl", run_id="run-state-test", verbose=False)

    assert last_run_state["run_id"] == "run-state-test"
    assert last_run_state["domain"] == "quant"
