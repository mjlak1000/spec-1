"""Congressional trade parser — normalizes raw dicts into Signal dataclasses.

source_type : "congressional_trade"
velocity    : 1.0 if trade within 7 days, else 0.5
engagement  : log10(amount) / 7.0 if amount > 0, else 0.1
environment : "congressional"
"""

from __future__ import annotations

import hashlib
import math
from datetime import datetime, timezone
from typing import Optional

from spec1_engine.schemas.models import Signal

SEVEN_DAYS_S = 7 * 86_400

_DATE_FORMATS = ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%B %d, %Y", "%b %d, %Y")


def _signal_id(politician: str, ticker: str, date_str: str) -> str:
    raw = f"{politician}::{ticker}::{date_str}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _parse_date(date_str: str) -> Optional[datetime]:
    """Try multiple date formats; return UTC-aware datetime or None."""
    for fmt in _DATE_FORMATS:
        try:
            dt = datetime.strptime(date_str.strip(), fmt)
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _velocity(trade_date: datetime) -> float:
    """1.0 if trade within 7 days of now, else 0.5."""
    age_s = (datetime.now(timezone.utc) - trade_date).total_seconds()
    return 1.0 if age_s <= SEVEN_DAYS_S else 0.5


def _engagement(amount: int) -> float:
    """log10(amount) / 7.0 — normalized trade size proxy. 0.1 if amount <= 0."""
    if amount <= 0:
        return 0.1
    return round(math.log10(amount) / 7.0, 4)


def _trade_text(raw: dict) -> str:
    return (
        f"{raw.get('politician', 'Unknown')} reported a "
        f"{raw.get('trade_type', 'trade')} of {raw.get('ticker', '?')} "
        f"worth approximately ${raw.get('amount', 0):,} "
        f"on {raw.get('trade_date', 'unknown date')}. "
        f"Committee: {raw.get('committee', 'None')}. "
        f"Data source: {raw.get('source', 'unknown')}."
    )


def parse_trade(
    raw: dict,
    run_id: str = "",
    environment: str = "congressional",
) -> Optional[Signal]:
    """Normalize a raw congressional trade dict into a Signal.

    Args:
        raw: Dict with keys: politician, ticker, amount, trade_type,
             trade_date, committee, source.
        run_id: Run identifier for traceability.
        environment: Environment label.

    Returns:
        Signal instance, or None if the record cannot be parsed.
    """
    try:
        politician = str(raw.get("politician", "")).strip()
        ticker = str(raw.get("ticker", "")).strip().upper()
        amount = int(raw.get("amount", 0))
        trade_type = str(raw.get("trade_type", "")).strip()
        date_str = str(raw.get("trade_date", "")).strip()
        committee = str(raw.get("committee", "")).strip()
        source = str(raw.get("source", "unknown")).strip()

        if not politician or not ticker:
            return None

        trade_date = _parse_date(date_str) or datetime.now(timezone.utc)

        return Signal(
            signal_id=_signal_id(politician, ticker, date_str),
            source=source,
            source_type="congressional_trade",
            text=_trade_text({**raw, "amount": amount}),
            url=(
                f"https://efts.sec.gov/LATEST/search-index"
                f"?q=%22{ticker}%22&dateRange=custom"
            ),
            author=politician,
            published_at=trade_date,
            velocity=_velocity(trade_date),
            engagement=_engagement(amount),
            run_id=run_id,
            environment=environment,
            metadata={
                "politician": politician,
                "ticker": ticker,
                "amount": amount,
                "trade_type": trade_type,
                "committee": committee,
                "source": source,
                "trade_date": date_str,
            },
        )
    except Exception:
        return None


def parse_batch(
    raw_trades: list[dict],
    run_id: str = "",
    environment: str = "congressional",
) -> list[Signal]:
    """Parse a list of raw trade dicts into Signals, silently skipping failures.

    Args:
        raw_trades: List of raw trade dicts from the collector.
        run_id: Run identifier.
        environment: Environment label.

    Returns:
        List of successfully parsed Signal instances.
    """
    signals = []
    for raw in raw_trades:
        sig = parse_trade(raw, run_id=run_id, environment=environment)
        if sig is not None:
            signals.append(sig)
    return signals
