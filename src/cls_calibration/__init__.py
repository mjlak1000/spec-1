"""cls_calibration — feedback-loop aggregation (phase 2).

Reads stored intelligence records and human verdicts (cls_verdicts) and
produces a CalibrationReport: overall accuracy, per-classification
accuracy, and reliability buckets across confidence, source_weight, and
analyst_weight. The report is descriptive — it surfaces drift, it does
not auto-tune anything. Calibration changes stay a human decision per
the project's "deterministic, legible" design philosophy.
"""

from cls_calibration.schemas import (
    Bucket,
    CalibrationReport,
    ProposalReport,
    SuggestedAdjustment,
)
from cls_calibration.aggregator import produce_report, score_verdict
from cls_calibration.proposer import propose_adjustments
from cls_calibration.formatter import to_markdown

__all__ = [
    "Bucket",
    "CalibrationReport",
    "ProposalReport",
    "SuggestedAdjustment",
    "produce_report",
    "score_verdict",
    "propose_adjustments",
    "to_markdown",
]
