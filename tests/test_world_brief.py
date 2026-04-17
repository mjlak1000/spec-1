"""Tests for cls_world_brief — world brief producer, formatter, store."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from cls_world_brief.schemas import WorldBrief, BriefSection
from cls_world_brief.producer import produce_brief, _build_headline, _build_summary
from cls_world_brief.formatter import to_markdown, to_plain_text, to_json_summary
from cls_world_brief.store import BriefStore


def _make_record(record_id="rec1", content="Defense spending increased for military"):
    return {
        "record_id": record_id,
        "source_type": "rss",
        "content": content,
        "url": "https://example.com",
        "confidence": 0.8,
    }


class TestWorldBriefSchema:
    def test_to_dict_has_required_fields(self):
        brief = WorldBrief(
            brief_id="brief_001",
            date="2024-01-15",
            headline="Test headline",
            summary="Test summary",
            sections=[BriefSection("Defense", "Body text")],
            sources=["https://example.com"],
            confidence=0.75,
        )
        d = brief.to_dict()
        assert d["brief_id"] == "brief_001"
        assert d["date"] == "2024-01-15"
        assert d["headline"] == "Test headline"
        assert len(d["sections"]) == 1
        assert d["confidence"] == 0.75

    def test_make_id_is_deterministic(self):
        id1 = WorldBrief.make_id("2024-01-15")
        id2 = WorldBrief.make_id("2024-01-15")
        assert id1 == id2
        assert id1.startswith("brief_")

    def test_make_id_differs_by_date(self):
        id1 = WorldBrief.make_id("2024-01-15")
        id2 = WorldBrief.make_id("2024-01-16")
        assert id1 != id2


class TestProduceBrief:
    def test_produces_brief_from_records(self):
        records = [
            _make_record("r1", "Military defense spending increased. NATO allies."),
            _make_record("r2", "Cyber espionage intelligence community NSA."),
            _make_record("r3", "China Russia geopolitics tensions rising."),
        ]
        brief = produce_brief(records, date="2024-01-15")

        assert isinstance(brief, WorldBrief)
        assert brief.date == "2024-01-15"
        assert brief.headline
        assert brief.summary
        assert brief.brief_id.startswith("brief_")

    def test_produces_brief_from_empty_records(self):
        brief = produce_brief([], date="2024-01-15")
        assert isinstance(brief, WorldBrief)
        assert brief.confidence == 0.0

    def test_uses_current_date_by_default(self):
        brief = produce_brief([])
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        assert brief.date == today

    def test_populates_sections_for_matching_records(self):
        records = [
            _make_record("r1", "Military defense Pentagon armed forces deployment"),
            _make_record("r2", "Cyber espionage intelligence NSA hack"),
        ]
        brief = produce_brief(records, date="2024-01-15")
        section_titles = [s.title for s in brief.sections]
        # Should have at least military or intel section
        assert any("Military" in t or "Intelligence" in t for t in section_titles)

    def test_sources_are_deduplicated(self):
        url = "https://same-url.com"
        records = [
            {"record_id": "r1", "content": "defense military", "url": url, "confidence": 0.8},
            {"record_id": "r2", "content": "military defense", "url": url, "confidence": 0.7},
        ]
        brief = produce_brief(records)
        assert brief.sources.count(url) <= 1

    def test_confidence_scales_with_record_count(self):
        records_few = [_make_record(f"r{i}") for i in range(2)]
        records_many = [_make_record(f"r{i}") for i in range(20)]

        brief_few = produce_brief(records_few)
        brief_many = produce_brief(records_many)

        assert brief_many.confidence >= brief_few.confidence


class TestBriefFormatter:
    def _make_brief(self):
        return WorldBrief(
            brief_id="brief_001",
            date="2024-01-15",
            headline="Critical intelligence detected",
            summary="Multiple signals indicate elevated threat.",
            sections=[
                BriefSection("Military & Defense", "Troop movements detected.", ["r1"]),
                BriefSection("Intelligence & Cyber", "Espionage activity reported.", ["r2"]),
            ],
            sources=["https://source1.com", "https://source2.com"],
            confidence=0.80,
            produced_at=datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc),
        )

    def test_to_markdown_contains_headline(self):
        md = to_markdown(self._make_brief())
        assert "Critical intelligence detected" in md

    def test_to_markdown_contains_date(self):
        md = to_markdown(self._make_brief())
        assert "2024-01-15" in md

    def test_to_markdown_contains_sections(self):
        md = to_markdown(self._make_brief())
        assert "Military & Defense" in md
        assert "Intelligence & Cyber" in md

    def test_to_markdown_contains_sources(self):
        md = to_markdown(self._make_brief())
        assert "https://source1.com" in md

    def test_to_plain_text_no_markdown_syntax(self):
        text = to_plain_text(self._make_brief())
        # Should not have markdown # headers
        assert "# " not in text
        assert "SPEC-1 WORLD INTELLIGENCE BRIEF" in text

    def test_to_json_summary(self):
        summary = to_json_summary(self._make_brief())
        assert summary["brief_id"] == "brief_001"
        assert summary["date"] == "2024-01-15"
        assert "headline" in summary
        assert "sections" in summary
        assert isinstance(summary["sections"], list)


class TestBriefStore:
    def test_save_and_read_back(self, tmp_path):
        store = BriefStore(
            jsonl_path=tmp_path / "briefs.jsonl",
            briefs_dir=tmp_path / "briefs",
        )
        brief = WorldBrief(
            brief_id="brief_test",
            date="2024-01-15",
            headline="Test",
            summary="Test summary",
            produced_at=datetime(2024, 1, 15, tzinfo=timezone.utc),
        )
        store.save(brief, write_markdown=False)

        record = store.get_by_date("2024-01-15")
        assert record is not None
        assert record["brief_id"] == "brief_test"

    def test_save_writes_markdown(self, tmp_path):
        store = BriefStore(
            jsonl_path=tmp_path / "briefs.jsonl",
            briefs_dir=tmp_path / "briefs",
        )
        brief = WorldBrief(
            brief_id="brief_md",
            date="2024-02-01",
            headline="MD Test",
            summary="Summary text",
            produced_at=datetime(2024, 2, 1, tzinfo=timezone.utc),
        )
        store.save(brief, write_markdown=True)

        md_file = tmp_path / "briefs" / "2024-02-01.md"
        assert md_file.exists()
        content = md_file.read_text()
        assert "MD Test" in content

    def test_latest_returns_most_recent(self, tmp_path):
        store = BriefStore(jsonl_path=tmp_path / "b.jsonl", briefs_dir=tmp_path)
        for date in ("2024-01-10", "2024-01-11", "2024-01-12"):
            store.save(
                WorldBrief(
                    brief_id=f"brief_{date}",
                    date=date,
                    headline="H",
                    summary="S",
                    produced_at=datetime.now(timezone.utc),
                ),
                write_markdown=False,
            )
        latest = store.latest()
        assert latest is not None
        assert latest["date"] == "2024-01-12"

    def test_count(self, tmp_path):
        store = BriefStore(jsonl_path=tmp_path / "b.jsonl", briefs_dir=tmp_path)
        for i in range(3):
            store.save(
                WorldBrief(
                    brief_id=f"b{i}",
                    date=f"2024-01-{10+i:02d}",
                    headline="H",
                    summary="S",
                    produced_at=datetime.now(timezone.utc),
                ),
                write_markdown=False,
            )
        assert store.count() == 3

    def test_clear(self, tmp_path):
        store = BriefStore(jsonl_path=tmp_path / "b.jsonl", briefs_dir=tmp_path)
        store.save(
            WorldBrief(brief_id="x", date="2024-01-01", headline="H", summary="S",
                       produced_at=datetime.now(timezone.utc)),
            write_markdown=False,
        )
        assert store.count() == 1
        store.clear()
        assert store.count() == 0

    def test_no_file_returns_none_for_latest(self, tmp_path):
        store = BriefStore(jsonl_path=tmp_path / "missing.jsonl", briefs_dir=tmp_path)
        assert store.latest() is None
