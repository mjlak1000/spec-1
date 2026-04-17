"""Technical indicators for cls_quant.

Implements RSI, MACD, Bollinger Bands, and ATR using only stdlib / math.
"""

from __future__ import annotations

import math
from typing import Sequence

from cls_quant.schemas import MarketBar


def closing_prices(bars: Sequence[MarketBar]) -> list[float]:
    return [b.close for b in bars]


def rsi(bars: Sequence[MarketBar], period: int = 14) -> float:
    """Relative Strength Index (0–100).

    Returns NaN if fewer than period+1 bars available.
    """
    closes = closing_prices(bars)
    if len(closes) < period + 1:
        return float("nan")

    gains: list[float] = []
    losses: list[float] = []
    for i in range(1, len(closes)):
        delta = closes[i] - closes[i - 1]
        if delta >= 0:
            gains.append(delta)
            losses.append(0.0)
        else:
            gains.append(0.0)
            losses.append(abs(delta))

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 2)


def ema(values: list[float], period: int) -> list[float]:
    """Exponential Moving Average."""
    if not values or period <= 0:
        return []
    k = 2 / (period + 1)
    result: list[float] = [values[0]]
    for v in values[1:]:
        result.append(v * k + result[-1] * (1 - k))
    return result


def macd(
    bars: Sequence[MarketBar],
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> dict:
    """MACD indicator.

    Returns dict with keys: macd_line, signal_line, histogram.
    Values are NaN if insufficient data.
    """
    closes = closing_prices(bars)
    if len(closes) < slow + signal:
        return {"macd_line": float("nan"), "signal_line": float("nan"), "histogram": float("nan")}

    fast_ema = ema(closes, fast)
    slow_ema = ema(closes, slow)
    macd_line = [f - s for f, s in zip(fast_ema, slow_ema)]
    signal_line = ema(macd_line, signal)

    latest_macd = round(macd_line[-1], 4) if macd_line else float("nan")
    latest_signal = round(signal_line[-1], 4) if signal_line else float("nan")
    histogram = round(latest_macd - latest_signal, 4) if not (math.isnan(latest_macd) or math.isnan(latest_signal)) else float("nan")

    return {
        "macd_line": latest_macd,
        "signal_line": latest_signal,
        "histogram": histogram,
    }


def bollinger_bands(
    bars: Sequence[MarketBar],
    period: int = 20,
    num_std: float = 2.0,
) -> dict:
    """Bollinger Bands.

    Returns dict: upper, middle (SMA), lower, bandwidth, %B.
    """
    closes = closing_prices(bars)
    if len(closes) < period:
        return {
            "upper": float("nan"),
            "middle": float("nan"),
            "lower": float("nan"),
            "bandwidth": float("nan"),
            "pct_b": float("nan"),
        }

    window = closes[-period:]
    sma = sum(window) / period
    variance = sum((x - sma) ** 2 for x in window) / period
    std = math.sqrt(variance)
    upper = sma + num_std * std
    lower = sma - num_std * std
    bandwidth = (upper - lower) / sma if sma != 0 else 0.0
    latest_close = closes[-1]
    pct_b = (latest_close - lower) / (upper - lower) if (upper - lower) != 0 else 0.5

    return {
        "upper": round(upper, 4),
        "middle": round(sma, 4),
        "lower": round(lower, 4),
        "bandwidth": round(bandwidth, 4),
        "pct_b": round(pct_b, 4),
    }


def atr(bars: Sequence[MarketBar], period: int = 14) -> float:
    """Average True Range.

    Returns NaN if fewer than period+1 bars.
    """
    bars_list = list(bars)
    if len(bars_list) < 2:
        return float("nan")
    trs: list[float] = []
    for i in range(1, len(bars_list)):
        prev_close = bars_list[i - 1].close
        high = bars_list[i].high
        low = bars_list[i].low
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        trs.append(tr)
    if len(trs) < period:
        return round(sum(trs) / len(trs), 4) if trs else float("nan")
    # Wilder's smoothing
    atr_val = sum(trs[:period]) / period
    for tr in trs[period:]:
        atr_val = (atr_val * (period - 1) + tr) / period
    return round(atr_val, 4)


def compute_all(bars: Sequence[MarketBar]) -> dict:
    """Compute all indicators for a bar series and return as dict."""
    bars_list = list(bars)
    return {
        "rsi": rsi(bars_list),
        "macd": macd(bars_list),
        "bollinger": bollinger_bands(bars_list),
        "atr": atr(bars_list),
    }
