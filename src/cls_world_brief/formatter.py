"""World brief formatter — renders WorldBrief to Markdown and plain text."""

from __future__ import annotations

from cls_world_brief.schemas import WorldBrief


def to_markdown(brief: WorldBrief) -> str:
    """Render a WorldBrief as a Markdown document."""
    lines: list[str] = []
    lines.append(f"# SPEC-1 World Intelligence Brief — {brief.date}")
    lines.append("")
    lines.append(f"**{brief.headline}**")
    lines.append("")
    lines.append(f"*Produced: {brief.produced_at.strftime('%Y-%m-%d %H:%M UTC') if hasattr(brief.produced_at, 'strftime') else brief.produced_at}*")
    lines.append(f"*Confidence: {brief.confidence:.0%}*")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Executive Summary")
    lines.append("")
    lines.append(brief.summary)
    lines.append("")

    if brief.sections:
        lines.append("---")
        lines.append("")
        for section in brief.sections:
            if section.body.strip():
                lines.append(f"## {section.title}")
                lines.append("")
                lines.append(section.body)
                lines.append("")

    if brief.sources:
        lines.append("---")
        lines.append("")
        lines.append("## Sources")
        lines.append("")
        for i, url in enumerate(brief.sources[:15], 1):
            lines.append(f"{i}. {url}")
        lines.append("")

    return "\n".join(lines)


def to_plain_text(brief: WorldBrief) -> str:
    """Render a WorldBrief as plain text (no Markdown syntax)."""
    lines: list[str] = []
    sep = "=" * 60

    lines.append(sep)
    lines.append(f"SPEC-1 WORLD INTELLIGENCE BRIEF — {brief.date}")
    lines.append(sep)
    lines.append("")
    lines.append(brief.headline.upper())
    lines.append("")
    produced = (
        brief.produced_at.strftime("%Y-%m-%d %H:%M UTC")
        if hasattr(brief.produced_at, "strftime")
        else str(brief.produced_at)
    )
    lines.append(f"Produced: {produced}  |  Confidence: {brief.confidence:.0%}")
    lines.append("")
    lines.append("EXECUTIVE SUMMARY")
    lines.append("-" * 40)
    lines.append(brief.summary)
    lines.append("")

    for section in brief.sections:
        if section.body.strip():
            lines.append(section.title.upper())
            lines.append("-" * 40)
            lines.append(section.body)
            lines.append("")

    if brief.sources:
        lines.append("SOURCES")
        lines.append("-" * 40)
        for i, url in enumerate(brief.sources[:15], 1):
            lines.append(f"  {i}. {url}")
        lines.append("")

    lines.append(sep)
    return "\n".join(lines)


def to_json_summary(brief: WorldBrief) -> dict:
    """Return a lightweight JSON-serialisable summary of the brief."""
    return {
        "brief_id": brief.brief_id,
        "date": brief.date,
        "headline": brief.headline,
        "sections": [s.title for s in brief.sections if s.body.strip()],
        "confidence": brief.confidence,
        "source_count": len(brief.sources),
        "produced_at": brief.produced_at.isoformat()
        if hasattr(brief.produced_at, "isoformat")
        else str(brief.produced_at),
    }
