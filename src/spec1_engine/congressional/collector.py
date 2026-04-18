"""Congressional trade collector — 3-source fallback chain.

Source 1: Quiver Quantitative API  (QUIVER_API_KEY env var required)
Source 2: Capitol Trades HTML scraper
Source 3: Built-in sample data (3 hardcoded trades)

Never raises. Returns list of raw dicts with keys:
  politician, ticker, amount, trade_type, trade_date, committee, source
"""

from __future__ import annotations

import logging
import os
import re
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

QUIVER_URL = "https://api.quiverquant.com/beta/live/congresstrading"
CAPITOL_TRADES_URL = "https://capitoltrades.com/trades"

# ─── Sample data ──────────────────────────────────────────────────────────────

def _recent(days_ago: int) -> str:
    from datetime import timedelta
    dt = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return dt.strftime("%Y-%m-%d")


SAMPLE_TRADES: list[dict] = [
    {
        "politician": "Sen. John Smith",
        "ticker": "LMT",
        "amount": 15001,
        "trade_type": "Purchase",
        "trade_date": _recent(8),
        "committee": "Armed Services",
        "source": "sample",
    },
    {
        "politician": "Rep. Jane Doe",
        "ticker": "PANW",
        "amount": 265000,
        "trade_type": "Purchase",
        "trade_date": _recent(4),
        "committee": "Homeland Security",
        "source": "sample",
    },
    {
        "politician": "Sen. Bob Johnson",
        "ticker": "RTX",
        "amount": 50000,
        "trade_type": "Sale",
        "trade_date": _recent(22),
        "committee": "Intelligence",
        "source": "sample",
    },
]


# ─── Amount parsing ───────────────────────────────────────────────────────────

def _parse_amount(raw: str) -> int:
    """Parse an amount string like '$1,001 - $15,000' or '15001' to midpoint int."""
    cleaned = re.sub(r"[$,\s]", "", str(raw))
    nums = [int(x) for x in re.findall(r"\d+", cleaned)]
    if not nums:
        return 0
    return int(sum(nums) / len(nums))


# ─── Source 1: Quiver Quantitative ───────────────────────────────────────────

def _fetch_quiver() -> list[dict]:
    """Fetch from Quiver Quantitative congressional trading endpoint.

    Raises:
        EnvironmentError: If QUIVER_API_KEY is not set.
        requests.RequestException: On HTTP failure.
    """
    import requests

    api_key = os.environ.get("QUIVER_API_KEY", "")
    if not api_key:
        raise EnvironmentError("QUIVER_API_KEY not set")

    headers = {
        "Accept": "application/json",
        "X-CSRFToken": api_key,
        "Cookie": f"csrftoken={api_key}",
    }
    resp = requests.get(QUIVER_URL, headers=headers, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    result = []
    for item in data if isinstance(data, list) else []:
        result.append({
            "politician": str(item.get("Representative", "")),
            "ticker": str(item.get("Ticker", "")).upper(),
            "amount": _parse_amount(str(item.get("Amount", "0"))),
            "trade_type": str(item.get("Transaction", "")),
            "trade_date": str(item.get("TransactionDate", "")),
            "committee": str(item.get("Committee", "")),
            "source": "quiver",
        })
    return result


# ─── Source 2: Capitol Trades HTML scraper ────────────────────────────────────

def _text(cell: str) -> str:
    return re.sub(r"<[^>]+>", " ", cell).strip()


def _fetch_capitol_trades() -> list[dict]:
    """Scrape recent trades from Capitol Trades HTML table.

    Raises:
        requests.RequestException: On HTTP failure.
    """
    import requests

    resp = requests.get(
        CAPITOL_TRADES_URL,
        timeout=15,
        headers={"User-Agent": "Mozilla/5.0 (compatible; SPEC-1/0.2)"},
    )
    resp.raise_for_status()

    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", resp.text, re.DOTALL | re.IGNORECASE)
    result = []
    for row in rows[1:]:  # skip header row
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.DOTALL | re.IGNORECASE)
        if len(cells) < 5:
            continue
        record = {
            "politician": _text(cells[0]),
            "ticker": _text(cells[1]).upper()[:10],
            "amount": _parse_amount(_text(cells[2])),
            "trade_type": _text(cells[3]),
            "trade_date": _text(cells[4]),
            "committee": _text(cells[5]) if len(cells) > 5 else "",
            "source": "capitol_trades",
        }
        if record["politician"] and record["ticker"]:
            result.append(record)
    return result


# ─── Public entry point ───────────────────────────────────────────────────────

def fetch_trades() -> list[dict]:
    """Collect congressional trade data using a 3-source fallback chain.

    Tries sources in order:
      1. Quiver Quantitative API  (requires QUIVER_API_KEY env var)
      2. Capitol Trades HTML scraper
      3. Built-in sample data

    Never raises. Returns a list of normalized raw dicts.
    """
    # Source 1 — Quiver
    try:
        trades = _fetch_quiver()
        if trades:
            logger.info("Quiver: fetched %d congressional trades", len(trades))
            return trades
        logger.warning("Quiver returned empty list — trying Capitol Trades")
    except Exception as exc:
        logger.warning("Quiver fetch failed (%s) — trying Capitol Trades", exc)

    # Source 2 — Capitol Trades
    try:
        trades = _fetch_capitol_trades()
        if trades:
            logger.info("Capitol Trades: scraped %d records", len(trades))
            return trades
        logger.warning("Capitol Trades returned empty list — using sample data")
    except Exception as exc:
        logger.warning("Capitol Trades scrape failed (%s) — using sample data", exc)

    # Source 3 — sample fallback
    logger.info("Using built-in sample congressional trades (%d records)", len(SAMPLE_TRADES))
    return list(SAMPLE_TRADES)
