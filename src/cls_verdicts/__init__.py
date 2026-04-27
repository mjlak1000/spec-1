"""cls_verdicts — human verdicts on intelligence records (Phase 1 of feedback loop).

A Verdict is a piece of human ground truth: "this IntelligenceRecord
was actually correct / incorrect / partial / unclear." Verdicts are
the input that closes the calibration loop on the four-gate scoring
framework. Aggregation lives in cls_calibration (Phase 2).

The store is append-only JSONL — multiple verdicts may be filed for
the same record over time (different reviewers, change of mind), and
none are overwritten. Aggregators decide how to fold them.
"""

from cls_verdicts.schemas import Verdict, VerdictKind
from cls_verdicts.store import VerdictStore

__all__ = ["Verdict", "VerdictKind", "VerdictStore"]
