"""FARA (Foreign Agents Registration Act) adapter.

Fetches and parses FARA filings from the DOJ FARA database.
In production, scrapes fara.gov/recent-filings.html.
Returns FaraRecord instances.
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from typing import Iterator

import requests
from bs4 import BeautifulSoup

from cls_osint.schemas import FaraRecord

FARA_BASE_URL = "https://www.fara.gov"
RECENT_FILINGS_URL = f"{FARA_BASE_URL}/recent-filings.html"
TIMEOUT = 20

_HEADERS = {
    "User-Agent": "spec1-engine/0.3 (research; contact: research@spec1.io)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# DOJ provides a structured JSON endpoint for recent filings
FARA_API_URL = "https://efile.fara.gov/api/v1/FilingFeed/json"


def _parse_date(date_str: str) -> datetime:
    """Parse various date formats returned by FARA sources."""
    date_str = date_str.strip()
    for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%B %d, %Y", "%b %d, %Y"):
        try:
            return datetime.strptime(date_str, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return datetime.now(timezone.utc)


def _make_record_id(registrant: str, foreign_principal: str, filed_at: str) -> str:
    raw = f"{registrant}::{foreign_principal}::{filed_at}"
    return "fara_" + hashlib.sha256(raw.encode()).hexdigest()[:12]


def _parse_activities_from_html(cell_text: str) -> list[str]:
    """Extract activity types from an HTML cell text."""
    known_activities = [
        "Political consulting",
        "Public relations",
        "Lobbying",
        "Dissemination of political propaganda",
        "Fundraising",
        "Legal representation",
        "Media outreach",
        "Government relations",
        "Financial consulting",
    ]
    found = []
    text_lower = cell_text.lower()
    for activity in known_activities:
        if activity.lower() in text_lower:
            found.append(activity)
    if not found and cell_text.strip():
        # Fall back to raw text
        found = [cell_text.strip()[:200]]
    return found or ["Unspecified"]


def fetch_recent_filings_html(
    url: str = RECENT_FILINGS_URL,
    timeout: int = TIMEOUT,
) -> list[FaraRecord]:
    """Scrape FARA recent filings page and return FaraRecord list."""
    resp = requests.get(url, headers=_HEADERS, timeout=timeout)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")
    records: list[FaraRecord] = []

    # FARA recent-filings page has a table with columns:
    # Registrant | Foreign Principal | Country | Date Filed | Document
    table = soup.find("table")
    if table is None:
        return records

    rows = table.find_all("tr")
    for row in rows[1:]:  # Skip header
        cells = row.find_all("td")
        if len(cells) < 5:
            continue
        registrant = cells[0].get_text(strip=True)
        foreign_principal = cells[1].get_text(strip=True)
        country = cells[2].get_text(strip=True)
        date_text = cells[3].get_text(strip=True)
        doc_link_tag = cells[4].find("a")
        doc_url = ""
        if doc_link_tag and doc_link_tag.get("href"):
            href = doc_link_tag["href"]
            doc_url = href if href.startswith("http") else FARA_BASE_URL + href

        if not registrant or not foreign_principal:
            continue

        filed_at = _parse_date(date_text)
        record_id = _make_record_id(registrant, foreign_principal, date_text)
        activities = _parse_activities_from_html(cells[4].get_text(strip=True))

        records.append(
            FaraRecord(
                record_id=record_id,
                registrant=registrant,
                foreign_principal=foreign_principal,
                country=country,
                activities=activities,
                filed_at=filed_at,
                doc_url=doc_url or RECENT_FILINGS_URL,
                registration_number="",
                status="active",
                metadata={"scraped_from": url},
            )
        )

    return records


def fetch_fara_api(
    url: str = FARA_API_URL,
    timeout: int = TIMEOUT,
    limit: int = 50,
) -> list[FaraRecord]:
    """Fetch FARA filings from the DOJ eFILE JSON API."""
    records: list[FaraRecord] = []
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        return records

    filings = data if isinstance(data, list) else data.get("filings", data.get("Filing", []))
    for item in filings[:limit]:
        registrant = item.get("RegistrantName", item.get("Registrant", ""))
        foreign_principal = item.get("ForeignPrincipalName", item.get("ForeignPrincipal", ""))
        country = item.get("Country", "")
        date_str = item.get("DateStamped", item.get("FiledDate", ""))
        doc_url = item.get("Url", item.get("DocumentUrl", FARA_BASE_URL))
        reg_num = str(item.get("RegistrationNumber", item.get("RegistrantNumber", "")))

        if not registrant:
            continue

        filed_at = _parse_date(date_str) if date_str else datetime.now(timezone.utc)
        record_id = _make_record_id(registrant, foreign_principal, date_str)
        activity_text = item.get("ActivityDescription", item.get("Exhibit", ""))
        activities = _parse_activities_from_html(activity_text) if activity_text else ["Unspecified"]

        records.append(
            FaraRecord(
                record_id=record_id,
                registrant=registrant,
                foreign_principal=foreign_principal,
                country=country,
                activities=activities,
                filed_at=filed_at,
                doc_url=doc_url,
                registration_number=reg_num,
                status="active",
                metadata={"api_item": item},
            )
        )

    return records


def collect(
    timeout: int = TIMEOUT,
    use_api: bool = True,
) -> list[FaraRecord]:
    """Main entry point — collect FARA records.

    Tries API first; falls back to HTML scrape.
    """
    if use_api:
        try:
            records = fetch_fara_api(timeout=timeout)
            if records:
                return records
        except Exception:
            pass
    try:
        return fetch_recent_filings_html(timeout=timeout)
    except Exception:
        return []


def iter_records(timeout: int = TIMEOUT) -> Iterator[FaraRecord]:
    """Yield FaraRecord instances from the FARA database."""
    for record in collect(timeout=timeout):
        yield record
