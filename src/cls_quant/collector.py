"""Market data collector — fetches OHLCV data.

Uses yfinance when available; falls back to synthetic test data.
"""

from __future__ import annotations

import importlib.util
import math
import random
from datetime import datetime, timedelta, timezone
from typing import Optional

from cls_quant.schemas import MarketBar
from cls_quant.sources import ALL_TICKERS, WATCHLIST

_YFINANCE_AVAILABLE = importlib.util.find_spec("yfinance") is not None


def _synthetic_bars(ticker: str, days: int = 5) -> list[MarketBar]:
    """Generate deterministic synthetic OHLCV bars (for testing / offline use)."""
    random.seed(hash(ticker) % 10000)
    base = 100.0 + (hash(ticker) % 400)
    bars: list[MarketBar] = []
    today = datetime.now(timezone.utc).date()
    for i in range(days, 0, -1):
        date = today - timedelta(days=i)
        # Skip weekends
        if date.weekday() >= 5:
            continue
        change = (random.random() - 0.48) * 0.04
        open_ = round(base, 2)
        close = round(base * (1 + change), 2)
        high = round(max(open_, close) * (1 + random.random() * 0.02), 2)
        low = round(min(open_, close) * (1 - random.random() * 0.02), 2)
        volume = random.randint(500_000, 20_000_000)
        bars.append(
            MarketBar(
                ticker=ticker,
                date=date.isoformat(),
                open=open_,
                high=high,
                low=low,
                close=close,
                volume=float(volume),
                adj_close=close,
                metadata={"synthetic": True},
            )
        )
        base = close
    return bars


def _fetch_yfinance(ticker: str, period: str = "5d") -> list[MarketBar]:
    """Fetch OHLCV bars via yfinance."""
    import yfinance as yf  # type: ignore[import]

    hist = yf.Ticker(ticker).history(period=period, auto_adjust=True)
    bars: list[MarketBar] = []
    for idx, row in hist.iterrows():
        date_str = idx.strftime("%Y-%m-%d") if hasattr(idx, "strftime") else str(idx)[:10]
        bars.append(
            MarketBar(
                ticker=ticker,
                date=date_str,
                open=float(row.get("Open", 0)),
                high=float(row.get("High", 0)),
                low=float(row.get("Low", 0)),
                close=float(row.get("Close", 0)),
                volume=float(row.get("Volume", 0)),
                adj_close=float(row.get("Close", 0)),
            )
        )
    return bars


def fetch_ticker(
    ticker: str,
    period: str = "5d",
    use_synthetic: bool = False,
) -> list[MarketBar]:
    """Fetch OHLCV data for a single ticker.

    Falls back to synthetic data if yfinance is unavailable or fails.
    """
    if use_synthetic or not _YFINANCE_AVAILABLE:
        return _synthetic_bars(ticker)
    try:
        bars = _fetch_yfinance(ticker, period=period)
        if bars:
            return bars
    except Exception:
        pass
    return _synthetic_bars(ticker)


def fetch_watchlist(
    tickers: Optional[list[str]] = None,
    period: str = "5d",
    use_synthetic: bool = False,
) -> dict[str, list[MarketBar]]:
    """Fetch OHLCV data for a list of tickers.

    Returns dict mapping ticker → list[MarketBar].
    """
    if tickers is None:
        tickers = WATCHLIST
    result: dict[str, list[MarketBar]] = {}
    for ticker in tickers:
        try:
            result[ticker] = fetch_ticker(ticker, period=period, use_synthetic=use_synthetic)
        except Exception:
            result[ticker] = []
    return result


def compute_relative_volume(bars: list[MarketBar], lookback: int = 20) -> float:
    """Compute relative volume (latest vol / average of prior lookback bars).

    Returns ratio; > 1 = above average, < 1 = below.
    """
    if len(bars) < 2:
        return 1.0
    prior = bars[:-1][-lookback:]
    if not prior:
        return 1.0
    avg_vol = sum(b.volume for b in prior) / len(prior)
    if avg_vol == 0:
        return 1.0
    return round(bars[-1].volume / avg_vol, 3)
