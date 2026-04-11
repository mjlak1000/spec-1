"""RSS Harvester — ported from cls_osint/collectors/rss.py.

Fetches RSS feeds using feedparser and produces Signal dataclass instances.
Sources: War on the Rocks, Cipher Brief, Lawfare, RAND, Atlantic Council, Defense One.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Iterator, Optional

import feedparser

from spec1_engine.schemas.models import Signal

DEFAULT_FEEDS: dict[str, str] = {
    "war_on_the_rocks": "https://warontherocks.com/feed/",
    "cipher_brief": "https://www.thecipherbrief.com/feed",
    "lawfare": "https://www.lawfaremedia.org/feed",
    "rand": "https://www.rand.org/blog.xml",
    "atlantic_council": "https://www.atlanticcouncil.org/feed/",
    "defense_one": "https://www.defenseone.com/rss/all/",
}

TIMEOUT = 15


def _make_signal_id(url: str, title: str) -> str:
    raw = f"{url}::{title}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _parse_date(entry: feedparser.FeedParserDict) -> datetime:
    """Extract published datetime from a feedparser entry."""
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        try:
            import time
            t = entry.published_parsed
            return datetime(*t[:6], tzinfo=timezone.utc)
        except Exception:
            pass
    if hasattr(entry, "updated_parsed") and entry.updated_parsed:
        try:
            import time
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


def fetch_feed(
    name: str,
    url: str,
    run_id: str = "",
    environment: str = "production",
    timeout: int = TIMEOUT,
) -> Iterator[Signal]:
    """Fetch a single RSS feed and yield Signal instances."""
    parsed = feedparser.parse(url, request_headers={"User-Agent": "spec1-engine/0.2"})

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
