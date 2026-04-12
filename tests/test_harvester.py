"""Tests for signal/harvester.py — private helpers, fetch paths, error handling."""

from __future__ import annotations

import io
import ssl
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open

import feedparser
import pytest

from spec1_engine.signal.harvester import (
    _parse_date,
    _get_text,
    _get_author,
    _fetch_raw_sanitized,
    _fetch_raw_no_ssl,
    _parse_feed,
    _SSL_UNVERIFIED,
    _SANITIZE_XML,
    fetch_feed,
    harvest_all,
    DEFAULT_FEEDS,
    _make_signal_id,
    _ILLEGAL_XML_RE,
)
from spec1_engine.schemas.models import Signal


# ─── Helpers ─────────────────────────────────────────────────────────────────

class _Entry:
    """Minimal feedparser entry stub."""

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


# ─── _parse_date tests ────────────────────────────────────────────────────────

def test_parse_date_with_published_parsed():
    entry = _Entry(published_parsed=(2025, 4, 10, 12, 0, 0, 3, 100, 0))
    dt = _parse_date(entry)
    assert isinstance(dt, datetime)
    assert dt.year == 2025
    assert dt.month == 4
    assert dt.day == 10


def test_parse_date_falls_back_to_updated_parsed():
    """When published_parsed is absent but updated_parsed is present, use it."""
    entry = _Entry(
        published_parsed=None,
        updated_parsed=(2025, 3, 15, 8, 30, 0, 0, 74, 0),
    )
    dt = _parse_date(entry)
    assert dt.year == 2025
    assert dt.month == 3
    assert dt.day == 15


def test_parse_date_no_date_returns_now():
    """When neither parsed date field is present, return roughly now."""
    entry = _Entry(published_parsed=None, updated_parsed=None)
    before = datetime.now(timezone.utc)
    dt = _parse_date(entry)
    after = datetime.now(timezone.utc)
    assert before <= dt <= after


def test_parse_date_invalid_published_parsed_falls_back_to_updated():
    """Invalid published_parsed tuple triggers fallback to updated_parsed."""
    entry = _Entry(
        published_parsed=(9999, 99, 99, 99, 99, 99),  # will throw in datetime()
        updated_parsed=(2024, 1, 1, 0, 0, 0, 0, 1, 0),
    )
    # Should not raise — should fall back gracefully
    dt = _parse_date(entry)
    assert isinstance(dt, datetime)


def test_parse_date_both_invalid_returns_now():
    """When both parsed fields throw, return roughly now."""
    entry = _Entry(
        published_parsed=(9999, 99, 99),
        updated_parsed=(9999, 99, 99),
    )
    before = datetime.now(timezone.utc)
    dt = _parse_date(entry)
    after = datetime.now(timezone.utc)
    assert before <= dt <= after


# ─── _get_text tests ──────────────────────────────────────────────────────────

def test_get_text_uses_title_and_summary():
    entry = _Entry(title="My Title", summary="My Summary")
    text = _get_text(entry)
    assert "My Title" in text
    assert "My Summary" in text


def test_get_text_description_fallback_when_no_summary():
    """Uses description when summary is absent."""
    entry = _Entry(title="Title", summary=None, description="Desc fallback")
    text = _get_text(entry)
    assert "Desc fallback" in text


def test_get_text_no_description_or_summary():
    """No summary or description results in just the title."""
    entry = _Entry(title="Only Title", summary=None, description=None)
    text = _get_text(entry)
    assert "Only Title" in text


def test_get_text_with_content_field():
    """content field provides additional text."""
    content_item = MagicMock()
    content_item.value = "Content value text."
    entry = _Entry(title="T", summary="S", content=[content_item])
    text = _get_text(entry)
    assert "Content value text." in text


def test_get_text_content_empty_value_skipped():
    """content item with falsy value is skipped."""
    content_item = MagicMock()
    content_item.value = ""
    entry = _Entry(title="T", summary="S", content=[content_item])
    text = _get_text(entry)
    # No crash — content skipped
    assert "T" in text


def test_get_text_no_content_attribute():
    entry = _Entry(title="Title only")
    # No summary, description, or content attributes
    text = _get_text(entry)
    assert "Title only" in text


# ─── _get_author tests ────────────────────────────────────────────────────────

def test_get_author_uses_author_attribute():
    entry = _Entry(author="Jane Smith")
    assert _get_author(entry) == "Jane Smith"


def test_get_author_uses_author_detail_name():
    """When author is absent, fall back to author_detail.name."""
    detail = MagicMock()
    detail.get = MagicMock(return_value="Detail Author")
    entry = _Entry(author=None, author_detail=detail)
    author = _get_author(entry)
    assert author == "Detail Author"


def test_get_author_returns_empty_when_missing():
    entry = _Entry(author=None, author_detail=None)
    assert _get_author(entry) == ""


# ─── _fetch_raw_sanitized tests ───────────────────────────────────────────────

def test_fetch_raw_sanitized_strips_illegal_chars():
    """_fetch_raw_sanitized removes illegal XML control characters."""
    dirty_xml = "<?xml version='1.0'?><root>hello\x00\x01\x0bworld</root>"
    mock_resp = MagicMock()
    mock_resp.text = dirty_xml
    mock_resp.raise_for_status = MagicMock()

    with patch("spec1_engine.signal.harvester.requests.get", return_value=mock_resp):
        result = _fetch_raw_sanitized("https://example.com/feed", timeout=5)

    assert b"\x00" not in result
    assert b"\x01" not in result
    assert b"hello" in result
    assert b"world" in result


def test_fetch_raw_sanitized_returns_bytes():
    mock_resp = MagicMock()
    mock_resp.text = "<feed>content</feed>"
    mock_resp.raise_for_status = MagicMock()

    with patch("spec1_engine.signal.harvester.requests.get", return_value=mock_resp):
        result = _fetch_raw_sanitized("https://example.com/feed", timeout=5)

    assert isinstance(result, bytes)


def test_fetch_raw_sanitized_calls_raise_for_status():
    mock_resp = MagicMock()
    mock_resp.text = "<feed/>"
    with patch("spec1_engine.signal.harvester.requests.get", return_value=mock_resp):
        _fetch_raw_sanitized("https://example.com/feed", timeout=5)
    mock_resp.raise_for_status.assert_called_once()


# ─── _fetch_raw_no_ssl tests ──────────────────────────────────────────────────

def test_fetch_raw_no_ssl_returns_bytes():
    """_fetch_raw_no_ssl reads from urlopen response."""
    fake_content = b"<feed><item/></feed>"
    mock_response = MagicMock()
    mock_response.__enter__ = MagicMock(return_value=mock_response)
    mock_response.__exit__ = MagicMock(return_value=False)
    mock_response.read = MagicMock(return_value=fake_content)

    with patch("spec1_engine.signal.harvester.urllib.request.urlopen", return_value=mock_response), \
         patch("spec1_engine.signal.harvester.ssl.create_default_context") as mock_ctx:
        mock_ctx.return_value = MagicMock()
        result = _fetch_raw_no_ssl("https://example.com/feed", timeout=5)

    assert result == fake_content


def test_fetch_raw_no_ssl_disables_cert_verification():
    """_fetch_raw_no_ssl creates an SSL context with cert verification off."""
    fake_content = b"<feed/>"
    mock_response = MagicMock()
    mock_response.__enter__ = MagicMock(return_value=mock_response)
    mock_response.__exit__ = MagicMock(return_value=False)
    mock_response.read = MagicMock(return_value=fake_content)

    mock_ssl_ctx = MagicMock()
    with patch("spec1_engine.signal.harvester.urllib.request.urlopen", return_value=mock_response), \
         patch("spec1_engine.signal.harvester.ssl.create_default_context", return_value=mock_ssl_ctx):
        _fetch_raw_no_ssl("https://example.com/feed", timeout=5)

    assert mock_ssl_ctx.check_hostname is False
    assert mock_ssl_ctx.verify_mode == ssl.CERT_NONE


# ─── _parse_feed tests ────────────────────────────────────────────────────────

def test_parse_feed_ssl_unverified_uses_no_ssl_fetch():
    """SSL-unverified sources use _fetch_raw_no_ssl."""
    fake_bytes = b"<rss/>"
    # Take the first SSL_UNVERIFIED source
    ssl_source = next(iter(_SSL_UNVERIFIED))

    with patch("spec1_engine.signal.harvester._fetch_raw_no_ssl", return_value=fake_bytes) as mock_no_ssl, \
         patch("spec1_engine.signal.harvester.feedparser.parse") as mock_parse:
        mock_parse.return_value = MagicMock(entries=[])
        _parse_feed(ssl_source, "https://example.com", timeout=5)

    mock_no_ssl.assert_called_once()


def test_parse_feed_sanitize_xml_uses_raw_sanitized():
    """SANITIZE_XML sources use _fetch_raw_sanitized."""
    # Temporarily add a test source to _SANITIZE_XML
    import spec1_engine.signal.harvester as h_mod
    original = set(h_mod._SANITIZE_XML)
    h_mod._SANITIZE_XML.add("test_sanitize_source")
    try:
        fake_bytes = b"<rss/>"
        with patch("spec1_engine.signal.harvester._fetch_raw_sanitized", return_value=fake_bytes) as mock_san, \
             patch("spec1_engine.signal.harvester.feedparser.parse") as mock_parse:
            mock_parse.return_value = MagicMock(entries=[])
            _parse_feed("test_sanitize_source", "https://example.com", timeout=5)
        mock_san.assert_called_once()
    finally:
        h_mod._SANITIZE_XML.discard("test_sanitize_source")


def test_parse_feed_normal_uses_feedparser_directly():
    """Normal sources go directly through feedparser.parse."""
    with patch("spec1_engine.signal.harvester.feedparser.parse") as mock_parse:
        mock_parse.return_value = MagicMock(entries=[])
        _parse_feed("regular_source", "https://example.com", timeout=5)
    mock_parse.assert_called_once()


# ─── fetch_feed tests ─────────────────────────────────────────────────────────

def test_fetch_feed_bozo_with_no_entries_raises():
    """A bozo feed with no entries and a bozo_exception raises RuntimeError."""
    mock_parsed = MagicMock()
    mock_parsed.get = MagicMock(side_effect=lambda k, d=None: {
        "bozo": True,
        "bozo_exception": Exception("invalid feed"),
        "entries": [],
    }.get(k, d))

    with patch("spec1_engine.signal.harvester._parse_feed", return_value=mock_parsed):
        with pytest.raises(RuntimeError, match="Failed to parse feed"):
            list(fetch_feed("bad_source", "https://example.com"))


def test_fetch_feed_skips_entries_without_title_or_link():
    """Entries without title or link are skipped."""
    fake_xml = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
  <item><description>No title or link here</description></item>
</channel></rss>"""
    parsed = feedparser.parse(fake_xml)
    with patch("spec1_engine.signal.harvester._parse_feed", return_value=parsed):
        signals = list(fetch_feed("test", "https://example.com"))
    assert signals == []


def test_fetch_feed_yields_signals_with_correct_source():
    fake_xml = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
  <item>
    <title>Test Article</title>
    <link>https://example.com/art1</link>
    <description>Some description text here.</description>
  </item>
</channel></rss>"""
    parsed = feedparser.parse(fake_xml)
    with patch("spec1_engine.signal.harvester._parse_feed", return_value=parsed):
        signals = list(fetch_feed("my_source", "https://example.com"))
    assert len(signals) == 1
    assert signals[0].source == "my_source"


# ─── harvest_all tests ────────────────────────────────────────────────────────

def test_harvest_all_records_error_when_fetch_raises():
    """harvest_all catches exceptions per-feed and records them in errors dict."""
    with patch("spec1_engine.signal.harvester.fetch_feed", side_effect=RuntimeError("timeout")):
        result = harvest_all(
            feeds={"bad_feed": "https://example.com"},
            run_id="run-test",
            environment="test",
        )
    assert "bad_feed" in result["errors"]
    assert result["signals"] == []


def test_harvest_all_partial_failure():
    """harvest_all succeeds for good feeds even if one fails."""
    fake_xml = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
  <item>
    <title>Good Article</title>
    <link>https://good.com/art</link>
    <description>Good content here.</description>
  </item>
</channel></rss>"""
    good_parsed = feedparser.parse(fake_xml)

    def _side_effect(name, url, **kwargs):
        if name == "good":
            return iter([Signal(
                signal_id="sig-good",
                source="good",
                source_type="rss",
                text="Good content",
                url="https://good.com/art",
                author="",
                published_at=datetime.now(timezone.utc),
                velocity=0.0,
                engagement=0.0,
                run_id=kwargs.get("run_id", ""),
                environment=kwargs.get("environment", ""),
                metadata={},
            )])
        raise RuntimeError("bad feed failure")

    with patch("spec1_engine.signal.harvester.fetch_feed", side_effect=_side_effect):
        result = harvest_all(
            feeds={"good": "https://good.com", "bad": "https://bad.com"},
            run_id="run-test",
            environment="test",
        )

    assert len(result["signals"]) == 1
    assert "bad" in result["errors"]


# ─── _make_signal_id tests ────────────────────────────────────────────────────

def test_make_signal_id_deterministic():
    id1 = _make_signal_id("https://example.com/a", "Title A")
    id2 = _make_signal_id("https://example.com/a", "Title A")
    assert id1 == id2


def test_make_signal_id_different_for_different_inputs():
    id1 = _make_signal_id("https://example.com/a", "Title A")
    id2 = _make_signal_id("https://example.com/b", "Title B")
    assert id1 != id2


def test_make_signal_id_length():
    sid = _make_signal_id("https://example.com", "Any Title")
    assert len(sid) == 16


# ─── _ILLEGAL_XML_RE tests ────────────────────────────────────────────────────

def test_illegal_xml_re_removes_control_chars():
    dirty = "hello\x00\x01\x0bworld"
    clean = _ILLEGAL_XML_RE.sub("", dirty)
    assert clean == "helloworld"


def test_illegal_xml_re_preserves_tab_lf_cr():
    text = "line1\nline2\ttab\rreturn"
    clean = _ILLEGAL_XML_RE.sub("", text)
    assert clean == text


# ─── Additional coverage tests ────────────────────────────────────────────────

def test_harvest_all_uses_default_feeds_when_none_passed():
    """harvest_all uses DEFAULT_FEEDS when feeds=None."""
    # When no feeds passed, harvest_all defaults to DEFAULT_FEEDS
    with patch("spec1_engine.signal.harvester.fetch_feed",
               side_effect=RuntimeError("mocked")):
        result = harvest_all(run_id="run-default", environment="test")
    # All feeds should have errors since fetch_feed raises for all
    assert len(result["errors"]) > 0
    assert result["signals"] == []


def test_parse_date_updated_parsed_exception_falls_back():
    """When updated_parsed has an invalid tuple, falls back to now."""
    # Only updated_parsed is present, and it's invalid
    class EntryNoPublished:
        updated_parsed = (9999, 99, 99)
        # no published_parsed attribute
    before = datetime.now(timezone.utc)
    dt = _parse_date(EntryNoPublished())
    after = datetime.now(timezone.utc)
    # When both fail, returns now
    assert before <= dt <= after


def test_get_text_no_attributes():
    """_get_text returns empty string for entry with no useful attributes."""
    class EmptyEntry:
        pass
    text = _get_text(EmptyEntry())
    assert text == ""
