"""Tests for cls_osint.adapters.fara — FARA filing adapter."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from cls_osint.adapters.fara import (
    _make_record_id,
    _parse_date,
    _parse_activities_from_html,
    fetch_fara_api,
    fetch_recent_filings_html,
    collect,
)
from cls_osint.schemas import FaraRecord


class TestParseDate:
    def test_parses_mm_dd_yyyy(self):
        dt = _parse_date("01/15/2024")
        assert dt.year == 2024
        assert dt.month == 1
        assert dt.day == 15

    def test_parses_yyyy_mm_dd(self):
        dt = _parse_date("2024-03-20")
        assert dt.year == 2024
        assert dt.month == 3

    def test_parses_long_month(self):
        dt = _parse_date("January 15, 2024")
        assert dt.year == 2024
        assert dt.month == 1

    def test_falls_back_to_now_on_bad_input(self):
        before = datetime.now(timezone.utc)
        dt = _parse_date("not-a-date")
        after = datetime.now(timezone.utc)
        assert before <= dt <= after

    def test_strips_whitespace(self):
        dt = _parse_date("  2024-06-01  ")
        assert dt.year == 2024


class TestParseActivities:
    def test_detects_lobbying(self):
        activities = _parse_activities_from_html("Lobbying and political consulting")
        assert "Lobbying" in activities

    def test_detects_public_relations(self):
        activities = _parse_activities_from_html("Public relations services")
        assert "Public relations" in activities

    def test_falls_back_to_raw_text(self):
        activities = _parse_activities_from_html("Custom activity description")
        assert len(activities) >= 1
        assert "Custom activity description" in activities[0]

    def test_empty_text_returns_unspecified(self):
        activities = _parse_activities_from_html("")
        assert activities == ["Unspecified"]

    def test_multiple_activities_detected(self):
        text = "Political consulting and lobbying for foreign government"
        activities = _parse_activities_from_html(text)
        assert len(activities) >= 2


class TestMakeRecordId:
    def test_deterministic(self):
        id1 = _make_record_id("Acme Corp", "China MFA", "2024-01-15")
        id2 = _make_record_id("Acme Corp", "China MFA", "2024-01-15")
        assert id1 == id2

    def test_different_inputs_different_ids(self):
        id1 = _make_record_id("Acme Corp", "China MFA", "2024-01-15")
        id2 = _make_record_id("Beta Corp", "Russia MFA", "2024-01-15")
        assert id1 != id2

    def test_has_fara_prefix(self):
        record_id = _make_record_id("A", "B", "2024-01-01")
        assert record_id.startswith("fara_")


class TestFaraRecord:
    def test_to_dict_has_required_fields(self):
        rec = FaraRecord(
            record_id="fara_001",
            registrant="Acme Corp",
            foreign_principal="China MFA",
            country="China",
            activities=["Lobbying"],
            filed_at=datetime(2024, 1, 15, tzinfo=timezone.utc),
            doc_url="https://fara.gov/doc/001",
        )
        d = rec.to_dict()
        assert d["record_id"] == "fara_001"
        assert d["registrant"] == "Acme Corp"
        assert d["country"] == "China"
        assert d["status"] == "active"

    def test_to_osint_record(self):
        rec = FaraRecord(
            record_id="fara_002",
            registrant="Beta LLC",
            foreign_principal="Saudi Arabia Embassy",
            country="Saudi Arabia",
            activities=["Media outreach"],
            filed_at=datetime(2024, 2, 1, tzinfo=timezone.utc),
            doc_url="https://fara.gov/doc/002",
        )
        osint = rec.to_osint_record()
        assert osint.source_type == "fara"
        assert "Beta LLC" in osint.content
        assert "Saudi Arabia" in osint.content


class TestFetchFaraApi:
    def test_parses_json_response(self):
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {
                "RegistrantName": "Acme Corp",
                "ForeignPrincipalName": "China MOFCOM",
                "Country": "China",
                "DateStamped": "2024-01-15",
                "Url": "https://fara.gov/doc/001",
                "RegistrationNumber": "12345",
                "ActivityDescription": "Lobbying",
            }
        ]
        mock_response.raise_for_status = MagicMock()

        with patch("cls_osint.adapters.fara.requests.get", return_value=mock_response):
            records = fetch_fara_api()

        assert len(records) == 1
        assert records[0].registrant == "Acme Corp"
        assert records[0].country == "China"
        assert records[0].registration_number == "12345"

    def test_returns_empty_on_network_error(self):
        with patch("cls_osint.adapters.fara.requests.get", side_effect=ConnectionError):
            records = fetch_fara_api()
        assert records == []

    def test_returns_empty_on_bad_json(self):
        mock_response = MagicMock()
        mock_response.json.side_effect = ValueError("bad json")
        mock_response.raise_for_status = MagicMock()

        with patch("cls_osint.adapters.fara.requests.get", return_value=mock_response):
            records = fetch_fara_api()

        assert records == []

    def test_skips_records_without_registrant(self):
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {"ForeignPrincipalName": "No registrant", "Country": "UK", "DateStamped": "2024-01-01"}
        ]
        mock_response.raise_for_status = MagicMock()

        with patch("cls_osint.adapters.fara.requests.get", return_value=mock_response):
            records = fetch_fara_api()

        assert records == []


class TestCollect:
    def test_falls_back_to_html_when_api_empty(self):
        with patch("cls_osint.adapters.fara.fetch_fara_api", return_value=[]), \
             patch("cls_osint.adapters.fara.fetch_recent_filings_html") as mock_html:
            mock_html.return_value = [
                FaraRecord(
                    record_id="fara_x",
                    registrant="Test Corp",
                    foreign_principal="Test Gov",
                    country="TestLand",
                    activities=["Lobbying"],
                    filed_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
                    doc_url="https://fara.gov",
                )
            ]
            records = collect(use_api=True)

        assert len(records) == 1
        assert records[0].registrant == "Test Corp"

    def test_returns_api_results_when_available(self):
        mock_records = [
            FaraRecord(
                record_id="fara_api_1",
                registrant="API Corp",
                foreign_principal="Foreign Gov",
                country="Foreign",
                activities=["PR"],
                filed_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
                doc_url="https://fara.gov",
            )
        ]
        with patch("cls_osint.adapters.fara.fetch_fara_api", return_value=mock_records):
            records = collect(use_api=True)

        assert records[0].registrant == "API Corp"

    def test_returns_empty_when_all_fail(self):
        with patch("cls_osint.adapters.fara.fetch_fara_api", side_effect=Exception), \
             patch("cls_osint.adapters.fara.fetch_recent_filings_html", side_effect=Exception):
            records = collect()

        assert records == []
