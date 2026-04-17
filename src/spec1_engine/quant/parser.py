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


def _relative_volume(df: pd.DataFrame, idx: int | None = None) -> float:
    """Volume at `idx` divided by rolling 30-day average up to that row."""
    try:
        col = _get_col(df, "Volume")
        if col is None or len(df) == 0:
            return 1.0
        row = len(df) - 1 if idx is None else idx
        vol_series = df[col]
        if isinstance(vol_series, pd.DataFrame):
            vol_series = vol_series.iloc[:, 0]
        series_up_to = vol_series.iloc[:row + 1]
        if len(series_up_to) < 2:
            return 1.0
        rolling_avg = series_up_to.rolling(window=30, min_periods=1).mean()
        avg = float(rolling_avg.iloc[-1])
        current = float(series_up_to.iloc[-1])
        return round(current / avg, 4) if avg > 0 else 1.0
    except Exception:
        return 1.0


def _daily_return(df: pd.DataFrame, idx: int | None = None) -> float:
    """(close[idx] - close[idx-1]) / close[idx-1]. Returns 0.0 when idx == 0."""
    try:
        col = _get_col(df, "Close")
        row = len(df) - 1 if idx is None else idx
        if col is None or row == 0:
            return 0.0
        close_series = df[col]
        if isinstance(close_series, pd.DataFrame):
            close_series = close_series.iloc[:, 0]
        prev = float(close_series.iloc[row - 1])
        curr = float(close_series.iloc[row])
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
    idx: int | None = None,
    run_id: str = "",
) -> Signal:
    """Convert an OHLCV row into a Signal. Uses last row when idx is None."""
    if df.empty:
        raise ValueError(f"DataFrame for {ticker} is empty")

    row = len(df) - 1 if idx is None else idx
    # alias so downstream references still work
    idx = row
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

    When latest_only=True (default), only the most recent row is returned
    (but using full historical data for velocity/volume calculations).
    Pass latest_only=False to get one Signal per row (for backtesting).
    """
    if df.empty:
        return []

    signals: list[Signal] = []

    if latest_only:
        # Return only the latest row, but pass the full DataFrame for calculations
        try:
            signals.append(parse_row(ticker, df, run_id=run_id))
        except Exception as exc:
            logger.error("Failed to parse latest row for %s: %s", ticker, exc)
    else:
        # For backtesting: one Signal per row using history up to that row
        for i in range(len(df)):
            df_slice = df.iloc[:i + 1].copy()
            try:
                signals.append(parse_row(ticker, df_slice, run_id=run_id))
            except Exception as exc:
                logger.error("Failed to parse row %d for %s: %s", i, ticker, exc)

    return signals
