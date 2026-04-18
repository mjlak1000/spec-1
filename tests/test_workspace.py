"""Tests for the investigation workspace."""

import pytest
import json
from pathlib import Path
from unittest.mock import patch, MagicMock
from datetime import datetime

from spec1_engine.schemas.models import Signal, CaseFile
from spec1_engine.workspace.case import (
    open_case,
    update_case,
    close_case,
    list_cases,
    get_case,
)
from spec1_engine.workspace.tracker import match_signals_to_cases
from spec1_engine.workspace.researcher import run_research


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def temp_workspace(tmp_path, monkeypatch):
    """Use temp directory for workspace."""
    workspace_dir = tmp_path / "workspace"
    workspace_dir.mkdir()

    # Monkey patch the workspace paths
    import spec1_engine.workspace.case as case_module
    case_module.WORKSPACE_DIR = workspace_dir
    case_module.CASES_DIR = workspace_dir / "cases"
    case_module.REPORTS_DIR = workspace_dir / "reports"
    case_module.INDEX_FILE = workspace_dir / "case_index.jsonl"

    return workspace_dir


@pytest.fixture
def sample_signal():
    """Create a sample signal."""
    return Signal(
        signal_id="sig_1234567890abcdef",
        source="war_on_the_rocks",
        source_type="publication",
        text="APT29 credential phishing campaign targeting defense contractors",
        url="https://example.com/apt29",
        author="Jane Analyst",
        published_at=datetime.now(),
        velocity=0.8,
        engagement=0.6,
        run_id="run-123",
        environment="osint",
        metadata={"tags": ["cyber", "apt29"]},
    )


@pytest.fixture
def apt29_signal():
    """Signal about APT29."""
    return Signal(
        signal_id="sig_apt29_0001",
        source="cipher_brief",
        source_type="publication",
        text="APT29 activity detected targeting US defense supply chains",
        url="https://example.com/apt29-signal",
        author="Analyst",
        published_at=datetime.now(),
        velocity=0.7,
        engagement=0.5,
        run_id="run-123",
        environment="osint",
        metadata={"region": "US", "sector": "defense"},
    )


@pytest.fixture
def unrelated_signal():
    """Signal unrelated to any case."""
    return Signal(
        signal_id="sig_other_0001",
        source="reuters",
        source_type="publication",
        text="European trade agreement signed",
        url="https://example.com/trade",
        author="Reuters",
        published_at=datetime.now(),
        velocity=0.4,
        engagement=0.3,
        run_id="run-123",
        environment="osint",
    )


# ── Case management tests ─────────────────────────────────────────────────────

def test_open_case_creates_file_and_index(temp_workspace):
    """Test: open_case creates case file and index entry."""
    case = open_case(
        "APT29 Targeting",
        "Is APT29 running a campaign?",
        ["apt29", "cyber", "defense"],
    )

    assert case.case_id.startswith("case-")
    assert case.title == "APT29 Targeting"
    assert case.status == "OPEN"
    assert case.confidence == 0.5

    # Check file exists
    case_file = temp_workspace / "cases" / f"case_{case.case_id}.json"
    assert case_file.exists()

    # Check index entry
    index_file = temp_workspace / "case_index.jsonl"
    assert index_file.exists()
    with open(index_file) as f:
        lines = f.readlines()
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["case_id"] == case.case_id
        assert entry["status"] == "OPEN"


def test_open_case_initializes_empty_signals_and_findings(temp_workspace):
    """Test: open_case initializes empty signal_ids and findings."""
    case = open_case("Test", "Test question", ["test"])

    assert case.signal_ids == []
    assert case.findings == []
    assert case.research_runs == 0


def test_list_cases_returns_all_open_cases(temp_workspace):
    """Test: list_cases returns all OPEN cases."""
    case1 = open_case("Case 1", "Question 1", ["tag1"])
    case2 = open_case("Case 2", "Question 2", ["tag2"])

    cases = list_cases(status="OPEN")
    assert len(cases) == 2
    assert any(c.case_id == case1.case_id for c in cases)
    assert any(c.case_id == case2.case_id for c in cases)


def test_update_case_appends_signals_and_finding(temp_workspace, apt29_signal):
    """Test: update_case appends signal and finding correctly."""
    case = open_case("Test", "Test?", ["apt29"])

    finding = "New evidence suggests APT29 is escalating"
    updated = update_case(case.case_id, [apt29_signal], finding)

    assert apt29_signal.signal_id in updated.signal_ids
    assert finding in updated.findings
    assert updated.research_runs == 1
    assert updated.updated_at != case.opened_at


def test_update_case_multiple_times(temp_workspace, apt29_signal):
    """Test: update_case can be called multiple times."""
    case = open_case("Test", "Test?", ["apt29"])

    update_case(case.case_id, [apt29_signal], "Finding 1")
    updated = update_case(case.case_id, [apt29_signal], "Finding 2")

    assert len(updated.findings) == 2
    assert updated.research_runs == 2


def test_close_case_sets_status_and_generates_report(temp_workspace):
    """Test: close_case sets status=CLOSED and writes report."""
    case = open_case("Test", "Test question?", ["test"])
    case = update_case(case.case_id, [], "Test finding")

    closed = close_case(case.case_id)

    assert closed.status == "CLOSED"

    # Check report exists
    report_file = temp_workspace / "reports" / f"report_{case.case_id}.md"
    assert report_file.exists()

    # Check report content
    with open(report_file) as f:
        content = f.read()
        assert "Test" in content
        assert "Test question?" in content


def test_get_case_retrieves_case_by_id(temp_workspace):
    """Test: get_case retrieves a case by ID."""
    case = open_case("Retrieve Test", "Can we find it?", ["test"])

    retrieved = get_case(case.case_id)

    assert retrieved.case_id == case.case_id
    assert retrieved.title == "Retrieve Test"


def test_get_case_raises_on_missing_case(temp_workspace):
    """Test: get_case raises ValueError for missing case."""
    with pytest.raises(ValueError):
        get_case("case-nonexistent")


# ── Signal matching tests ─────────────────────────────────────────────────────

def test_tracker_matches_signal_to_case_by_tag(temp_workspace, apt29_signal):
    """Test: tracker matches signal to case by tag."""
    case = open_case(
        "APT29 Targeting",
        "Is APT29 targeting defense?",
        ["apt29", "credential", "defense"],
    )

    matches = match_signals_to_cases([apt29_signal])

    assert case.case_id in matches
    assert len(matches[case.case_id]) == 1
    assert matches[case.case_id][0].signal_id == apt29_signal.signal_id


def test_tracker_returns_empty_for_no_match(temp_workspace, unrelated_signal):
    """Test: tracker returns empty list for no match."""
    case = open_case("APT29", "APT29?", ["apt29", "cyber"])

    matches = match_signals_to_cases([unrelated_signal])

    # Case exists, but no match
    assert matches.get(case.case_id, []) == []


def test_tracker_case_insensitive_matching(temp_workspace):
    """Test: tracker matching is case-insensitive."""
    case = open_case("Test", "Test?", ["APT29"])

    signal = Signal(
        signal_id="sig_test",
        source="test",
        source_type="publication",
        text="apt29 activity detected",
        url="https://example.com/test",
        author="Test",
        published_at=datetime.now(),
        velocity=0.5,
        engagement=0.4,
        run_id="run-123",
        environment="osint",
    )

    matches = match_signals_to_cases([signal])

    assert case.case_id in matches
    assert len(matches[case.case_id]) == 1


def test_tracker_matches_on_metadata(temp_workspace):
    """Test: tracker matches signals with tags in metadata."""
    case = open_case("Test", "Test?", ["defense"])

    signal = Signal(
        signal_id="sig_test",
        source="test",
        source_type="publication",
        text="Nothing interesting here",
        url="https://example.com/test",
        author="Test",
        published_at=datetime.now(),
        velocity=0.5,
        engagement=0.4,
        run_id="run-123",
        environment="osint",
        metadata={"sector": "defense"},
    )

    matches = match_signals_to_cases([signal])

    assert case.case_id in matches
    assert len(matches[case.case_id]) == 1


# ── Researcher tests ──────────────────────────────────────────────────────────

def test_researcher_returns_fallback_without_anthropic():
    """Test: researcher returns fallback when Anthropic not installed."""
    case = CaseFile(
        case_id="case-test",
        title="Test",
        question="Test?",
        tags=["test"],
    )

    signal = Signal(
        signal_id="sig_test",
        source="test",
        source_type="publication",
        text="Test signal",
        url="https://example.com/test",
        author="Test",
        published_at=datetime.now(),
        velocity=0.5,
        engagement=0.4,
        run_id="run-123",
        environment="osint",
    )

    # Mock anthropic import to raise ImportError
    with patch.dict("sys.modules", {"anthropic": None}):
        result = run_research(case, [signal])

        assert "not installed" in result.lower()


def test_researcher_returns_empty_for_no_signals():
    """Test: researcher returns empty string for no signals."""
    case = CaseFile(
        case_id="case-test",
        title="Test",
        question="Test?",
        tags=["test"],
    )

    result = run_research(case, [])

    assert result == ""


@patch("spec1_engine.workspace.researcher._anthropic")
def test_researcher_calls_claude_sonnet_4(mock_anthropic):
    """Test: researcher calls Claude Sonnet 4 model."""
    mock_client = MagicMock()
    mock_anthropic.Anthropic.return_value = mock_client

    mock_response = MagicMock()
    mock_response.content[0].text = "Finding text"
    mock_response.usage.input_tokens = 100
    mock_response.usage.output_tokens = 50
    mock_client.messages.create.return_value = mock_response

    case = CaseFile(
        case_id="case-test",
        title="Test Case",
        question="Test question?",
        tags=["test"],
        findings=[],
    )

    signal = Signal(
        signal_id="sig_test",
        source="test_source",
        source_type="publication",
        text="Test signal text",
        url="https://example.com/test",
        author="Test",
        published_at=datetime.now(),
        velocity=0.5,
        engagement=0.4,
        run_id="run-123",
        environment="osint",
    )

    result = run_research(case, [signal])

    assert result == "Finding text"

    # Check that Sonnet 4 model was called
    mock_client.messages.create.assert_called_once()
    call_kwargs = mock_client.messages.create.call_args[1]
    assert call_kwargs["model"] == "claude-sonnet-4-20250514"
    assert call_kwargs["max_tokens"] == 2000


@patch("spec1_engine.workspace.researcher._anthropic")
def test_researcher_returns_fallback_on_api_error(mock_anthropic):
    """Test: researcher returns fallback on API failure."""
    mock_client = MagicMock()
    mock_anthropic.Anthropic.return_value = mock_client
    mock_client.messages.create.side_effect = Exception("API Error")

    case = CaseFile(
        case_id="case-test",
        title="Test",
        question="Test?",
        tags=["test"],
    )

    signal = Signal(
        signal_id="sig_test",
        source="test",
        source_type="publication",
        text="Test",
        url="https://example.com/test",
        author="Test",
        published_at=datetime.now(),
        velocity=0.5,
        engagement=0.4,
        run_id="run-123",
        environment="osint",
    )

    result = run_research(case, [signal])

    assert "unavailable" in result.lower()


# ── Confidence calculation tests ──────────────────────────────────────────────

def test_confidence_updated_on_finding_with_high(temp_workspace):
    """Test: confidence increases with HIGH confidence findings."""
    case = open_case("Test", "Test?", ["test"])

    finding_high = "HIGH confidence: strong evidence found"
    update_case(case.case_id, [], finding_high)

    updated = get_case(case.case_id)
    assert updated.confidence == 1.0


def test_confidence_updated_on_finding_with_medium(temp_workspace):
    """Test: confidence with MEDIUM confidence finding."""
    case = open_case("Test", "Test?", ["test"])

    finding_medium = "MEDIUM confidence: some evidence"
    update_case(case.case_id, [], finding_medium)

    updated = get_case(case.case_id)
    assert updated.confidence == 0.5


def test_confidence_updated_on_finding_with_low(temp_workspace):
    """Test: confidence decreases with LOW confidence findings."""
    case = open_case("Test", "Test?", ["test"])

    finding_low = "LOW confidence: weak evidence"
    update_case(case.case_id, [], finding_low)

    updated = get_case(case.case_id)
    assert updated.confidence == 0.0


def test_confidence_averaged_across_findings(temp_workspace):
    """Test: confidence is averaged across multiple findings."""
    case = open_case("Test", "Test?", ["test"])

    update_case(case.case_id, [], "HIGH confidence: strong")
    update_case(case.case_id, [], "LOW confidence: weak")

    updated = get_case(case.case_id)
    # Average: (1.0 + 0.0) / 2 = 0.5
    assert updated.confidence == 0.5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
