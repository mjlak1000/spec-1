"""Tests for cls_osint.adapters.congressional — Congressional records adapter."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from cls_osint.adapters.congressional import (
    _extract_bill_id,
    _extract_chamber,
    _extract_sponsor,
    _extract_status,
    _extract_tags,
    _classify_record_type,
    _make_record_id,
    fetch_congress_rss,
    fetch_govtrack_rss,
    collect,
)
from cls_osint.schemas import CongressRecord


class TestExtractBillId:
    def test_extracts_hr(self):
        assert _extract_bill_id("H.R.1234 National Defense Act") == "H.R.1234"

    def test_extracts_senate(self):
        assert _extract_bill_id("S.567 Authorization bill") == "S.567"

    def test_extracts_resolution(self):
        result = _extract_bill_id("H.Res.100 Expressing support")
        assert "H.Res" in result

    def test_returns_empty_when_no_match(self):
        assert _extract_bill_id("No bill ID here") == ""

    def test_handles_spaces(self):
        assert "H.R." in _extract_bill_id("H.R. 5000 Some bill")


class TestExtractChamber:
    def test_detects_house_from_hr(self):
        assert _extract_chamber("Defense bill", "H.R.1234") == "HOUSE"

    def test_detects_senate_from_s(self):
        assert _extract_chamber("Intelligence bill", "S.567") == "SENATE"

    def test_detects_house_from_title(self):
        assert _extract_chamber("House Passed Defense Act", "") == "HOUSE"

    def test_returns_unknown_for_ambiguous(self):
        assert _extract_chamber("Some bill", "") == "UNKNOWN"


class TestExtractStatus:
    def test_detects_enacted(self):
        assert _extract_status("The bill was signed into law today") == "ENACTED"

    def test_detects_passed_senate(self):
        assert _extract_status("passed senate 60-40") == "PASSED_SENATE"

    def test_detects_passed_house(self):
        assert _extract_status("passed house by voice vote") == "PASSED_HOUSE"

    def test_detects_failed(self):
        assert _extract_status("The bill failed to pass") == "FAILED"

    def test_defaults_to_introduced(self):
        assert _extract_status("A new bill was introduced") == "INTRODUCED"


class TestExtractSponsor:
    def test_extracts_representative(self):
        sponsor = _extract_sponsor("introduced by Rep. John Smith to authorize")
        assert "John Smith" in sponsor

    def test_extracts_senator(self):
        sponsor = _extract_sponsor("Sen. Jane Doe introduced legislation")
        assert "Jane Doe" in sponsor

    def test_returns_unknown_for_no_match(self):
        assert _extract_sponsor("No sponsor information here") == "UNKNOWN"


class TestExtractTags:
    def test_detects_defense(self):
        tags = _extract_tags("National Defense Authorization Act 2025")
        assert "defense" in tags

    def test_detects_cyber(self):
        tags = _extract_tags("Cybersecurity Infrastructure Protection Act")
        assert "cyber" in tags

    def test_detects_intelligence(self):
        tags = _extract_tags("Intelligence Community Oversight Reform")
        assert "intelligence" in tags

    def test_returns_empty_for_unrelated(self):
        tags = _extract_tags("Highway Infrastructure Improvement Act")
        assert "defense" not in tags


class TestClassifyRecordType:
    def test_detects_hearing(self):
        assert _classify_record_type("Senate Hearing on Defense Budget", "") == "HEARING"

    def test_detects_resolution(self):
        assert _classify_record_type("H.Res.100 Resolution on foreign policy", "") == "RESOLUTION"

    def test_detects_amendment(self):
        assert _classify_record_type("Amendment to NDAA", "") == "AMENDMENT"

    def test_defaults_to_bill(self):
        assert _classify_record_type("H.R.1234 New Legislation", "") == "BILL"


class TestMakeRecordId:
    def test_deterministic(self):
        id1 = _make_record_id("H.R.1234", "2024-01-15")
        id2 = _make_record_id("H.R.1234", "2024-01-15")
        assert id1 == id2

    def test_different_inputs_different_ids(self):
        id1 = _make_record_id("H.R.1234", "2024-01-15")
        id2 = _make_record_id("S.567", "2024-01-15")
        assert id1 != id2

    def test_has_congress_prefix(self):
        assert _make_record_id("H.R.1", "2024").startswith("congress_")


class TestCongressRecord:
    def test_to_dict(self):
        rec = CongressRecord(
            record_id="congress_001",
            record_type="BILL",
            bill_id="H.R.1234",
            title="Defense Act",
            sponsor="Rep. Smith",
            chamber="HOUSE",
            status="INTRODUCED",
            date=datetime(2024, 1, 15, tzinfo=timezone.utc),
            summary="Authorizes defense spending.",
            url="https://congress.gov/bill/1234",
        )
        d = rec.to_dict()
        assert d["bill_id"] == "H.R.1234"
        assert d["chamber"] == "HOUSE"
        assert d["status"] == "INTRODUCED"

    def test_to_osint_record(self):
        rec = CongressRecord(
            record_id="congress_002",
            record_type="BILL",
            bill_id="S.500",
            title="Intelligence Authorization Act",
            sponsor="Sen. Jones",
            chamber="SENATE",
            status="PASSED_SENATE",
            date=datetime(2024, 3, 1, tzinfo=timezone.utc),
            summary="Intelligence community funding.",
            url="https://congress.gov/bill/s500",
        )
        osint = rec.to_osint_record()
        assert osint.source_type == "CONGRESSIONAL"
        assert "S.500" in osint.content
        assert "Intelligence Authorization" in osint.content


class TestFetchCongressRss:
    def _make_entry(self, title="H.R.1234 Defense Act", link="https://congress.gov/bill/1234"):
        entry = MagicMock()
        entry.title = title
        entry.link = link
        entry.summary = "A bill to authorize defense spending. introduced by Rep. Smith."
        entry.description = entry.summary
        entry.published_parsed = (2024, 1, 15, 0, 0, 0, 0, 15, 0)
        entry.updated_parsed = None
        return entry

    def test_parses_entries(self):
        mock_feed = MagicMock()
        mock_feed.entries = [self._make_entry()]
        mock_feed.get = lambda k, d=None: getattr(mock_feed, k, d)

        with patch("cls_osint.adapters.congressional.feedparser.parse", return_value=mock_feed):
            records = fetch_congress_rss()

        assert len(records) == 1
        assert isinstance(records[0], CongressRecord)

    def test_skips_entries_without_title(self):
        mock_feed = MagicMock()
        entry = MagicMock()
        entry.title = ""
        entry.link = "https://example.com"
        entry.summary = ""
        entry.published_parsed = None
        entry.updated_parsed = None
        mock_feed.entries = [entry]
        mock_feed.get = lambda k, d=None: getattr(mock_feed, k, d)

        with patch("cls_osint.adapters.congressional.feedparser.parse", return_value=mock_feed):
            records = fetch_congress_rss()

        assert len(records) == 0

    def test_returns_empty_on_parse_error(self):
        with patch("cls_osint.adapters.congressional.feedparser.parse", side_effect=Exception):
            records = fetch_congress_rss()
        assert records == []


class TestCollect:
    def test_deduplicates_across_sources(self):
        rec = CongressRecord(
            record_id="dedup_001",
            record_type="BILL",
            bill_id="H.R.1",
            title="Test",
            sponsor="Rep. X",
            chamber="HOUSE",
            status="INTRODUCED",
            date=datetime(2024, 1, 1, tzinfo=timezone.utc),
            summary="Test",
            url="https://congress.gov/1",
        )
        with patch("cls_osint.adapters.congressional.fetch_congress_rss", return_value=[rec]), \
             patch("cls_osint.adapters.congressional.fetch_govtrack_rss", return_value=[rec]):
            records = collect()

        # Same record_id from both sources → deduplicated to 1
        assert len(records) == 1

    def test_combines_multiple_sources(self):
        rec1 = CongressRecord(
            record_id="rec_1",
            record_type="BILL",
            bill_id="H.R.1",
            title="Bill One",
            sponsor="Rep. A",
            chamber="HOUSE",
            status="INTRODUCED",
            date=datetime(2024, 1, 1, tzinfo=timezone.utc),
            summary="",
            url="",
        )
        rec2 = CongressRecord(
            record_id="rec_2",
            record_type="BILL",
            bill_id="S.2",
            title="Bill Two",
            sponsor="Sen. B",
            chamber="SENATE",
            status="INTRODUCED",
            date=datetime(2024, 1, 2, tzinfo=timezone.utc),
            summary="",
            url="",
        )
        with patch("cls_osint.adapters.congressional.fetch_congress_rss", return_value=[rec1]), \
             patch("cls_osint.adapters.congressional.fetch_govtrack_rss", return_value=[rec2]):
            records = collect()

        assert len(records) == 2
