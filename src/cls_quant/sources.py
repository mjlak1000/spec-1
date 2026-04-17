"""Ticker watchlists for cls_quant."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class TickerMeta:
    ticker: str
    name: str
    sector: str
    tags: list[str] = field(default_factory=list)
    credibility: float = 0.8   # 0–1; higher = more liquid / reliable


# Defence & Aerospace
DEFENSE_TICKERS: dict[str, TickerMeta] = {
    "LMT": TickerMeta("LMT", "Lockheed Martin", "defense", ["missiles", "aircraft", "space"]),
    "RTX": TickerMeta("RTX", "RTX Corporation (Raytheon)", "defense", ["missiles", "sensors"]),
    "NOC": TickerMeta("NOC", "Northrop Grumman", "defense", ["cyber", "space", "stealth"]),
    "GD": TickerMeta("GD", "General Dynamics", "defense", ["submarines", "IT"]),
    "BA": TickerMeta("BA", "Boeing", "aerospace", ["aircraft", "defense"]),
    "HII": TickerMeta("HII", "Huntington Ingalls", "defense", ["ships", "nuclear"]),
    "L3H": TickerMeta("L3H", "L3Harris Technologies", "defense", ["comms", "intel"]),
    "LDOS": TickerMeta("LDOS", "Leidos", "defense", ["IT", "intelligence"]),
    "SAIC": TickerMeta("SAIC", "Science Applications International", "defense", ["IT", "government"]),
    "DRS": TickerMeta("DRS", "Leonardo DRS", "defense", ["electronics", "sensors"]),
}

# Cyber Security
CYBER_TICKERS: dict[str, TickerMeta] = {
    "CRWD": TickerMeta("CRWD", "CrowdStrike", "cyber", ["EDR", "threat intel"], credibility=0.9),
    "PANW": TickerMeta("PANW", "Palo Alto Networks", "cyber", ["NGFW", "cloud"], credibility=0.9),
    "FTNT": TickerMeta("FTNT", "Fortinet", "cyber", ["network security"], credibility=0.85),
    "S": TickerMeta("S", "SentinelOne", "cyber", ["AI security"], credibility=0.8),
    "ZS": TickerMeta("ZS", "Zscaler", "cyber", ["zero trust", "cloud"], credibility=0.85),
    "HACK": TickerMeta("HACK", "ETFMG Prime Cyber Security ETF", "cyber", ["etf"], credibility=0.75),
}

# Energy & Critical Infrastructure
ENERGY_TICKERS: dict[str, TickerMeta] = {
    "XOM": TickerMeta("XOM", "ExxonMobil", "energy", ["oil", "gas"], credibility=0.85),
    "CVX": TickerMeta("CVX", "Chevron", "energy", ["oil", "gas"], credibility=0.85),
    "OXY": TickerMeta("OXY", "Occidental Petroleum", "energy", ["oil"], credibility=0.8),
    "NEE": TickerMeta("NEE", "NextEra Energy", "energy", ["nuclear", "renewables"], credibility=0.8),
    "SO": TickerMeta("SO", "Southern Company", "energy", ["utility", "nuclear"], credibility=0.8),
}

# Macro / Market Intelligence
MACRO_TICKERS: dict[str, TickerMeta] = {
    "SPY": TickerMeta("SPY", "S&P 500 ETF", "macro", ["etf", "broad market"], credibility=0.95),
    "TLT": TickerMeta("TLT", "iShares 20+ Year Treasury", "macro", ["bonds", "rates"], credibility=0.95),
    "GLD": TickerMeta("GLD", "SPDR Gold Shares", "macro", ["gold", "safe haven"], credibility=0.95),
    "VIX": TickerMeta("VIX", "CBOE Volatility Index", "macro", ["volatility", "fear"], credibility=0.95),
    "DXY": TickerMeta("DXY", "US Dollar Index", "macro", ["fx", "dollar"], credibility=0.9),
    "USO": TickerMeta("USO", "United States Oil Fund", "macro", ["oil", "commodity"], credibility=0.85),
}

# All tickers combined
ALL_TICKERS: dict[str, TickerMeta] = {
    **DEFENSE_TICKERS,
    **CYBER_TICKERS,
    **ENERGY_TICKERS,
    **MACRO_TICKERS,
}

WATCHLIST: list[str] = sorted(ALL_TICKERS.keys())


def get_meta(ticker: str) -> TickerMeta | None:
    return ALL_TICKERS.get(ticker.upper())


def get_by_sector(sector: str) -> list[TickerMeta]:
    return [m for m in ALL_TICKERS.values() if m.sector == sector]


def get_credibility(ticker: str) -> float:
    meta = ALL_TICKERS.get(ticker.upper())
    return meta.credibility if meta else 0.5
