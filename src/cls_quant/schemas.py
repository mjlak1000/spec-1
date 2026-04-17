"""Data schemas for cls_quant."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class MarketBar:
    """A single OHLCV bar for a ticker."""

    ticker: str
    date: str           # ISO date "YYYY-MM-DD"
    open: float
    high: float
    low: float
    close: float
    volume: float
    adj_close: float = 0.0
    metadata: dict = field(default_factory=dict)

    @property
    def daily_return(self) -> float:
        """Percentage return: (close - open) / open."""
        if self.open == 0:
            return 0.0
        return round((self.close - self.open) / self.open, 6)

    def to_dict(self) -> dict:
        return {
            "ticker": self.ticker,
            "date": self.date,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
            "adj_close": self.adj_close,
            "daily_return": self.daily_return,
            "metadata": self.metadata,
        }


@dataclass
class QuantSignal:
    """A scored market signal derived from one or more MarketBars."""

    signal_id: str
    ticker: str
    pattern: str           # e.g. "HIGH_VOL_BREAKOUT", "MOMENTUM_UP"
    score: float           # 0–1
    gate_results: dict     # {"credibility": bool, "volume": bool, "velocity": bool, "novelty": bool}
    triggered_at: datetime = field(default_factory=_now)
    bar: MarketBar | None = None
    indicators: dict = field(default_factory=dict)   # RSI, MACD, etc.
    metadata: dict = field(default_factory=dict)

    @classmethod
    def make_id(cls, ticker: str, pattern: str, date: str) -> str:
        raw = f"{ticker}::{pattern}::{date}"
        return "qsig_" + hashlib.sha256(raw.encode()).hexdigest()[:12]

    def to_dict(self) -> dict:
        return {
            "signal_id": self.signal_id,
            "ticker": self.ticker,
            "pattern": self.pattern,
            "score": self.score,
            "gate_results": self.gate_results,
            "triggered_at": self.triggered_at.isoformat()
            if isinstance(self.triggered_at, datetime)
            else str(self.triggered_at),
            "bar": self.bar.to_dict() if self.bar else None,
            "indicators": self.indicators,
            "metadata": self.metadata,
        }
