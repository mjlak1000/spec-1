"""Calibration aggregator — folds verdicts onto records to produce reports."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

from cls_calibration.schemas import Bucket, CalibrationReport


# Reliability buckets. Edges define [lo, hi) intervals; the last bucket is closed.
_RELIABILITY_EDGES: tuple[float, ...] = (0.0, 0.2, 0.4, 0.6, 0.8, 1.0)


def score_verdict(kind: str) -> float | None:
    """Map a verdict kind to a [0,1] score. Returns None for 'unclear'."""
    if kind == "correct":
        return 1.0
    if kind == "partial":
        return 0.5
    if kind == "incorrect":
        return 0.0
    return None  # 'unclear' or unknown — excluded from accuracy


def _bucket_label(value: float) -> str:
    """Return the reliability bucket label that a 0..1 value falls into."""
    if value < 0.0:
        value = 0.0
    if value > 1.0:
        value = 1.0
    edges = _RELIABILITY_EDGES
    for i in range(len(edges) - 1):
        lo, hi = edges[i], edges[i + 1]
        if i == len(edges) - 2:
            # last bucket is inclusive on the right
            if lo <= value <= hi:
                return f"{lo:.1f}-{hi:.1f}"
        else:
            if lo <= value < hi:
                return f"{lo:.1f}-{hi:.1f}"
    return "out-of-range"


def _tally(bucket: Bucket, kind: str) -> None:
    bucket.count += 1
    if kind == "correct":
        bucket.correct += 1
    elif kind == "incorrect":
        bucket.incorrect += 1
    elif kind == "partial":
        bucket.partial += 1
    else:
        bucket.unclear += 1


def produce_report(
    records: Iterable[dict],
    verdicts: Iterable[dict],
) -> CalibrationReport:
    """Build a CalibrationReport from intelligence records and verdicts.

    Records are joined to verdicts on `record_id`. Verdicts referencing a
    record_id not present in `records` are counted as unmatched and do
    not contribute to per-classification or reliability buckets.
    """
    records_by_id: dict[str, dict] = {}
    for r in records:
        rid = r.get("record_id")
        if rid:
            records_by_id[rid] = r

    report = CalibrationReport(
        generated_at=datetime.now(timezone.utc).isoformat(),
        total_records=len(records_by_id),
    )

    for v in verdicts:
        report.total_verdicts += 1
        rid = v.get("record_id")
        kind = v.get("verdict", "unclear")

        # Always count toward overall — verdicts without a matching record
        # still tell us about review activity, just not about calibration.
        record = records_by_id.get(rid) if rid else None
        if record is None:
            report.unmatched_verdicts += 1
            _tally(report.overall, kind)
            continue

        report.matched_verdicts += 1
        _tally(report.overall, kind)

        classification = str(record.get("classification", "UNKNOWN")).upper()
        bucket = report.by_classification.setdefault(classification, Bucket(label=classification))
        _tally(bucket, kind)

        for field_name, target in (
            ("confidence", report.by_confidence_bucket),
            ("source_weight", report.by_source_weight_bucket),
            ("analyst_weight", report.by_analyst_weight_bucket),
        ):
            raw = record.get(field_name)
            if isinstance(raw, (int, float)):
                label = _bucket_label(float(raw))
                b = target.setdefault(label, Bucket(label=label))
                _tally(b, kind)

    return report
