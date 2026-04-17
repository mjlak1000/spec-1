"""Congressional records adapter.

Fetches US Congressional bills, resolutions, and hearings from:
- congress.gov RSS feed
- govtrack.us RSS feed

Returns CongressRecord instances.
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from typing import Iterator

import feedparser
import requests

from cls_osint.schemas import CongressRecord

CONGRESS_RSS_URL = "https://www.congress.gov/rss/legislation.xml"
GOVTRACK_RSS_URL = "https://www.govtrack.us/congress/bills/feed"
TIMEOUT = 15

_HEADERS = {"User-Agent": "spec1-engine/0.3"}

# Patterns for extracting bill IDs
_BILL_ID_RE = re.compile(
    r"\b(H\.R\.|S\.|H\.J\.Res\.|S\.J\.Res\.|H\.Con\.Res\.|S\.Con\.Res\.|H\.Res\.|S\.Res\.)\s*(\d+)\b",
    re.IGNORECASE,
)
_HEARING_RE = re.compile(r"\bhearing\b", re.IGNORECASE)

# Defense/national-security related keywords
_DEFENSE_TAGS = {
    "defense": ["defense", "military", "pentagon", "armed forces", "DoD"],
    "intelligence": ["intelligence", "cia", "nsa", "dni", "covert"],
    "cyber": ["cyber", "cybersecurity", "information operations"],
    "foreign_policy": ["foreign", "diplomatic", "embassy", "treaty", "sanctions"],
    "homeland": ["homeland", "DHS", "border", "immigration"],
    "budget": ["authorization", "appropriation", "NDAA", "budget"],
}


def _make_record_id(bill_id: str, date_str: str) -> str:
    raw = f"{bill_id}::{date_str}"
    return "congress_" + hashlib.sha256(raw.encode()).hexdigest()[:12]


def _parse_date(entry: feedparser.FeedParserDict) -> datetime:
    for attr in ("published_parsed", "updated_parsed"):
        val = getattr(entry, attr, None)
        if val:
            try:
                return datetime(*val[:6], tzinfo=timezone.utc)
            except Exception:
                pass
    return datetime.now(timezone.utc)


def _extract_bill_id(text: str) -> str:
    """Extract first matching bill ID from text."""
    m = _BILL_ID_RE.search(text)
    if m:
        return m.group(0).replace(" ", "")
    return ""


def _classify_record_type(title: str, summary: str) -> str:
    """Classify record as bill, resolution, hearing, or amendment."""
    combined = (title + " " + summary).lower()
    if "hearing" in combined:
        return "HEARING"
    if "joint resolution" in combined or "j.res" in combined.lower():
        return "RESOLUTION"
    if "concurrent resolution" in combined or "con.res" in combined.lower():
        return "RESOLUTION"
    if "resolution" in combined:
        return "RESOLUTION"
    if "amendment" in combined:
        return "AMENDMENT"
    return "BILL"


def _extract_tags(text: str) -> list[str]:
    """Extract relevant topic tags from text."""
    tags: list[str] = []
    text_lower = text.lower()
    for tag, keywords in _DEFENSE_TAGS.items():
        if any(kw.lower() in text_lower for kw in keywords):
            tags.append(tag)
    return tags


def _extract_sponsor(summary: str) -> str:
    """Attempt to extract sponsor name from summary text."""
    # Pattern: "introduced by [Rep.|Sen.] Name"
    patterns = [
        r"introduced by (?:Rep\.|Sen\.|Representative|Senator)\s+([A-Z][a-z]+(?: [A-Z][a-z]+){1,3})",
        r"(?:Rep\.|Sen\.)\s+([A-Z][a-z]+(?: [A-Z][a-z]+){1,3})\s+introduced",
        r"Sponsor:\s*([A-Z][a-z]+(?: [A-Z][a-z]+){1,3})",
    ]
    for pat in patterns:
        m = re.search(pat, summary)
        if m:
            return m.group(1)
    return "UNKNOWN"


def _extract_chamber(title: str, bill_id: str) -> str:
    """Determine chamber from bill ID or title."""
    combined = (title + " " + bill_id).upper()
    if any(x in combined for x in ("H.R.", "H.J.", "H.CON.", "H.RES.")):
        return "HOUSE"
    if any(x in combined for x in ("S.", "S.J.", "S.CON.", "S.RES.")):
        return "SENATE"
    if "HOUSE" in combined:
        return "HOUSE"
    if "SENATE" in combined:
        return "SENATE"
    return "UNKNOWN"


def _extract_status(summary: str) -> str:
    """Infer bill status from summary text."""
    text = summary.lower()
    if any(kw in text for kw in ("signed into law", "enacted", "became law")):
        return "ENACTED"
    if "passed senate" in text:
        return "PASSED_SENATE"
    if "passed house" in text:
        return "PASSED_HOUSE"
    if any(kw in text for kw in ("failed", "rejected", "defeated", "died")):
        return "FAILED"
    return "INTRODUCED"


def fetch_congress_rss(
    url: str = CONGRESS_RSS_URL,
    timeout: int = TIMEOUT,
) -> list[CongressRecord]:
    """Fetch legislation from congress.gov RSS feed."""
    records: list[CongressRecord] = []
    try:
        parsed = feedparser.parse(url, request_headers=_HEADERS)
    except Exception:
        return records

    for entry in parsed.get("entries", []):
        title = getattr(entry, "title", "") or ""
        link = getattr(entry, "link", "") or ""
        summary = getattr(entry, "summary", "") or getattr(entry, "description", "") or ""
        date = _parse_date(entry)

        if not title:
            continue

        bill_id = _extract_bill_id(title + " " + summary) or title[:50]
        record_id = _make_record_id(bill_id, date.isoformat())
        chamber = _extract_chamber(title, bill_id)
        record_type = _classify_record_type(title, summary)
        status = _extract_status(summary)
        sponsor = _extract_sponsor(summary)
        tags = _extract_tags(title + " " + summary)

        records.append(
            CongressRecord(
                record_id=record_id,
                record_type=record_type,
                bill_id=bill_id,
                title=title,
                sponsor=sponsor,
                chamber=chamber,
                status=status,
                date=date,
                summary=summary[:500],
                url=link,
                tags=tags,
                metadata={"feed": url},
            )
        )

    return records


def fetch_govtrack_rss(
    url: str = GOVTRACK_RSS_URL,
    timeout: int = TIMEOUT,
) -> list[CongressRecord]:
    """Fetch legislation from govtrack.us RSS feed."""
    records: list[CongressRecord] = []
    try:
        parsed = feedparser.parse(url, request_headers=_HEADERS)
    except Exception:
        return records

    for entry in parsed.get("entries", []):
        title = getattr(entry, "title", "") or ""
        link = getattr(entry, "link", "") or ""
        summary = getattr(entry, "summary", "") or getattr(entry, "description", "") or ""
        date = _parse_date(entry)

        if not title:
            continue

        bill_id = _extract_bill_id(title + " " + link) or title[:50]
        record_id = _make_record_id(bill_id + "_govtrack", date.isoformat())
        chamber = _extract_chamber(title, bill_id)
        record_type = _classify_record_type(title, summary)
        status = _extract_status(summary)
        sponsor = _extract_sponsor(summary)
        tags = _extract_tags(title + " " + summary)

        records.append(
            CongressRecord(
                record_id=record_id,
                record_type=record_type,
                bill_id=bill_id,
                title=title,
                sponsor=sponsor,
                chamber=chamber,
                status=status,
                date=date,
                summary=summary[:500],
                url=link,
                tags=tags,
                metadata={"feed": url, "source": "govtrack"},
            )
        )

    return records


def collect(timeout: int = TIMEOUT) -> list[CongressRecord]:
    """Collect congressional records from all sources."""
    records: list[CongressRecord] = []
    seen_ids: set[str] = set()

    for fetcher in (fetch_congress_rss, fetch_govtrack_rss):
        try:
            batch = fetcher(timeout=timeout)
            for r in batch:
                if r.record_id not in seen_ids:
                    seen_ids.add(r.record_id)
                    records.append(r)
        except Exception:
            pass

    return records


def iter_records(timeout: int = TIMEOUT) -> Iterator[CongressRecord]:
    """Yield CongressRecord instances from all congressional sources."""
    for record in collect(timeout=timeout):
        yield record
