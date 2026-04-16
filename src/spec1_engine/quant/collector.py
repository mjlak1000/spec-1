"""Quant Collector — fetches OHLCV data via yfinance.

Each ticker in the watchlist is fetched independently. Failures are logged
and skipped — the collector never crashes the cycle.
"""

from __future__ import annotations

import logging

try:
    import pandas as pd
    import yfinance as yf
    _YFINANCE_AVAILABLE = True
except ImportError:
    pd = None  # type: ignore[assignment]
    yf = None  # type: ignore[assignment]
    _YFINANCE_AVAILABLE = False

logger = logging.getLogger(__name__)

# ── Watchlist ──────────────────────────────────────────────────────────────────

WATCHLIST: dict[str, list[str]] = {
    "defense":  ["LMT", "RTX", "NOC", "GD", "BA"],
    "cyber":    ["PANW", "CRWD", "S", "FTNT"],
    "energy":   ["XOM", "CVX", "SLB"],
    "macro":    ["SPY", "GLD", "TLT", "DX-Y.NYB"],
}

# Flat set of all watched tickers for O(1) gate lookup
ALL_TICKERS: set[str] = {t for tickers in WATCHLIST.values() for t in tickers}

# Sector lookup — used by parser metadata
TICKER_SECTOR: dict[str, str] = {
    t: sector
    for sector, tickers in WATCHLIST.items()
    for t in tickers
}


def fetch_ohlcv(
    ticker: str,
    period: str = "3mo",
    interval: str = "1d",
):
    """Fetch OHLCV DataFrame for a single ticker.

    Returns an empty DataFrame on any yfinance error.
    """
    if not _YFINANCE_AVAILABLE:
        return pd.DataFrame() if pd else type("DF", (), {"empty": True})()
    try:
        df = yf.download(
            ticker,
            period=period,
            interval=interval,
            progress=False,
            auto_adjust=True,
        )
        if df is None or df.empty:
            logger.warning("No data returned for %s", ticker)
            return pd.DataFrame()
        df = df.copy()
        df.index = pd.to_datetime(df.index, utc=True)
        return df
    except Exception as exc:
        logger.error("yfinance fetch failed for %s: %s", ticker, exc)
        return pd.DataFrame()


def fetch_all(
    tickers: list[str] | None = None,
    period: str = "3mo",
    interval: str = "1d",
) -> dict[str, pd.DataFrame]:
    """Fetch OHLCV for every ticker in the watchlist (or a custom list).

    Returns {ticker: DataFrame}. Empty DataFrames are excluded from the result.
    """
    if tickers is None:
        tickers = sorted(ALL_TICKERS)

    results: dict[str, pd.DataFrame] = {}
    for ticker in tickers:
        df = fetch_ohlcv(ticker, period=period, interval=interval)
        if not df.empty:
            results[ticker] = df
        else:
            logger.warning("Skipping %s — empty result", ticker)

    logger.info("Collected OHLCV for %d/%d tickers", len(results), len(tickers))
    return results
