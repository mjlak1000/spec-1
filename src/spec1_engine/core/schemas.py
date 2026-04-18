"""Canonical data models for SPEC-1 Intelligence Engine.

This file is part of the frozen core package. It defines all authoritative
dataclasses used throughout the pipeline.

IMMUTABILITY RULE: No agent or module may write to ``core/``.
All imports flow *from* ``core/`` outward.
"""

from __future__ import annotations

# ── stdlib ──────────────────────────────────────────────────────────────────
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class Signal:
    """Raw signal harvested from an RSS feed or OSINT source.

    Attributes:
        signal_id: Deterministic hex ID derived from URL + title.
        source: Human-readable source key (e.g. ``"war_on_the_rocks"``).
        source_type: Broad category (e.g. ``"rss"``, ``"fara"``, ``"congress"``).
        text: Full raw text or HTML of the item.
        url: Canonical URL of the source item.
        author: Author name or empty string when unknown.
        published_at: Publication timestamp (timezone-aware).
        velocity: Pre-computed freshness score in ``[0.0, 1.0]``.
        engagement: Social/engagement proxy score in ``[0.0, 1.0]``.
        run_id: Pipeline run that harvested this signal.
        environment: Deployment environment (e.g. ``"osint"``, ``"test"``).
        metadata: Arbitrary extra fields for downstream adapters.
    """

    signal_id: str
    source: str
    source_type: str
    text: str
    url: str
    author: str
    published_at: datetime
    velocity: float
    engagement: float
    run_id: str
    environment: str
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Serialize to a JSON-safe dictionary."""
        return {
            "signal_id": self.signal_id,
            "source": self.source,
            "source_type": self.source_type,
            "text": self.text,
            "url": self.url,
            "author": self.author,
            "published_at": (
                self.published_at.isoformat()
                if isinstance(self.published_at, datetime)
                else str(self.published_at)
            ),
            "velocity": self.velocity,
            "engagement": self.engagement,
            "run_id": self.run_id,
            "environment": self.environment,
            "metadata": self.metadata,
        }


@dataclass
class ParsedSignal:
    """Signal after HTML cleaning, language detection, and keyword extraction.

    Attributes:
        signal_id: Matches the parent :class:`Signal`.
        cleaned_text: Whitespace-normalised, HTML-stripped body text.
        keywords: Extracted high-value terms (lowercased).
        entities: Named entities found by the parser (names, orgs, places).
        language: ISO-639-1 language code (e.g. ``"en"``).
        word_count: Token count of ``cleaned_text``.
    """

    signal_id: str
    cleaned_text: str
    keywords: list[str]
    entities: list[str]
    language: str
    word_count: int

    def to_dict(self) -> dict:
        """Serialize to a JSON-safe dictionary."""
        return {
            "signal_id": self.signal_id,
            "cleaned_text": self.cleaned_text,
            "keywords": self.keywords,
            "entities": self.entities,
            "language": self.language,
            "word_count": self.word_count,
        }


@dataclass
class Opportunity:
    """Signal that has passed all four scoring gates.

    Attributes:
        opportunity_id: Unique identifier (``"opp-<hex>"``).
        signal_id: ID of the originating :class:`Signal`.
        score: Composite float in ``[0.0, 1.0]``.
        priority: Tier label — ``"ELEVATED"``, ``"STANDARD"``, or ``"MONITOR"``.
        gate_results: Boolean pass/fail per gate:
            ``{"credibility": bool, "volume": bool, "velocity": bool, "novelty": bool}``.
        run_id: Pipeline run that scored this opportunity.
    """

    opportunity_id: str
    signal_id: str
    score: float
    priority: str  # "ELEVATED" | "STANDARD" | "MONITOR"
    gate_results: dict  # {"credibility": bool, "volume": bool, "velocity": bool, "novelty": bool}
    run_id: str

    def to_dict(self) -> dict:
        """Serialize to a JSON-safe dictionary."""
        return {
            "opportunity_id": self.opportunity_id,
            "signal_id": self.signal_id,
            "score": self.score,
            "priority": self.priority,
            "gate_results": self.gate_results,
            "run_id": self.run_id,
        }


@dataclass
class Investigation:
    """Investigation generated for a scored opportunity.

    Attributes:
        investigation_id: Unique identifier (``"inv-<hex>"``).
        opportunity_id: ID of the originating :class:`Opportunity`.
        hypothesis: Single-sentence investigative hypothesis.
        queries: List of research questions to pursue.
        sources_to_check: Authoritative URLs or source keys to consult.
        analyst_leads: Named analysts or experts relevant to the hypothesis.
    """

    investigation_id: str
    opportunity_id: str
    hypothesis: str
    queries: list[str]
    sources_to_check: list[str]
    analyst_leads: list[str]

    def to_dict(self) -> dict:
        """Serialize to a JSON-safe dictionary."""
        return {
            "investigation_id": self.investigation_id,
            "opportunity_id": self.opportunity_id,
            "hypothesis": self.hypothesis,
            "queries": self.queries,
            "sources_to_check": self.sources_to_check,
            "analyst_leads": self.analyst_leads,
        }


@dataclass
class Outcome:
    """Outcome of verifying an investigation hypothesis via Claude.

    Attributes:
        outcome_id: Unique identifier (``"out-<hex>"``).
        classification: One of ``"CORROBORATED"``, ``"ESCALATE"``,
            ``"INVESTIGATE"``, ``"MONITOR"``, ``"CONFLICTED"``, ``"ARCHIVE"``.
        confidence: Analyst-assessed confidence in ``[0.0, 1.0]``.
        evidence: Supporting sentences or reasoning fragments.
    """

    outcome_id: str
    classification: str  # "CORROBORATED" | "ESCALATE" | "INVESTIGATE" | "MONITOR" | "CONFLICTED" | "ARCHIVE"
    confidence: float
    evidence: list[str]

    def to_dict(self) -> dict:
        """Serialize to a JSON-safe dictionary."""
        return {
            "outcome_id": self.outcome_id,
            "classification": self.classification,
            "confidence": self.confidence,
            "evidence": self.evidence,
        }


@dataclass
class IntelligenceRecord:
    """Analyzed intelligence record ready for storage and briefing.

    Attributes:
        record_id: Unique identifier (``"rec-<hex>"``).
        pattern: Detected pattern label (e.g. ``"geopolitics"``, ``"cyber"``).
        classification: Outcome classification carried forward from
            :class:`Outcome`.
        confidence: Final composite confidence score in ``[0.0, 1.0]``.
        source_weight: Credibility weight of the originating source.
        analyst_weight: Credibility weight of any associated analyst.
    """

    record_id: str
    pattern: str
    classification: str
    confidence: float
    source_weight: float
    analyst_weight: float

    def to_dict(self) -> dict:
        """Serialize to a JSON-safe dictionary."""
        return {
            "record_id": self.record_id,
            "pattern": self.pattern,
            "classification": self.classification,
            "confidence": self.confidence,
            "source_weight": self.source_weight,
            "analyst_weight": self.analyst_weight,
        }


@dataclass
class AnalystRecord:
    """Known analyst or subject-matter expert record.

    Attributes:
        analyst_id: Unique identifier.
        name: Full name (e.g. ``"Michael Kofman"``).
        affiliation: Organisation or publication.
        domains: Topic areas the analyst covers.
        credibility_score: Weight in ``[0.0, 1.0]`` used by the scorer.
    """

    analyst_id: str
    name: str
    affiliation: str
    domains: list[str]
    credibility_score: float

    def to_dict(self) -> dict:
        """Serialize to a JSON-safe dictionary."""
        return {
            "analyst_id": self.analyst_id,
            "name": self.name,
            "affiliation": self.affiliation,
            "domains": self.domains,
            "credibility_score": self.credibility_score,
        }


@dataclass
class CaseFile:
    """Persistent investigation case that accumulates evidence across cycles.

    Attributes:
        case_id: Unique identifier (``"case-<hex>"``).
        title: Short descriptive title.
        question: Core investigative question.
        tags: Categorisation tags (e.g. ``["cyber", "russia"]``).
        status: Lifecycle state — ``"OPEN"``, ``"CLOSED"``, or ``"WATCHING"``.
        opened_at: UTC timestamp when the case was created.
        updated_at: UTC timestamp of the most recent update.
        signal_ids: IDs of all :class:`Signal` objects linked to this case.
        findings: Accumulated finding sentences.
        research_runs: Number of pipeline cycles this case has participated in.
        confidence: Current composite confidence score in ``[0.0, 1.0]``.
        run_id: Most recent pipeline run that touched this case.
        environment: Deployment environment.
        metadata: Arbitrary extra fields for downstream adapters.
    """

    case_id: str
    title: str
    question: str
    tags: list[str] = field(default_factory=list)
    status: str = "OPEN"  # OPEN | CLOSED | WATCHING
    opened_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    signal_ids: list[str] = field(default_factory=list)
    findings: list[str] = field(default_factory=list)
    research_runs: int = 0
    confidence: float = 0.5
    run_id: str = ""
    environment: str = "osint"
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Serialize to a JSON-safe dictionary."""
        return {
            "case_id": self.case_id,
            "title": self.title,
            "question": self.question,
            "tags": self.tags,
            "status": self.status,
            "opened_at": (
                self.opened_at.isoformat()
                if isinstance(self.opened_at, datetime)
                else str(self.opened_at)
            ),
            "updated_at": (
                self.updated_at.isoformat()
                if isinstance(self.updated_at, datetime)
                else str(self.updated_at)
            ),
            "signal_ids": self.signal_ids,
            "findings": self.findings,
            "research_runs": self.research_runs,
            "confidence": self.confidence,
            "run_id": self.run_id,
            "environment": self.environment,
            "metadata": self.metadata,
        }
