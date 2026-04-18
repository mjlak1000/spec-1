"""Frozen core package for SPEC-1 Intelligence Engine.

This package contains all authoritative schemas, scoring contracts,
prompt definitions, and version metadata.

IMMUTABILITY RULE
-----------------
No agent or automated module may write to ``core/``.
All imports flow *from* ``core/`` outward to the rest of the codebase.

Changes to any file in this package require:
1. A human code review.
2. A version bump in :mod:`spec1_engine.core.version`.
3. A corresponding entry in ``CHANGELOG.md``.

Public API
----------
Import canonical types directly from this package::

    from spec1_engine.core import Signal, Opportunity, __version__
"""

from __future__ import annotations

from spec1_engine.core.schemas import (
    AnalystRecord,
    CaseFile,
    IntelligenceRecord,
    Investigation,
    Opportunity,
    Outcome,
    ParsedSignal,
    Signal,
)
from spec1_engine.core.version import (
    RELEASE_NAME,
    VERSION,
    __version__,
    bump_version,
)
from spec1_engine.core.contracts import (
    CREDIBILITY_THRESHOLD,
    DEFAULT_CREDIBILITY,
    GATE_DESCRIPTIONS,
    GATE_NAMES,
    NOVELTY_TERMS,
    NOVELTY_THRESHOLD,
    PRIMARY_SOURCE_CREDIBILITY,
    LEGACY_SOURCE_CREDIBILITY,
    SOURCE_CREDIBILITY,
    VALID_CLASSIFICATIONS,
    VELOCITY_THRESHOLD,
    VOLUME_THRESHOLD,
    VOLUME_TIERS,
    CREDIBILITY_WEIGHT,
    VOLUME_WEIGHT,
    VELOCITY_WEIGHT,
    NOVELTY_WEIGHT,
    PRIORITY_ELEVATED_THRESHOLD,
    PRIORITY_STANDARD_THRESHOLD,
    PRIORITY_LABELS,
)

__all__ = [
    # ── Canonical data models ────────────────────────────────────────────────
    "Signal",
    "ParsedSignal",
    "Opportunity",
    "Investigation",
    "Outcome",
    "IntelligenceRecord",
    "AnalystRecord",
    "CaseFile",
    # ── Version metadata ─────────────────────────────────────────────────────
    "__version__",
    "VERSION",
    "RELEASE_NAME",
    "bump_version",
    # ── Scoring contracts ────────────────────────────────────────────────────
    "SOURCE_CREDIBILITY",
    "PRIMARY_SOURCE_CREDIBILITY",
    "LEGACY_SOURCE_CREDIBILITY",
    "DEFAULT_CREDIBILITY",
    "CREDIBILITY_THRESHOLD",
    "VOLUME_TIERS",
    "VOLUME_THRESHOLD",
    "VELOCITY_THRESHOLD",
    "NOVELTY_TERMS",
    "NOVELTY_THRESHOLD",
    "CREDIBILITY_WEIGHT",
    "VOLUME_WEIGHT",
    "VELOCITY_WEIGHT",
    "NOVELTY_WEIGHT",
    "PRIORITY_ELEVATED_THRESHOLD",
    "PRIORITY_STANDARD_THRESHOLD",
    "PRIORITY_LABELS",
    "VALID_CLASSIFICATIONS",
    "GATE_NAMES",
    "GATE_DESCRIPTIONS",
]
