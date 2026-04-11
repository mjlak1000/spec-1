"""Investigation Verifier.

Verifies Investigation instances by analyzing signal evidence and producing Outcome records.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from spec1_engine.schemas.models import Investigation, Outcome, ParsedSignal, Signal

CLASSIFICATION_THRESHOLDS = {
    "Corroborated": 0.80,
    "Escalate": 0.65,
    "Investigate": 0.50,
    "Monitor": 0.35,
    "Conflicted": 0.20,
    "Archive": 0.0,
}

# Evidence strength terms
STRONG_EVIDENCE_TERMS = {
    "confirmed", "verified", "corroborated", "documented", "declassified",
    "official", "statement", "report", "assessment", "analysis",
}
WEAK_EVIDENCE_TERMS = {
    "alleged", "reportedly", "claims", "unconfirmed", "sources say",
    "believed", "rumored", "speculated", "possible", "may",
}

CORROBORATION_SOURCES = {
    "rand", "war_on_the_rocks", "lawfare", "cipher_brief", "atlantic_council",
}


def _calculate_confidence(
    signal: Signal,
    parsed: ParsedSignal,
    investigation: Investigation,
) -> float:
    """Calculate confidence score for the verification."""
    base = 0.40

    # Source credibility boost
    from spec1_engine.signal.scorer import SOURCE_CREDIBILITY, DEFAULT_CREDIBILITY
    credibility = SOURCE_CREDIBILITY.get(signal.source, DEFAULT_CREDIBILITY)
    base += credibility * 0.20

    # Evidence term analysis
    text_lower = parsed.cleaned_text.lower()
    strong_hits = sum(1 for t in STRONG_EVIDENCE_TERMS if t in text_lower)
    weak_hits = sum(1 for t in WEAK_EVIDENCE_TERMS if t in text_lower)
    base += min(strong_hits * 0.05, 0.15)
    base -= min(weak_hits * 0.03, 0.10)

    # Analyst leads boost
    lead_count = len(investigation.analyst_leads)
    base += min(lead_count * 0.02, 0.08)

    # Word count (volume) boost
    if parsed.word_count >= 500:
        base += 0.05
    elif parsed.word_count >= 200:
        base += 0.02

    # Source tier boost
    if signal.source in CORROBORATION_SOURCES:
        base += 0.05

    return round(min(max(base, 0.05), 0.98), 4)


def _classify(confidence: float) -> str:
    """Classify based on confidence score."""
    for classification, threshold in CLASSIFICATION_THRESHOLDS.items():
        if confidence >= threshold:
            return classification
    return "Archive"


def _build_evidence(
    signal: Signal,
    parsed: ParsedSignal,
    investigation: Investigation,
) -> list[str]:
    """Build a list of evidence strings."""
    evidence: list[str] = []

    evidence.append(f"Source: {signal.source.replace('_', ' ').title()} (url: {signal.url})")
    evidence.append(f"Published: {signal.published_at}")

    if investigation.analyst_leads:
        evidence.append(f"Analyst leads identified: {', '.join(investigation.analyst_leads)}")

    if parsed.entities:
        evidence.append(f"Key entities: {', '.join(parsed.entities[:5])}")

    if parsed.keywords:
        evidence.append(f"Key terms: {', '.join(parsed.keywords[:5])}")

    snippet = parsed.cleaned_text[:200].strip()
    if snippet:
        evidence.append(f"Text snippet: {snippet}...")

    return evidence


def verify_investigation(
    investigation: Investigation,
    signal: Signal,
    parsed: ParsedSignal,
) -> Outcome:
    """Verify an investigation and produce an Outcome."""
    confidence = _calculate_confidence(signal, parsed, investigation)
    classification = _classify(confidence)
    evidence = _build_evidence(signal, parsed, investigation)

    return Outcome(
        outcome_id=f"out-{uuid.uuid4().hex[:12]}",
        classification=classification,
        confidence=confidence,
        evidence=evidence,
    )
