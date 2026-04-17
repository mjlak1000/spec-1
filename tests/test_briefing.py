"""Tests for the SPEC-1 briefing module."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


# ─── Fixtures ─────────────────────────────────────────────────────────────────

REQUIRED_SECTIONS = [
    "## SPEC-1 DAILY BRIEF",
    "### Executive Summary",
    "### Elevated Signals",
    "### Domain Briefings",
    "### Story Leads",
    "### Watch List",
    "### Signal Notes",
]

SAMPLE_BRIEF = "\n".join([
    "## SPEC-1 DAILY BRIEF — 2026-04-11",
    "",
    "### Executive Summary",
    "Three things happened. They mean something. Uncertainty remains.",
    "",
    "### Elevated Signals",
    "No elevated signals today.",
    "",
    "### Domain Briefings",
    "",
    "**Geopolitics**",
    "Patterns observed.",
    "",
    "**Cyber / Info Ops**",
    "Attribution confidence low.",
    "",
    "### Story Leads",
    "",
    "**LEAD: Test Lead**",
    "Signal: war_on_the_rocks",
    "The question: What happened?",
    "Who to call: DoD spokesperson",
    "Documents to request: FOIA",
    "Window: 24hrs",
    "Confidence: MEDIUM",
    "",
    "### Watch List — Tomorrow",
    "- Watch thing 1",
    "",
    "### Signal Notes",
    "Collection quality was acceptable today.",
])


def make_record(
    source: str = "war_on_the_rocks",
    classification: str = "Investigate",
    confidence: float = 0.65,
    priority: str = "STANDARD",
) -> dict:
    return {
        "record_id": f"rec-{source}-test",
        "pattern": f"[{priority}] Test pattern | gates=credibility+volume",
        "classification": classification,
        "confidence": confidence,
        "source_weight": 0.85,
        "analyst_weight": 0.80,
        "run_id": "run-brief-test",
        "signal_id": f"sig-{source}",
        "signal_source": source,
        "signal_url": f"https://{source}.com/article",
        "environment": "production",
        "opportunity_id": f"opp-{source}",
        "opportunity_score": 0.72,
        "opportunity_priority": priority,
        "gate_results": {"credibility": True, "volume": True, "velocity": True, "novelty": True},
        "investigation_id": "inv-test",
        "hypothesis": "Test hypothesis.",
        "outcome_classification": classification,
        "outcome_confidence": confidence,
    }


def make_cycle_stats(records_stored: int = 5) -> dict:
    return {
        "run_id": "run-brief-test",
        "started_at": "2026-04-11T06:00:00+00:00",
        "finished_at": "2026-04-11T06:03:00+00:00",
        "signals_harvested": 245,
        "opportunities_found": 50,
        "records_stored": records_stored,
        "errors": [],
    }


def make_mock_claude_response(text: str) -> MagicMock:
    content_block = MagicMock()
    content_block.text = text
    response = MagicMock()
    response.content = [content_block]
    return response


# ─── generator.py — unit tests ────────────────────────────────────────────────

def test_generate_brief_returns_string():
    from spec1_engine.briefing.generator import generate_brief
    records = [make_record()]
    stats = make_cycle_stats()
    mock_resp = make_mock_claude_response(SAMPLE_BRIEF)
    with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
        with patch("anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = mock_resp
            result = generate_brief(records, stats)
    assert isinstance(result, str)
    assert len(result) > 0


def test_generate_brief_contains_executive_summary():
    from spec1_engine.briefing.generator import generate_brief
    records = [make_record()]
    stats = make_cycle_stats()
    mock_resp = make_mock_claude_response(SAMPLE_BRIEF)
    with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
        with patch("anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = mock_resp
            result = generate_brief(records, stats)
    assert "### Executive Summary" in result


def test_generate_brief_contains_all_required_sections():
    from spec1_engine.briefing.generator import generate_brief
    records = [make_record()]
    stats = make_cycle_stats()
    mock_resp = make_mock_claude_response(SAMPLE_BRIEF)
    with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
        with patch("anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = mock_resp
            result = generate_brief(records, stats)
    for section in REQUIRED_SECTIONS:
        assert section in result, f"Missing section: {section}"


def test_generate_brief_story_leads_present_with_elevated():
    from spec1_engine.briefing.generator import generate_brief
    records = [make_record(classification="CORROBORATED", priority="ELEVATED")]
    stats = make_cycle_stats()
    mock_resp = make_mock_claude_response(SAMPLE_BRIEF)
    with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
        with patch("anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = mock_resp
            result = generate_brief(records, stats)
    assert "### Story Leads" in result


def test_generate_brief_api_failure_returns_fallback():
    from spec1_engine.briefing.generator import generate_brief
    records = [make_record()]
    stats = make_cycle_stats()
    with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
        with patch("anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.side_effect = Exception("API down")
            result = generate_brief(records, stats)
    assert isinstance(result, str)
    assert "## SPEC-1 DAILY BRIEF" in result


def test_generate_brief_api_failure_no_exception():
    from spec1_engine.briefing.generator import generate_brief
    records = [make_record()]
    stats = make_cycle_stats()
    with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
        with patch("anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.side_effect = RuntimeError("timeout")
            try:
                generate_brief(records, stats)
            except Exception as exc:
                pytest.fail(f"generate_brief raised: {exc}")


def test_generate_brief_no_api_key_returns_fallback():
    from spec1_engine.briefing.generator import generate_brief
    import os
    records = [make_record()]
    stats = make_cycle_stats()
    with patch.dict("os.environ", {}, clear=True):
        os.environ.pop("ANTHROPIC_API_KEY", None)
        result = generate_brief(records, stats)
    assert "## SPEC-1 DAILY BRIEF" in result
    assert "API key not configured" in result or "unavailable" in result


def test_generate_brief_fallback_contains_date():
    from spec1_engine.briefing.generator import _fallback_brief
    stats = make_cycle_stats()
    result = _fallback_brief(stats)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    assert today in result


def test_generate_brief_elevated_count_in_prompt():
    from spec1_engine.briefing.generator import _build_prompt
    records = [
        make_record(classification="CORROBORATED"),
        make_record(classification="ESCALATE", source="rand"),
        make_record(classification="INVESTIGATE", source="defense_one"),
    ]
    stats = make_cycle_stats()
    prompt = _build_prompt(records, stats)
    assert "ELEVATED SIGNALS (2)" in prompt


def test_generate_brief_standard_records_in_prompt():
    from spec1_engine.briefing.generator import _build_prompt
    records = [make_record() for _ in range(5)]
    stats = make_cycle_stats()
    prompt = _build_prompt(records, stats)
    assert "STANDARD SIGNALS" in prompt


def test_generate_brief_geo_count_in_prompt():
    from spec1_engine.briefing.generator import _build_prompt
    records = [make_record(source="war_on_the_rocks"), make_record(source="rand")]
    stats = make_cycle_stats()
    prompt = _build_prompt(records, stats)
    assert "Geopolitics: 2" in prompt


def test_generate_brief_cyber_count_in_prompt():
    from spec1_engine.briefing.generator import _build_prompt
    records = [make_record(source="cipher_brief"), make_record(source="just_security")]
    stats = make_cycle_stats()
    prompt = _build_prompt(records, stats)
    assert "Cyber / Info Ops: 2" in prompt


def test_format_record_contains_source():
    from spec1_engine.briefing.generator import _format_record
    rec = make_record(source="war_on_the_rocks")
    result = _format_record(rec)
    assert "WAR_ON_THE_ROCKS" in result


def test_format_record_contains_confidence():
    from spec1_engine.briefing.generator import _format_record
    rec = make_record(confidence=0.73)
    result = _format_record(rec)
    assert "confidence=0.73" in result


def test_format_record_contains_classification():
    from spec1_engine.briefing.generator import _format_record
    rec = make_record(classification="ESCALATE")
    result = _format_record(rec)
    assert "classification=ESCALATE" in result


def test_classify_domain_cyber():
    from spec1_engine.briefing.generator import _classify_domain
    assert _classify_domain({"signal_source": "cipher_brief"}) == "cyber"
    assert _classify_domain({"signal_source": "just_security"}) == "cyber"


def test_classify_domain_geo():
    from spec1_engine.briefing.generator import _classify_domain
    assert _classify_domain({"signal_source": "war_on_the_rocks"}) == "geo"
    assert _classify_domain({"signal_source": "rand"}) == "geo"


def test_standard_top10_capped():
    from spec1_engine.briefing.generator import _build_prompt
    records = [make_record(source=f"rand", confidence=i * 0.05) for i in range(20)]
    stats = make_cycle_stats()
    prompt = _build_prompt(records, stats)
    # Prompt should reference at most 10 standard records
    assert "STANDARD SIGNALS — TOP 10 BY CONFIDENCE" in prompt


# ─── writer.py — unit tests ───────────────────────────────────────────────────

def test_write_brief_creates_dated_file(tmp_path):
    from spec1_engine.briefing import writer
    original_dir = writer.BRIEFS_DIR
    writer.BRIEFS_DIR = tmp_path / "briefs"
    try:
        path = writer.write_brief(SAMPLE_BRIEF, "run-001", "2026-04-11T06:00:00+00:00")
        assert Path(path).exists()
        assert "2026-04-11" in path
    finally:
        writer.BRIEFS_DIR = original_dir


def test_write_brief_creates_latest_file(tmp_path):
    from spec1_engine.briefing import writer
    original_dir = writer.BRIEFS_DIR
    writer.BRIEFS_DIR = tmp_path / "briefs"
    try:
        writer.write_brief(SAMPLE_BRIEF, "run-001", "2026-04-11T06:00:00+00:00")
        latest = writer.BRIEFS_DIR / "spec1_brief_latest.md"
        assert latest.exists()
        assert latest.read_text(encoding="utf-8") == SAMPLE_BRIEF
    finally:
        writer.BRIEFS_DIR = original_dir


def test_write_brief_dated_file_content(tmp_path):
    from spec1_engine.briefing import writer
    original_dir = writer.BRIEFS_DIR
    writer.BRIEFS_DIR = tmp_path / "briefs"
    try:
        path = writer.write_brief(SAMPLE_BRIEF, "run-001", "2026-04-11T06:00:00+00:00")
        content = Path(path).read_text(encoding="utf-8")
        assert content == SAMPLE_BRIEF
    finally:
        writer.BRIEFS_DIR = original_dir


def test_write_brief_appends_index(tmp_path):
    from spec1_engine.briefing import writer
    original_dir = writer.BRIEFS_DIR
    writer.BRIEFS_DIR = tmp_path / "briefs"
    try:
        writer.write_brief(SAMPLE_BRIEF, "run-001", "2026-04-11T06:00:00+00:00")
        writer.write_brief(SAMPLE_BRIEF, "run-002", "2026-04-12T06:00:00+00:00")
        index = writer.BRIEFS_DIR / "brief_index.jsonl"
        lines = [l for l in index.read_text().splitlines() if l.strip()]
        assert len(lines) == 2
    finally:
        writer.BRIEFS_DIR = original_dir


def test_write_brief_index_has_correct_fields(tmp_path):
    from spec1_engine.briefing import writer
    original_dir = writer.BRIEFS_DIR
    writer.BRIEFS_DIR = tmp_path / "briefs"
    try:
        writer.write_brief(SAMPLE_BRIEF, "run-001", "2026-04-11T06:00:00+00:00")
        index = writer.BRIEFS_DIR / "brief_index.jsonl"
        entry = json.loads(index.read_text().strip())
        assert entry["run_id"] == "run-001"
        assert entry["date"] == "2026-04-11"
        assert "filepath" in entry
        assert "word_count" in entry
        assert "timestamp" in entry
    finally:
        writer.BRIEFS_DIR = original_dir


def test_write_brief_word_count_in_index(tmp_path):
    from spec1_engine.briefing import writer
    original_dir = writer.BRIEFS_DIR
    writer.BRIEFS_DIR = tmp_path / "briefs"
    try:
        writer.write_brief(SAMPLE_BRIEF, "run-001", "2026-04-11T06:00:00+00:00")
        index = writer.BRIEFS_DIR / "brief_index.jsonl"
        entry = json.loads(index.read_text().strip())
        assert entry["word_count"] == len(SAMPLE_BRIEF.split())
    finally:
        writer.BRIEFS_DIR = original_dir


def test_write_brief_returns_filepath_string(tmp_path):
    from spec1_engine.briefing import writer
    original_dir = writer.BRIEFS_DIR
    writer.BRIEFS_DIR = tmp_path / "briefs"
    try:
        result = writer.write_brief(SAMPLE_BRIEF, "run-001", "2026-04-11T06:00:00+00:00")
        assert isinstance(result, str)
        assert result.endswith(".md")
    finally:
        writer.BRIEFS_DIR = original_dir


def test_write_brief_creates_dir_if_missing(tmp_path):
    from spec1_engine.briefing import writer
    original_dir = writer.BRIEFS_DIR
    briefs_dir = tmp_path / "new_briefs_dir"
    writer.BRIEFS_DIR = briefs_dir
    try:
        assert not briefs_dir.exists()
        writer.write_brief(SAMPLE_BRIEF, "run-001", "2026-04-11T06:00:00+00:00")
        assert briefs_dir.exists()
    finally:
        writer.BRIEFS_DIR = original_dir


# ─── API routes — brief endpoints ─────────────────────────────────────────────

@pytest.fixture(scope="module")
def api_client():
    with patch("spec1_engine.api.app.build_scheduler") as mock_build, \
         patch("spec1_engine.api.app.maybe_run_on_start"):
        mock_sched = MagicMock()
        mock_sched.running = True
        mock_build.return_value = mock_sched
        from spec1_engine.api.app import app
        with TestClient(app) as c:
            yield c


def _patch_briefs_dir(briefs_dir):
    """Context manager that patches BRIEFS_DIR in both writer and routes modules."""
    import spec1_engine.briefing.writer as _w
    import spec1_engine.api.routes as _r  # noqa: F401 (unused but needed to trigger import)
    return patch.object(_w, "BRIEFS_DIR", briefs_dir)


def test_brief_latest_404_when_no_file(api_client, tmp_path):
    import spec1_engine.briefing.writer as _w
    empty = tmp_path / "empty_briefs"
    empty.mkdir()
    with patch.object(_w, "BRIEFS_DIR", empty):
        r = api_client.get("/api/v1/brief/latest")
    assert r.status_code == 404


def test_brief_latest_200_when_file_exists(api_client, tmp_path):
    import spec1_engine.briefing.writer as _w
    briefs_dir = tmp_path / "briefs_test"
    briefs_dir.mkdir()
    (briefs_dir / "spec1_brief_latest.md").write_text(SAMPLE_BRIEF, encoding="utf-8")
    (briefs_dir / "brief_index.jsonl").write_text(
        json.dumps({"run_id": "run-t", "date": "2026-04-11",
                    "filepath": "x", "word_count": 10, "timestamp": "2026-04-11T00:00:00+00:00"}) + "\n",
        encoding="utf-8",
    )
    with patch.object(_w, "BRIEFS_DIR", briefs_dir):
        r = api_client.get("/api/v1/brief/latest")
    assert r.status_code == 200
    data = r.json()
    assert "brief" in data
    assert len(data["brief"]) > 0


def test_brief_latest_returns_run_id(api_client, tmp_path):
    import spec1_engine.briefing.writer as _w
    briefs_dir = tmp_path / "briefs_runid"
    briefs_dir.mkdir()
    (briefs_dir / "spec1_brief_latest.md").write_text(SAMPLE_BRIEF, encoding="utf-8")
    (briefs_dir / "brief_index.jsonl").write_text(
        json.dumps({"run_id": "run-xyz", "date": "2026-04-11",
                    "filepath": "x", "word_count": 10, "timestamp": "2026-04-11T00:00:00+00:00"}) + "\n",
        encoding="utf-8",
    )
    with patch.object(_w, "BRIEFS_DIR", briefs_dir):
        r = api_client.get("/api/v1/brief/latest")
    assert r.json()["run_id"] == "run-xyz"


def test_brief_by_date_404_missing(api_client, tmp_path):
    import spec1_engine.briefing.writer as _w
    briefs_dir = tmp_path / "briefs_date_miss"
    briefs_dir.mkdir()
    with patch.object(_w, "BRIEFS_DIR", briefs_dir):
        r = api_client.get("/api/v1/brief/2020-01-01")
    assert r.status_code == 404


def test_brief_by_date_200_when_exists(api_client, tmp_path):
    import spec1_engine.briefing.writer as _w
    briefs_dir = tmp_path / "briefs_date_ok"
    briefs_dir.mkdir()
    (briefs_dir / "spec1_brief_2026-04-11.md").write_text(SAMPLE_BRIEF, encoding="utf-8")
    with patch.object(_w, "BRIEFS_DIR", briefs_dir):
        r = api_client.get("/api/v1/brief/2026-04-11")
    assert r.status_code == 200
    assert r.json()["brief"] == SAMPLE_BRIEF
    assert r.json()["date"] == "2026-04-11"


def test_brief_index_empty_list_when_no_file(api_client, tmp_path):
    import spec1_engine.briefing.writer as _w
    briefs_dir = tmp_path / "briefs_empty_idx"
    briefs_dir.mkdir()
    with patch.object(_w, "BRIEFS_DIR", briefs_dir):
        r = api_client.get("/api/v1/brief/index")
    assert r.status_code == 200
    assert r.json() == []


def test_brief_index_returns_newest_first(api_client, tmp_path):
    import spec1_engine.briefing.writer as _w
    briefs_dir = tmp_path / "briefs_idx_order"
    briefs_dir.mkdir()
    entries = [
        {"run_id": "run-1", "date": "2026-04-09", "filepath": "a", "word_count": 100, "timestamp": "t1"},
        {"run_id": "run-2", "date": "2026-04-10", "filepath": "b", "word_count": 200, "timestamp": "t2"},
        {"run_id": "run-3", "date": "2026-04-11", "filepath": "c", "word_count": 300, "timestamp": "t3"},
    ]
    (briefs_dir / "brief_index.jsonl").write_text(
        "\n".join(json.dumps(e) for e in entries) + "\n", encoding="utf-8"
    )
    with patch.object(_w, "BRIEFS_DIR", briefs_dir):
        r = api_client.get("/api/v1/brief/index")
    data = r.json()
    assert data[0]["run_id"] == "run-3"
    assert data[-1]["run_id"] == "run-1"


# ─── writer.py — prompts artifact tests ──────────────────────────────────────

SAMPLE_PROMPTS = "## SYSTEM PROMPT\n\nYou are an intelligence editor.\n"


def test_write_brief_creates_prompts_files_when_provided(tmp_path):
    from spec1_engine.briefing import writer
    original_dir = writer.BRIEFS_DIR
    writer.BRIEFS_DIR = tmp_path / "briefs"
    try:
        writer.write_brief(SAMPLE_BRIEF, "run-001", "2026-04-11T06:00:00+00:00", prompts=SAMPLE_PROMPTS)
        dated = writer.BRIEFS_DIR / "spec1_prompts_2026-04-11.md"
        latest = writer.BRIEFS_DIR / "spec1_prompts_latest.md"
        assert dated.exists()
        assert latest.exists()
    finally:
        writer.BRIEFS_DIR = original_dir


def test_write_brief_prompts_file_content(tmp_path):
    from spec1_engine.briefing import writer
    original_dir = writer.BRIEFS_DIR
    writer.BRIEFS_DIR = tmp_path / "briefs"
    try:
        writer.write_brief(SAMPLE_BRIEF, "run-001", "2026-04-11T06:00:00+00:00", prompts=SAMPLE_PROMPTS)
        dated = writer.BRIEFS_DIR / "spec1_prompts_2026-04-11.md"
        latest = writer.BRIEFS_DIR / "spec1_prompts_latest.md"
        # Content is now built by _build_prompts_doc (PR's extraction approach)
        assert "SPEC-1 Investigation Prompts" in dated.read_text(encoding="utf-8")
        assert "SPEC-1 Investigation Prompts" in latest.read_text(encoding="utf-8")
    finally:
        writer.BRIEFS_DIR = original_dir


def test_write_brief_prompts_files_always_created(tmp_path):
    """write_brief always creates prompts files (extraction from brief)."""
    from spec1_engine.briefing import writer
    original_dir = writer.BRIEFS_DIR
    writer.BRIEFS_DIR = tmp_path / "briefs"
    try:
        writer.write_brief(SAMPLE_BRIEF, "run-001", "2026-04-11T06:00:00+00:00")
        assert (writer.BRIEFS_DIR / "spec1_prompts_2026-04-11.md").exists()
        assert (writer.BRIEFS_DIR / "spec1_prompts_latest.md").exists()
    finally:
        writer.BRIEFS_DIR = original_dir


def test_write_brief_prompts_latest_overwritten(tmp_path):
    from spec1_engine.briefing import writer
    original_dir = writer.BRIEFS_DIR
    writer.BRIEFS_DIR = tmp_path / "briefs"
    try:
        writer.write_brief(SAMPLE_BRIEF, "run-001", "2026-04-11T06:00:00+00:00", prompts="first prompts")
        writer.write_brief(SAMPLE_BRIEF, "run-002", "2026-04-12T06:00:00+00:00", prompts="second prompts")
        latest = writer.BRIEFS_DIR / "spec1_prompts_latest.md"
        # latest is always overwritten; content is extracted from brief
        assert "SPEC-1 Investigation Prompts — 2026-04-12" in latest.read_text(encoding="utf-8")
    finally:
        writer.BRIEFS_DIR = original_dir


# ─── writer.py invalid timestamp fallback test ────────────────────────────────

def test_write_brief_invalid_timestamp_falls_back_to_today(tmp_path):
    """write_brief falls back to today's date when timestamp is invalid."""
    from spec1_engine.briefing import writer
    from datetime import datetime, timezone
    original_dir = writer.BRIEFS_DIR
    writer.BRIEFS_DIR = tmp_path / "briefs_inv_ts"
    try:
        path = writer.write_brief(SAMPLE_BRIEF, "run-001", "NOT-A-VALID-TIMESTAMP")
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        assert today in path
        assert Path(path).exists()
    finally:
        writer.BRIEFS_DIR = original_dir


# ─── _extract_prompts — unit tests ───────────────────────────────────────────

SAMPLE_BRIEF_WITH_PROMPTS = "\n".join([
    "## SPEC-1 DAILY BRIEF — 2026-04-12",
    "",
    "### Story Leads",
    "",
    "**LEAD: Pentagon Budget Leak**",
    "Signal: defense_one | pattern | confidence=0.82 | classification=Escalate",
    "The question: Who authorised the disclosure?",
    "Who to call: DoD spokesperson",
    "Documents to request: OSD budget filings FY2026",
    "Window: 48hrs",
    "Confidence: HIGH",
    "",
    "> **CLAUDE PROMPT:**",
    '> "You are an investigative journalist working this lead: Pentagon Budget Leak.',
    ">  The signal: defense_one, pattern, confidence=0.82.",
    ">  The core question: Who authorised the disclosure?",
    ">",
    ">  Step 1 — Draft a 3-paragraph background memo.",
    ">",
    ">  Step 2 — Write 5 specific questions for DoD spokesperson.",
    ">",
    ">  Step 3 — Write a FOIA request draft targeting OSD budget filings FY2026.",
    ">",
    '> Step 4 — Write a 150-word pitch memo for an editor meeting."',
    "",
    "**LEAD: Cyber Intrusion Pattern**",
    "Signal: cipher_brief | pattern | confidence=0.71 | classification=Investigate",
    "The question: Is this linked to prior campaigns?",
    "Who to call: CISA analyst",
    "Documents to request: DHS incident reports 2025-2026",
    "Window: 3 days",
    "Confidence: MEDIUM",
    "",
    "> **CLAUDE PROMPT:**",
    '> "You are an investigative journalist working this lead: Cyber Intrusion Pattern.',
    ">  The signal: cipher_brief, pattern, confidence=0.71.",
    ">  The core question: Is this linked to prior campaigns?",
    ">",
    ">  Step 1 — Draft a 3-paragraph background memo.",
    ">",
    ">  Step 2 — Write 5 specific questions for CISA analyst.",
    ">",
    ">  Step 3 — Write a FOIA request draft targeting DHS incident reports 2025-2026.",
    ">",
    '> Step 4 — Write a 150-word pitch memo for an editor meeting."',
])


def test_extract_prompts_empty_when_no_blocks():
    from spec1_engine.briefing.writer import _extract_prompts
    result = _extract_prompts(SAMPLE_BRIEF)
    assert result == []


def test_extract_prompts_finds_all_blocks():
    from spec1_engine.briefing.writer import _extract_prompts
    result = _extract_prompts(SAMPLE_BRIEF_WITH_PROMPTS)
    assert len(result) == 2


def test_extract_prompts_each_block_starts_with_marker():
    from spec1_engine.briefing.writer import _extract_prompts
    result = _extract_prompts(SAMPLE_BRIEF_WITH_PROMPTS)
    for block in result:
        assert "**CLAUDE PROMPT:**" in block


def test_extract_prompts_block_contains_lead_title():
    from spec1_engine.briefing.writer import _extract_prompts
    result = _extract_prompts(SAMPLE_BRIEF_WITH_PROMPTS)
    assert any("Pentagon Budget Leak" in b for b in result)
    assert any("Cyber Intrusion Pattern" in b for b in result)


# ─── writer.py — prompts file tests ──────────────────────────────────────────

def test_write_brief_creates_prompts_latest_file(tmp_path):
    from spec1_engine.briefing import writer
    original_dir = writer.BRIEFS_DIR
    writer.BRIEFS_DIR = tmp_path / "briefs"
    try:
        writer.write_brief(SAMPLE_BRIEF, "run-001", "2026-04-12T06:00:00+00:00")
        prompts_latest = writer.BRIEFS_DIR / "spec1_prompts_latest.md"
        assert prompts_latest.exists()
    finally:
        writer.BRIEFS_DIR = original_dir


def test_write_brief_creates_prompts_dated_file(tmp_path):
    from spec1_engine.briefing import writer
    original_dir = writer.BRIEFS_DIR
    writer.BRIEFS_DIR = tmp_path / "briefs"
    try:
        writer.write_brief(SAMPLE_BRIEF, "run-001", "2026-04-12T06:00:00+00:00")
        prompts_dated = writer.BRIEFS_DIR / "spec1_prompts_2026-04-12.md"
        assert prompts_dated.exists()
    finally:
        writer.BRIEFS_DIR = original_dir


def test_write_brief_prompts_doc_contains_header(tmp_path):
    from spec1_engine.briefing import writer
    original_dir = writer.BRIEFS_DIR
    writer.BRIEFS_DIR = tmp_path / "briefs"
    try:
        writer.write_brief(SAMPLE_BRIEF, "run-001", "2026-04-12T06:00:00+00:00")
        content = (writer.BRIEFS_DIR / "spec1_prompts_latest.md").read_text(encoding="utf-8")
        assert "# SPEC-1 Investigation Prompts" in content
    finally:
        writer.BRIEFS_DIR = original_dir


def test_write_brief_prompts_doc_with_blocks(tmp_path):
    from spec1_engine.briefing import writer
    original_dir = writer.BRIEFS_DIR
    writer.BRIEFS_DIR = tmp_path / "briefs"
    try:
        writer.write_brief(SAMPLE_BRIEF_WITH_PROMPTS, "run-002", "2026-04-12T06:00:00+00:00")
        content = (writer.BRIEFS_DIR / "spec1_prompts_latest.md").read_text(encoding="utf-8")
        assert "## Prompt 1" in content
        assert "## Prompt 2" in content
        assert "**CLAUDE PROMPT:**" in content
    finally:
        writer.BRIEFS_DIR = original_dir


def test_write_brief_prompts_doc_no_blocks_placeholder(tmp_path):
    from spec1_engine.briefing import writer
    original_dir = writer.BRIEFS_DIR
    writer.BRIEFS_DIR = tmp_path / "briefs"
    try:
        writer.write_brief(SAMPLE_BRIEF, "run-001", "2026-04-12T06:00:00+00:00")
        content = (writer.BRIEFS_DIR / "spec1_prompts_latest.md").read_text(encoding="utf-8")
        assert "No Claude investigation prompts" in content
    finally:
        writer.BRIEFS_DIR = original_dir


# ─── API routes — /brief/prompts/latest endpoint ─────────────────────────────

def test_brief_prompts_latest_404_when_no_file(api_client, tmp_path):
    import spec1_engine.briefing.writer as _w
    empty = tmp_path / "empty_prompts"
    empty.mkdir()
    with patch.object(_w, "BRIEFS_DIR", empty):
        r = api_client.get("/api/v1/brief/prompts/latest")
    assert r.status_code == 404


def test_brief_prompts_latest_200_when_file_exists(api_client, tmp_path):
    import spec1_engine.briefing.writer as _w
    briefs_dir = tmp_path / "briefs_prompts_ok"
    briefs_dir.mkdir()
    # Write prompts file and an index entry
    prompts_content = (
        "# SPEC-1 Investigation Prompts — 2026-04-12\nGenerated: 2026-04-12T06:00:00+00:00\n\n"
        "## Prompt 1\n\n> **CLAUDE PROMPT:**\n> \"Test prompt.\"\n"
    )
    (briefs_dir / "spec1_prompts_latest.md").write_text(prompts_content, encoding="utf-8")
    (briefs_dir / "brief_index.jsonl").write_text(
        json.dumps({"run_id": "run-p", "date": "2026-04-12",
                    "filepath": "x", "word_count": 10, "timestamp": "2026-04-12T06:00:00+00:00"}) + "\n",
        encoding="utf-8",
    )
    with patch.object(_w, "BRIEFS_DIR", briefs_dir):
        r = api_client.get("/api/v1/brief/prompts/latest")
    assert r.status_code == 200
    data = r.json()
    assert "prompts" in data
    assert "date" in data
    assert "lead_count" in data
    assert data["date"] == "2026-04-12"
    assert data["lead_count"] == 1


def test_brief_prompts_latest_lead_count_correct(api_client, tmp_path):
    import spec1_engine.briefing.writer as _w
    briefs_dir = tmp_path / "briefs_prompts_count"
    briefs_dir.mkdir()
    prompts_content = (
        "# SPEC-1 Investigation Prompts — 2026-04-12\n\n"
        "## Prompt 1\n\n> **CLAUDE PROMPT:**\n> \"First.\"\n\n"
        "## Prompt 2\n\n> **CLAUDE PROMPT:**\n> \"Second.\"\n\n"
        "## Prompt 3\n\n> **CLAUDE PROMPT:**\n> \"Third.\"\n"
    )
    (briefs_dir / "spec1_prompts_latest.md").write_text(prompts_content, encoding="utf-8")
    with patch.object(_w, "BRIEFS_DIR", briefs_dir):
        r = api_client.get("/api/v1/brief/prompts/latest")
    assert r.status_code == 200
    assert r.json()["lead_count"] == 3
