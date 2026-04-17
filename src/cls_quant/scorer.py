"""Quant signal scorer — 4-gate scoring for market data."""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Optional

from cls_quant.collector import compute_relative_volume
from cls_quant.indicators import bollinger_bands, compute_all, macd, rsi
from cls_quant.schemas import MarketBar, QuantSignal
from cls_quant.sources import get_credibility

# Gate thresholds
CREDIBILITY_THRESHOLD = 0.6    # Ticker must be on watchlist with credibility >= this
VOLUME_THRESHOLD = 1.2          # Relative volume must be >= this (20% above average)
VELOCITY_THRESHOLD = 0.015      # Absolute daily return must be >= 1.5%
NOVELTY_MIN_RSI_CHANGE = 5.0   # RSI must be outside 40–60 band


def _gate_credibility(ticker: str) -> bool:
    return get_credibility(ticker) >= CREDIBILITY_THRESHOLD


def _gate_volume(bars: list[MarketBar]) -> bool:
    if not bars:
        return False
    rel_vol = compute_relative_volume(bars)
    return rel_vol >= VOLUME_THRESHOLD


def _gate_velocity(bar: MarketBar) -> bool:
    return abs(bar.daily_return) >= VELOCITY_THRESHOLD


def _gate_novelty(bars: list[MarketBar]) -> bool:
    """Novelty = RSI outside 40–60 band (indicates non-neutral momentum)."""
    r = rsi(bars)
    if math.isnan(r):
        return True  # insufficient data → treat as novel
    return r < 40 or r > 60


def _detect_pattern(bars: list[MarketBar], indicators: dict) -> str:
    """Classify the primary market pattern."""
    if not bars:
        return "UNKNOWN"
    bar = bars[-1]
    r = indicators.get("rsi", float("nan"))
    bb = indicators.get("bollinger", {})
    pct_b = bb.get("pct_b", 0.5)
    m = indicators.get("macd", {})
    histogram = m.get("histogram", 0)

    if bar.daily_return >= 0.03 and compute_relative_volume(bars) >= 1.5:
        return "HIGH_VOL_BREAKOUT"
    if bar.daily_return <= -0.03 and compute_relative_volume(bars) >= 1.5:
        return "HIGH_VOL_BREAKDOWN"
    if not math.isnan(r):
        if r > 70:
            return "OVERBOUGHT"
        if r < 30:
            return "OVERSOLD"
    if not math.isnan(pct_b):
        if pct_b > 1.0:
            return "BB_UPPER_BREACH"
        if pct_b < 0.0:
            return "BB_LOWER_BREACH"
    if not math.isnan(histogram if not isinstance(histogram, float) else histogram):
        if isinstance(histogram, float) and not math.isnan(histogram):
            if histogram > 0 and bar.daily_return > 0:
                return "MOMENTUM_UP"
            if histogram < 0 and bar.daily_return < 0:
                return "MOMENTUM_DOWN"
    return "NEUTRAL"


def score_bar(
    ticker: str,
    bars: list[MarketBar],
) -> Optional[QuantSignal]:
    """Score the latest bar for a ticker through the 4-gate system.

    Returns a QuantSignal if the bar passes all gates; None otherwise.
    """
    if not bars:
        return None

    bar = bars[-1]
    gate_credibility = _gate_credibility(ticker)
    gate_volume = _gate_volume(bars)
    gate_velocity = _gate_velocity(bar)
    gate_novelty = _gate_novelty(bars)

    gate_results = {
        "credibility": gate_credibility,
        "volume": gate_volume,
        "velocity": gate_velocity,
        "novelty": gate_novelty,
    }

    # Must pass all gates
    if not all(gate_results.values()):
        return None

    indicators = compute_all(bars)
    pattern = _detect_pattern(bars, indicators)
    gates_passed = sum(gate_results.values())
    score = round(gates_passed / 4.0, 3)

    signal_id = QuantSignal.make_id(ticker, pattern, bar.date)

    return QuantSignal(
        signal_id=signal_id,
        ticker=ticker,
        pattern=pattern,
        score=score,
        gate_results=gate_results,
        triggered_at=datetime.now(timezone.utc),
        bar=bar,
        indicators={
            "rsi": indicators.get("rsi"),
            "macd_histogram": indicators.get("macd", {}).get("histogram"),
            "bb_pct_b": indicators.get("bollinger", {}).get("pct_b"),
            "atr": indicators.get("atr"),
            "relative_volume": compute_relative_volume(bars),
            "daily_return": bar.daily_return,
        },
        metadata={"ticker": ticker, "date": bar.date},
    )


def score_all(
    market_data: dict[str, list[MarketBar]],
) -> list[QuantSignal]:
    """Score all tickers; return list of QuantSignals that passed all gates."""
    signals: list[QuantSignal] = []
    for ticker, bars in market_data.items():
        try:
            sig = score_bar(ticker, bars)
            if sig is not None:
                signals.append(sig)
        except Exception:
            continue
    signals.sort(key=lambda s: s.score, reverse=True)
    return signals
