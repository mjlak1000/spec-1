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
]
