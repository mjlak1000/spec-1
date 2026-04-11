"""RSS Harvester — ported from cls_osint/collectors/rss.py.

Fetches RSS feeds using feedparser and produces Signal dataclass instances.
Sources: War on the Rocks, Cipher Brief, Lawfare, RAND, Atlantic Council, Defense One.
"""

from __future__ import annotations

import hashlib
import re
import ssl
import urllib.request
from datetime import datetime, timezone
from typing import Iterator, Optional

import feedparser
import requests

from spec1_engine.schemas.models import Signal

DEFAULT_FEEDS: dict[str, str] = {
    "war_on_the_rocks": "https://warontherocks.com/feed/",
    "cipher_brief": "https://www.thecipherbrief.com/feed",
    "just_security": "https://www.justsecurity.org/feed/",
    "rand": "https://www.rand.org/blog.xml",
    "atlantic_council": "https://www.atlanticcouncil.org/feed/",
    "defense_one": "https://www.defenseone.com/rss/all/",
}

TIMEOUT = 15
_HEADERS = {"User-Agent": "spec1-engine/0.2"}

# Sources that need SSL verification disabled (cert chain issues on this host)
_SSL_UNVERIFIED = {"cipher_brief"}

# Sources whose feeds contain stray invalid XML characters that need scrubbing
_SANITIZE_XML: set[str] = set()

# Regex matching XML-illegal control characters (except tab/LF/CR)
_ILLEGAL_XML_RE = re.compile(
    r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f"
    r"\ud800-\udfff"
    r"\ufffe\uffff]"
)


def _make_signal_id(url: str, title: str) -> str:
    raw = f"{url}::{title}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _parse_date(entry: feedparser.FeedParserDict) -> datetime:
    """Extract published datetime from a feedparser entry."""
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        try:
            t = entry.published_parsed
            return datetime(*t[:6], tzinfo=timezone.utc)
        except Exception:
            pass
    if hasattr(entry, "updated_parsed") and entry.updated_parsed:
        try:
            t = entry.updated_parsed
            return datetime(*t[:6], tzinfo=timezone.utc)
        except Exception:
            pass
    return datetime.now(timezone.utc)


def _get_text(entry: feedparser.FeedParserDict) -> str:
    """Extract text content from a feedparser entry."""
    parts = []
    if hasattr(entry, "title") and entry.title:
        parts.append(str(entry.title))
    if hasattr(entry, "summary") and entry.summary:
        parts.append(str(entry.summary))
    elif hasattr(entry, "description") and entry.description:
        parts.append(str(entry.description))
    if hasattr(entry, "content") and entry.content:
        for c in entry.content:
            if hasattr(c, "value") and c.value:
                parts.append(str(c.value))
                break
    return " ".join(parts)


def _get_author(entry: feedparser.FeedParserDict) -> str:
    if hasattr(entry, "author") and entry.author:
        return str(entry.author)
    if hasattr(entry, "author_detail") and entry.author_detail:
        return str(entry.author_detail.get("name", ""))
    return ""


_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/rss+xml, application/xml, text/xml, */*",
}


def _fetch_raw_sanitized(url: str, timeout: int) -> bytes:
    """Fetch URL with requests, strip illegal XML control chars, return bytes."""
    resp = requests.get(url, headers=_BROWSER_HEADERS, timeout=timeout, verify=True)
    resp.raise_for_status()
    text = resp.text
    text = _ILLEGAL_XML_RE.sub("", text)
    return text.encode("utf-8")


def _fetch_raw_no_ssl(url: str, timeout: int) -> bytes:
    """Fetch URL ignoring SSL verification errors, return raw bytes."""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    req = urllib.request.Request(url, headers=_HEADERS)
    with urllib.request.urlopen(req, context=ctx, timeout=timeout) as resp:
        return resp.read()


def _parse_feed(name: str, url: str, timeout: int) -> feedparser.FeedParserDict:
    """Return a feedparser result, applying source-specific workarounds."""
    if name in _SSL_UNVERIFIED:
        raw = _fetch_raw_no_ssl(url, timeout)
        return feedparser.parse(raw)

    if name in _SANITIZE_XML:
        raw = _fetch_raw_sanitized(url, timeout)
        return feedparser.parse(raw)

    return feedparser.parse(url, request_headers=_HEADERS)


def fetch_feed(
    name: str,
    url: str,
    run_id: str = "",
    environment: str = "production",
    timeout: int = TIMEOUT,
) -> Iterator[Signal]:
    """Fetch a single RSS feed and yield Signal instances."""
    parsed = _parse_feed(name, url, timeout)

    if parsed.get("bozo") and not parsed.get("entries"):
        bozo_exc = parsed.get("bozo_exception")
        if bozo_exc:
            raise RuntimeError(f"Failed to parse feed {name}: {bozo_exc}")

    for entry in parsed.get("entries", []):
        title = getattr(entry, "title", "") or ""
        link = getattr(entry, "link", "") or ""

        if not title or not link:
            continue

        text = _get_text(entry)
        author = _get_author(entry)
        published_at = _parse_date(entry)

        yield Signal(
            signal_id=_make_signal_id(link, title),
            source=name,
            source_type="rss",
            text=text,
            url=link,
            author=author,
            published_at=published_at,
            velocity=0.0,
            engagement=0.0,
            run_id=run_id,
            environment=environment,
            metadata={"feed_url": url, "tags": [name]},
        )


def harvest_all(
    feeds: Optional[dict[str, str]] = None,
    run_id: str = "",
    environment: str = "production",
    timeout: int = TIMEOUT,
) -> dict:
    """Fetch all feeds and return signals plus any errors."""
    if feeds is None:
        feeds = DEFAULT_FEEDS
    signals: list[Signal] = []
    errors: dict[str, str] = {}

    for name, url in feeds.items():
        try:
            batch = list(fetch_feed(name, url, run_id=run_id, environment=environment, timeout=timeout))
            signals.extend(batch)
        except Exception as exc:
            errors[name] = str(exc)

    return {"signals": signals, "errors": errors}
