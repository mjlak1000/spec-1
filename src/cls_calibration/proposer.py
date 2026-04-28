"""Calibration proposer — turns a CalibrationReport into suggested adjustments.

Output is descriptive only. Every adjustment is something a human is
expected to read, evaluate, and apply (or not) by hand. Per the project's
governance, gate thresholds and source-credibility weights are the
calibrated decisions the system is built around — they don't change
automatically.
"""

from __future__ import annotations

from datetime import datetime, timezone

from cls_calibration.schemas import (
    Bucket,
    CalibrationReport,
    ProposalReport,
    SuggestedAdjustment,
)


# Ports of analyzer.py weight tables. Pulled in as constants here so the
# proposer can compare observed accuracy against the value the system
# currently asserts for each outcome.
CLASSIFICATION_WEIGHTS: dict[str, float] = {
    "CORROBORATED": 1.0,
    "ESCALATE": 0.85,
    "INVESTIGATE": 0.70,
    "MONITOR": 0.55,
    "CONFLICTED": 0.35,
    "ARCHIVE": 0.15,
}


def _bucket_midpoint(label: str) -> float | None:
    """Return the centre of a 'lo-hi' reliability bucket label, or None if unparsable."""
    try:
        lo_s, hi_s = label.split("-", 1)
        return (float(lo_s) + float(hi_s)) / 2.0
    except (ValueError, AttributeError):
        return None


def _severity(delta: float, sample_size: int) -> str:
    """Heuristic severity tag — used to sort / triage proposals."""
    abs_delta = abs(delta)
    if abs_delta < 0.10 or sample_size < 10:
        return "small"
    if abs_delta < 0.25:
        return "moderate"
    return "large"


def _direction(delta: float) -> str:
    return "overconfident" if delta < 0 else "underconfident"


def _adjust_from_bucket(
    *,
    target_kind: str,
    target_id: str,
    expected: float,
    bucket: Bucket,
    sample_floor: int,
    delta_floor: float,
) -> SuggestedAdjustment | None:
    """Build a SuggestedAdjustment for a bucket if it clears the floors."""
    observed = bucket.accuracy
    if observed is None or bucket.scored < sample_floor:
        return None
    delta = observed - expected
    if abs(delta) < delta_floor:
        return None
    severity = _severity(delta, bucket.scored)
    rationale = (
        f"{target_kind.replace('_', ' ').title()} `{target_id}` is {_direction(delta)}: "
        f"system expects {expected:.2f} accuracy, verdicts show {observed:.2f} "
        f"(n={bucket.scored}, delta={delta:+.2f})."
    )
    return SuggestedAdjustment(
        target_kind=target_kind,
        target_id=target_id,
        expected=expected,
        observed=observed,
        delta=delta,
        sample_size=bucket.scored,
        severity=severity,
        rationale=rationale,
    )


def propose_adjustments(
    report: CalibrationReport,
    *,
    sample_floor: int = 5,
    delta_floor: float = 0.15,
) -> ProposalReport:
    """Walk a CalibrationReport and emit SuggestedAdjustments wherever drift exceeds the floors.

    sample_floor: minimum scored verdicts in a bucket before we'll suggest anything
    delta_floor:  minimum |observed - expected| for the suggestion to be worth surfacing
    """
    adjustments: list[SuggestedAdjustment] = []

    # Per-classification: expected = CLASSIFICATION_WEIGHTS[name]
    for name, bucket in report.by_classification.items():
        expected = CLASSIFICATION_WEIGHTS.get(name)
        if expected is None:
            continue
        adj = _adjust_from_bucket(
            target_kind="classification",
            target_id=name,
            expected=expected,
            bucket=bucket,
            sample_floor=sample_floor,
            delta_floor=delta_floor,
        )
        if adj is not None:
            adjustments.append(adj)

    # Reliability buckets: expected = bucket midpoint
    for kind, source in (
        ("confidence_bucket", report.by_confidence_bucket),
        ("source_weight_bucket", report.by_source_weight_bucket),
        ("analyst_weight_bucket", report.by_analyst_weight_bucket),
    ):
        for label, bucket in source.items():
            mid = _bucket_midpoint(label)
            if mid is None:
                continue
            adj = _adjust_from_bucket(
                target_kind=kind,
                target_id=label,
                expected=mid,
                bucket=bucket,
                sample_floor=sample_floor,
                delta_floor=delta_floor,
            )
            if adj is not None:
                adjustments.append(adj)

    # Sort: largest absolute delta first, then largest sample size — surfaces the
    # most actionable drift signals at the top of the report.
    adjustments.sort(key=lambda a: (-abs(a.delta), -a.sample_size))

    return ProposalReport(
        generated_at=datetime.now(timezone.utc).isoformat(),
        sample_floor=sample_floor,
        delta_floor=delta_floor,
        adjustments=adjustments,
    )
