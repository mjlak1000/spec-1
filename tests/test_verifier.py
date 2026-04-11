"""Tests for the Claude-backed investigation verifier."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from spec1_engine.schemas.models import Investigation, Outcome
from spec1_engine.investigation.verifier import (
    verify_investigation,
    _build_user_prompt,
    _fallback_outcome,
    VALID_CLASSIFICATIONS,
    MODEL,
)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def make_investigation(
    hypothesis: str = "Russian forces may be repositioning near Kharkiv.",
    queries: list[str] | None = None,
    sources: list[str] | None = None,
    leads: list[str] | None = None,
) -> Investigation:
    return Investigation(
        investigation_id="inv-test-001",
        opportunity_id="opp-test-001",
        hypothesis=hypothesis,
        queries=queries or ["Is there satellite imagery corroborating movement?", "Any official statements?"],
        sources_to_check=sources or ["War on the Rocks", "ISW", "RAND"],
        analyst_leads=leads or ["Michael Kofman", "Dara Massicot"],
    )


def make_mock_response(payload: dict) -> MagicMock:
    """Build a mock anthropic Messages response."""
    content_block = MagicMock()
    content_block.text = json.dumps(payload)
    response = MagicMock()
    response.content = [content_block]
    return response


# ─── Unit: _fallback_outcome ──────────────────────────────────────────────────

def test_fallback_outcome_returns_outcome():
    out = _fallback_outcome()
    assert isinstance(out, Outcome)


def test_fallback_outcome_classification_is_investigate():
    out = _fallback_outcome()
    assert out.classification == "Investigate"


def test_fallback_outcome_confidence_is_zero():
    out = _fallback_outcome()
    assert out.confidence == 0.0


def test_fallback_outcome_has_evidence():
    out = _fallback_outcome()
    assert len(out.evidence) > 0


def test_fallback_outcome_ids_are_unique():
    a = _fallback_outcome()
    b = _fallback_outcome()
    assert a.outcome_id != b.outcome_id


# ─── Unit: _build_user_prompt ─────────────────────────────────────────────────

def test_build_user_prompt_contains_hypothesis():
    inv = make_investigation()
    prompt = _build_user_prompt(inv)
    assert inv.hypothesis in prompt


def test_build_user_prompt_contains_queries():
    inv = make_investigation()
    prompt = _build_user_prompt(inv)
    for q in inv.queries:
        assert q in prompt


def test_build_user_prompt_contains_sources():
    inv = make_investigation()
    prompt = _build_user_prompt(inv)
    for s in inv.sources_to_check:
        assert s in prompt


def test_build_user_prompt_contains_analyst_leads():
    inv = make_investigation()
    prompt = _build_user_prompt(inv)
    for a in inv.analyst_leads:
        assert a in prompt


def test_build_user_prompt_no_leads():
    inv = make_investigation(leads=[])
    prompt = _build_user_prompt(inv)
    assert "Hypothesis" in prompt  # still builds without leads


# ─── Unit: constants ──────────────────────────────────────────────────────────

def test_valid_classifications_complete():
    expected = {"Corroborated", "Escalate", "Investigate", "Monitor", "Conflicted", "Archive"}
    assert VALID_CLASSIFICATIONS == expected


def test_model_is_haiku():
    assert MODEL == "claude-haiku-4-5-20251001"


# ─── Integration: successful Claude response → Corroborated ──────────────────

def test_successful_verification_corroborated():
    """Mock a successful Claude call returning Corroborated."""
    inv = make_investigation()
    payload = {
        "verified": True,
        "confidence": 0.87,
        "reasoning": "Multiple authoritative sources corroborate the hypothesis.",
        "classification": "Corroborated",
    }
    mock_response = make_mock_response(payload)

    with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
        with patch("anthropic.Anthropic") as MockClient:
            instance = MockClient.return_value
            instance.messages.create.return_value = mock_response

            outcome = verify_investigation(inv)

    assert isinstance(outcome, Outcome)
    assert outcome.classification == "Corroborated"
    assert outcome.confidence == pytest.approx(0.87)
    assert outcome.outcome_id.startswith("out-")


def test_successful_verification_escalate():
    """Mock a Claude call returning Escalate classification."""
    inv = make_investigation()
    payload = {
        "verified": True,
        "confidence": 0.72,
        "reasoning": "Partial corroboration, warrants escalation.",
        "classification": "Escalate",
    }
    mock_response = make_mock_response(payload)

    with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
        with patch("anthropic.Anthropic") as MockClient:
            instance = MockClient.return_value
            instance.messages.create.return_value = mock_response

            outcome = verify_investigation(inv)

    assert outcome.classification == "Escalate"
    assert outcome.confidence == pytest.approx(0.72)


def test_successful_verification_evidence_includes_reasoning():
    """Reasoning from Claude should appear in evidence."""
    inv = make_investigation()
    reasoning = "Strong satellite imagery confirms redeployment."
    payload = {
        "verified": True,
        "confidence": 0.90,
        "reasoning": reasoning,
        "classification": "Corroborated",
    }
    mock_response = make_mock_response(payload)

    with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
        with patch("anthropic.Anthropic") as MockClient:
            instance = MockClient.return_value
            instance.messages.create.return_value = mock_response

            outcome = verify_investigation(inv)

    assert any(reasoning in e for e in outcome.evidence)


def test_successful_verification_verified_false():
    """Claude returns verified=False — still produces a valid Outcome."""
    inv = make_investigation()
    payload = {
        "verified": False,
        "confidence": 0.30,
        "reasoning": "Insufficient evidence to confirm.",
        "classification": "Monitor",
    }
    mock_response = make_mock_response(payload)

    with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
        with patch("anthropic.Anthropic") as MockClient:
            instance = MockClient.return_value
            instance.messages.create.return_value = mock_response

            outcome = verify_investigation(inv)

    assert outcome.classification == "Monitor"
    assert outcome.confidence == pytest.approx(0.30)


def test_successful_verification_confidence_clamped_high():
    """Confidence > 1.0 from Claude is clamped to 1.0."""
    inv = make_investigation()
    payload = {
        "verified": True,
        "confidence": 1.5,
        "reasoning": "Very high confidence.",
        "classification": "Corroborated",
    }
    mock_response = make_mock_response(payload)

    with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
        with patch("anthropic.Anthropic") as MockClient:
            instance = MockClient.return_value
            instance.messages.create.return_value = mock_response

            outcome = verify_investigation(inv)

    assert outcome.confidence <= 1.0


def test_successful_verification_confidence_clamped_low():
    """Confidence < 0.0 from Claude is clamped to 0.0."""
    inv = make_investigation()
    payload = {
        "verified": False,
        "confidence": -0.5,
        "reasoning": "No evidence.",
        "classification": "Archive",
    }
    mock_response = make_mock_response(payload)

    with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
        with patch("anthropic.Anthropic") as MockClient:
            instance = MockClient.return_value
            instance.messages.create.return_value = mock_response

            outcome = verify_investigation(inv)

    assert outcome.confidence >= 0.0


def test_invalid_classification_falls_back_to_investigate():
    """Unknown classification from Claude defaults to Investigate."""
    inv = make_investigation()
    payload = {
        "verified": True,
        "confidence": 0.75,
        "reasoning": "Seems legit.",
        "classification": "BOGUS_CLASS",
    }
    mock_response = make_mock_response(payload)

    with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
        with patch("anthropic.Anthropic") as MockClient:
            instance = MockClient.return_value
            instance.messages.create.return_value = mock_response

            outcome = verify_investigation(inv)

    assert outcome.classification == "Investigate"


# ─── API failure → fallback, no exception raised ─────────────────────────────

def test_api_failure_returns_fallback():
    """API raises an exception — should return fallback Outcome, not crash."""
    inv = make_investigation()

    with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
        with patch("anthropic.Anthropic") as MockClient:
            instance = MockClient.return_value
            instance.messages.create.side_effect = Exception("Connection timeout")

            outcome = verify_investigation(inv)

    assert isinstance(outcome, Outcome)
    assert outcome.classification == "Investigate"
    assert outcome.confidence == 0.0


def test_api_failure_does_not_raise():
    """Verify no exception propagates from an API failure."""
    inv = make_investigation()

    with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
        with patch("anthropic.Anthropic") as MockClient:
            instance = MockClient.return_value
            instance.messages.create.side_effect = RuntimeError("Network error")

            try:
                verify_investigation(inv)
            except Exception as exc:
                pytest.fail(f"verify_investigation raised unexpectedly: {exc}")


def test_api_rate_limit_returns_fallback():
    """Rate limit error returns fallback gracefully."""
    inv = make_investigation()

    with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
        with patch("anthropic.Anthropic") as MockClient:
            instance = MockClient.return_value
            instance.messages.create.side_effect = Exception("rate_limit_error")

            outcome = verify_investigation(inv)

    assert outcome.classification == "Investigate"


# ─── Malformed JSON response → fallback, no exception raised ─────────────────

def test_malformed_json_returns_fallback():
    """Non-JSON response from Claude falls back gracefully."""
    inv = make_investigation()

    content_block = MagicMock()
    content_block.text = "Sorry, I cannot answer that."
    mock_response = MagicMock()
    mock_response.content = [content_block]

    with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
        with patch("anthropic.Anthropic") as MockClient:
            instance = MockClient.return_value
            instance.messages.create.return_value = mock_response

            outcome = verify_investigation(inv)

    assert isinstance(outcome, Outcome)
    assert outcome.classification == "Investigate"
    assert outcome.confidence == 0.0


def test_malformed_json_does_not_raise():
    """Malformed JSON must never propagate an exception."""
    inv = make_investigation()

    content_block = MagicMock()
    content_block.text = "{not valid json{{{"
    mock_response = MagicMock()
    mock_response.content = [content_block]

    with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
        with patch("anthropic.Anthropic") as MockClient:
            instance = MockClient.return_value
            instance.messages.create.return_value = mock_response

            try:
                verify_investigation(inv)
            except Exception as exc:
                pytest.fail(f"verify_investigation raised unexpectedly: {exc}")


def test_empty_json_object_returns_fallback_values():
    """Empty JSON {} uses defaults — classification=Investigate, confidence=0.0."""
    inv = make_investigation()

    content_block = MagicMock()
    content_block.text = "{}"
    mock_response = MagicMock()
    mock_response.content = [content_block]

    with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
        with patch("anthropic.Anthropic") as MockClient:
            instance = MockClient.return_value
            instance.messages.create.return_value = mock_response

            outcome = verify_investigation(inv)

    assert outcome.classification == "Investigate"
    assert outcome.confidence == 0.0


# ─── No API key → fallback immediately ───────────────────────────────────────

def test_no_api_key_returns_fallback():
    """Missing ANTHROPIC_API_KEY returns fallback without calling the API."""
    inv = make_investigation()

    with patch.dict("os.environ", {}, clear=True):
        # Ensure key is absent
        import os
        os.environ.pop("ANTHROPIC_API_KEY", None)

        with patch("anthropic.Anthropic") as MockClient:
            outcome = verify_investigation(inv)
            MockClient.assert_not_called()

    assert outcome.classification == "Investigate"
    assert outcome.confidence == 0.0


def test_no_api_key_does_not_raise():
    """No API key must never raise."""
    inv = make_investigation()

    with patch.dict("os.environ", {}, clear=True):
        import os
        os.environ.pop("ANTHROPIC_API_KEY", None)

        try:
            verify_investigation(inv)
        except Exception as exc:
            pytest.fail(f"verify_investigation raised unexpectedly: {exc}")


# ─── Output structure ─────────────────────────────────────────────────────────

def test_outcome_has_required_fields():
    """Outcome always has outcome_id, classification, confidence, evidence."""
    inv = make_investigation()

    with patch.dict("os.environ", {}, clear=True):
        import os
        os.environ.pop("ANTHROPIC_API_KEY", None)
        outcome = verify_investigation(inv)

    assert hasattr(outcome, "outcome_id")
    assert hasattr(outcome, "classification")
    assert hasattr(outcome, "confidence")
    assert hasattr(outcome, "evidence")


def test_outcome_to_dict():
    """Outcome.to_dict() returns expected keys."""
    inv = make_investigation()
    with patch.dict("os.environ", {}, clear=True):
        import os
        os.environ.pop("ANTHROPIC_API_KEY", None)
        outcome = verify_investigation(inv)

    d = outcome.to_dict()
    assert "outcome_id" in d
    assert "classification" in d
    assert "confidence" in d
    assert "evidence" in d


def test_all_valid_classifications_accepted():
    """Verify every valid classification passes through correctly."""
    for cls in VALID_CLASSIFICATIONS:
        inv = make_investigation()
        payload = {
            "verified": True,
            "confidence": 0.5,
            "reasoning": "Test.",
            "classification": cls,
        }
        mock_response = make_mock_response(payload)

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            with patch("anthropic.Anthropic") as MockClient:
                instance = MockClient.return_value
                instance.messages.create.return_value = mock_response

                outcome = verify_investigation(inv)

        assert outcome.classification == cls, f"Expected {cls}, got {outcome.classification}"
