"""Schemas for cls_calibration."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Bucket:
    """A single calibration bucket — counts of each verdict kind plus accuracy.

    Accuracy scoring: correct = 1.0, partial = 0.5, incorrect = 0.0.
    'unclear' verdicts are excluded from the denominator.
    """

    label: str
    count: int = 0
    correct: int = 0
    incorrect: int = 0
    partial: int = 0
    unclear: int = 0

    @property
    def scored(self) -> int:
        """Number of verdicts that contribute to accuracy (excludes 'unclear')."""
        return self.correct + self.incorrect + self.partial

    @property
    def accuracy(self) -> float | None:
        """Weighted accuracy in [0, 1], or None if there are no scored verdicts."""
        if self.scored == 0:
            return None
        return (self.correct + 0.5 * self.partial) / self.scored

    def to_dict(self) -> dict:
        return {
            "label": self.label,
            "count": self.count,
            "correct": self.correct,
            "incorrect": self.incorrect,
            "partial": self.partial,
            "unclear": self.unclear,
            "scored": self.scored,
            "accuracy": self.accuracy,
        }


@dataclass
class SuggestedAdjustment:
    """A single calibration drift signal — observation + recommendation, never auto-applied.

    target_kind: which calibrated dimension drifted
        ('confidence_bucket' | 'source_weight_bucket' | 'analyst_weight_bucket' | 'classification')
    target_id:   bucket label ('0.8-1.0') or classification name ('CORROBORATED')
    expected:    the calibration the system currently asserts (e.g. midpoint of a confidence
                 bucket, or CLASSIFICATION_WEIGHTS[name] for an outcome)
    observed:    the accuracy verdicts actually showed
    delta:       observed - expected (negative = the system is overconfident here)
    sample_size: number of *scored* verdicts (excludes 'unclear')
    severity:    'small' | 'moderate' | 'large' — based on |delta| and sample_size
    rationale:   human-readable explanation suitable for a markdown report
    """

    target_kind: str
    target_id: str
    expected: float
    observed: float
    delta: float
    sample_size: int
    severity: str
    rationale: str

    def to_dict(self) -> dict:
        return {
            "target_kind": self.target_kind,
            "target_id": self.target_id,
            "expected": round(self.expected, 4),
            "observed": round(self.observed, 4),
            "delta": round(self.delta, 4),
            "sample_size": self.sample_size,
            "severity": self.severity,
            "rationale": self.rationale,
        }


@dataclass
class ProposalReport:
    """A list of suggested adjustments derived from a CalibrationReport.

    Descriptive only. The plan deliberately keeps the apply step a human
    code change — gate thresholds and source credibility weights are the
    'frozen decisions' the project is built around.
    """

    generated_at: str
    sample_floor: int
    delta_floor: float
    adjustments: list[SuggestedAdjustment] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "generated_at": self.generated_at,
            "sample_floor": self.sample_floor,
            "delta_floor": self.delta_floor,
            "adjustments": [a.to_dict() for a in self.adjustments],
        }


@dataclass
class CalibrationReport:
    """Top-level calibration report produced by aggregator.produce_report."""

    generated_at: str
    total_records: int = 0
    total_verdicts: int = 0
    matched_verdicts: int = 0       # verdicts whose record_id was found in records
    unmatched_verdicts: int = 0
    overall: Bucket = field(default_factory=lambda: Bucket(label="overall"))
    by_classification: dict[str, Bucket] = field(default_factory=dict)
    by_confidence_bucket: dict[str, Bucket] = field(default_factory=dict)
    by_source_weight_bucket: dict[str, Bucket] = field(default_factory=dict)
    by_analyst_weight_bucket: dict[str, Bucket] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "generated_at": self.generated_at,
            "total_records": self.total_records,
            "total_verdicts": self.total_verdicts,
            "matched_verdicts": self.matched_verdicts,
            "unmatched_verdicts": self.unmatched_verdicts,
            "overall": self.overall.to_dict(),
            "by_classification": {k: b.to_dict() for k, b in self.by_classification.items()},
            "by_confidence_bucket": {k: b.to_dict() for k, b in self.by_confidence_bucket.items()},
            "by_source_weight_bucket": {k: b.to_dict() for k, b in self.by_source_weight_bucket.items()},
            "by_analyst_weight_bucket": {k: b.to_dict() for k, b in self.by_analyst_weight_bucket.items()},
        }
