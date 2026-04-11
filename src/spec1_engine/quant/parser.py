"""Quant Parser — normalises OHLCV rows into Signal dataclasses.

Each row of a ticker's DataFrame becomes one Signal. The most recent row
(last trading day) is the primary signal; historical rows provide context
for relative-volume calculation.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone

import pandas as pd

from spec1_engine.schemas.models import Signal
from spec1_engine.quant.collector import TICKER_SECTOR

logger = logging.getLogger(__name__)

_LOOKBACK_DAYS = 30  # window for avg-volume baseline


def _signal_id(ticker: str, date: datetime) -> str:
    raw = f"{ticker}::{date.isoformat()}"
    return "q-" + hashlib.sha256(raw.encode()).hexdigest()[:14]


def _relative_volume(df: pd.DataFrame, idx: int) -> float:
    """Volume at row idx divided by 30-day average volume (excluding that row)."""
    try:
        col = _get_col(df, "Volume")
        if col is None:
            return 1.0
        start = max(0, idx - _LOOKBACK_DAYS)
        window = df[col].iloc[start:idx]
        avg = float(window.mean()) if len(window) > 0 else 0.0
        current = float(df[col].iloc[idx])
        return round(current / avg, 4) if avg > 0 else 1.0
    except Exception:
        return 1.0


def _daily_return(df: pd.DataFrame, idx: int) -> float:
    """(close[idx] - close[idx-1]) / close[idx-1]."""
    try:
        col = _get_col(df, "Close")
        if col is None or idx == 0:
            return 0.0
        prev = float(df[col].iloc[idx - 1])
        curr = float(df[col].iloc[idx])
        return round((curr - prev) / prev, 6) if prev != 0 else 0.0
    except Exception:
        return 0.0


def _get_col(df: pd.DataFrame, name: str):
    """Return the column for `name`, handling MultiIndex columns from yfinance."""
    if name in df.columns:
        return name
    # yfinance sometimes returns MultiIndex: (field, ticker)
    for col in df.columns:
        label = col[0] if isinstance(col, tuple) else col
        if str(label).lower() == name.lower():
            return col
    return None


def _get_val(df: pd.DataFrame, name: str, idx: int) -> float:
    col = _get_col(df, name)
    if col is None:
        return 0.0
    try:
        return float(df[col].iloc[idx])
    except Exception:
        return 0.0


def parse_row(
    ticker: str,
    df: pd.DataFrame,
    idx: int,
    run_id: str = "",
) -> Signal:
    """Convert one OHLCV row into a Signal."""
    ts = df.index[idx]
    if hasattr(ts, "to_pydatetime"):
        published_at = ts.to_pydatetime()
    else:
        published_at = datetime.fromtimestamp(float(ts), tz=timezone.utc)
    if published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=timezone.utc)

    close  = _get_val(df, "Close",  idx)
    open_  = _get_val(df, "Open",   idx)
    high   = _get_val(df, "High",   idx)
    low    = _get_val(df, "Low",    idx)
    volume = _get_val(df, "Volume", idx)

    daily_ret = _daily_return(df, idx)
    rel_vol   = _relative_volume(df, idx)
    sector    = TICKER_SECTOR.get(ticker, "unknown")
    date_str  = published_at.strftime("%Y-%m-%d")

    return Signal(
        signal_id=_signal_id(ticker, published_at),
        source=ticker,
        source_type="market_data",
        text=f"{ticker} — close={close:.4f}, vol={int(volume):,}, date={date_str}",
        url=f"https://finance.yahoo.com/quote/{ticker}",
        author="yfinance",
        published_at=published_at,
        velocity=daily_ret,
        engagement=rel_vol,
        run_id=run_id,
        environment="quant",
        metadata={
            "ticker": ticker,
            "sector": sector,
            "open":   open_,
            "high":   high,
            "low":    low,
            "close":  close,
            "volume": int(volume),
            "daily_return": daily_ret,
            "relative_volume": rel_vol,
        },
    )


def parse_dataframe(
    ticker: str,
    df: pd.DataFrame,
    run_id: str = "",
    latest_only: bool = True,
) -> list[Signal]:
    """Parse a full OHLCV DataFrame into Signal instances.

    When latest_only=True (default), only the most recent row is returned.
    Pass latest_only=False to get one Signal per row (for backtesting).
    """
    if df.empty:
        return []
    indices = [len(df) - 1] if latest_only else list(range(len(df)))
    signals: list[Signal] = []
    for idx in indices:
        try:
            signals.append(parse_row(ticker, df, idx, run_id=run_id))
        except Exception as exc:
            logger.error("Failed to parse row %d for %s: %s", idx, ticker, exc)
    return signals
