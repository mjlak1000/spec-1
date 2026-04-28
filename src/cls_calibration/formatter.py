"""Markdown rendering for ProposalReport."""

from __future__ import annotations

from cls_calibration.schemas import ProposalReport


_SEVERITY_ORDER = {"large": 0, "moderate": 1, "small": 2}


def to_markdown(report: ProposalReport) -> str:
    """Render a ProposalReport as a human-readable markdown document.

    Designed for the calibration_propose CLI to write into generated/.
    """
    lines: list[str] = []
    lines.append("# SPEC-1 Calibration Proposal")
    lines.append("")
    lines.append(f"_Generated: {report.generated_at}_")
    lines.append("")
    lines.append(
        f"Floors: sample_size ≥ **{report.sample_floor}**, "
        f"|delta| ≥ **{report.delta_floor:.2f}**."
    )
    lines.append("")

    if not report.adjustments:
        lines.append("No drift signals exceed the configured floors. Nothing to surface.")
        lines.append("")
        return "\n".join(lines)

    by_severity: dict[str, list] = {"large": [], "moderate": [], "small": []}
    for adj in report.adjustments:
        by_severity.setdefault(adj.severity, []).append(adj)

    for severity in ("large", "moderate", "small"):
        items = by_severity.get(severity, [])
        if not items:
            continue
        lines.append(f"## {severity.title()} drift ({len(items)})")
        lines.append("")
        lines.append("| target_kind | target_id | expected | observed | delta | n |")
        lines.append("|---|---|---:|---:|---:|---:|")
        for a in items:
            lines.append(
                f"| {a.target_kind} | `{a.target_id}` | {a.expected:.2f} | "
                f"{a.observed:.2f} | {a.delta:+.2f} | {a.sample_size} |"
            )
        lines.append("")
        lines.append("**Rationale**")
        lines.append("")
        for a in items:
            lines.append(f"- {a.rationale}")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append(
        "_This report is descriptive only. Apply changes by editing the "
        "relevant constants by hand (e.g. `CLASSIFICATION_WEIGHTS` in "
        "`spec1_engine.intelligence.analyzer`, `SOURCE_CREDIBILITY` in "
        "`spec1_engine.signal.scorer`) and bumping the version per "
        "CLAUDE.md governance._"
    )
    lines.append("")
    return "\n".join(lines)
