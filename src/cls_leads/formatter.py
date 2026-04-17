"""Lead formatter — renders Lead objects for human consumption."""

from __future__ import annotations

from cls_leads.schemas import Lead

_PRIORITY_ICONS = {
    "CRITICAL": "[!!!]",
    "HIGH": "[!!]",
    "MEDIUM": "[!]",
    "LOW": "[-]",
}

_PRIORITY_COLORS = {
    "CRITICAL": "red",
    "HIGH": "orange",
    "MEDIUM": "yellow",
    "LOW": "blue",
}


def lead_to_text(lead: Lead) -> str:
    """Render a single Lead as human-readable plain text."""
    icon = _PRIORITY_ICONS.get(lead.priority, "[?]")
    lines = [
        f"{icon} [{lead.priority}] {lead.title}",
        f"   Category : {lead.category}",
        f"   Confidence: {lead.confidence:.0%}",
        f"   Generated : {lead.generated_at.strftime('%Y-%m-%d %H:%M UTC') if hasattr(lead.generated_at, 'strftime') else lead.generated_at}",
        "",
        f"   {lead.summary}",
        "",
    ]
    if lead.action_items:
        lines.append("   Actions:")
        for item in lead.action_items:
            lines.append(f"     • {item}")
        lines.append("")
    return "\n".join(lines)


def leads_to_text(leads: list[Lead]) -> str:
    """Render a list of leads as a plain-text report."""
    if not leads:
        return "No actionable leads generated.\n"
    header = f"SPEC-1 INTELLIGENCE LEADS — {len(leads)} item(s)\n" + "=" * 60 + "\n"
    body = "\n".join(lead_to_text(l) for l in leads)
    return header + body


def lead_to_markdown(lead: Lead) -> str:
    """Render a single Lead as Markdown."""
    icon = _PRIORITY_ICONS.get(lead.priority, "[?]")
    lines = [
        f"### {icon} {lead.title}",
        "",
        f"| Field | Value |",
        f"|-------|-------|",
        f"| Priority | **{lead.priority}** |",
        f"| Category | {lead.category} |",
        f"| Confidence | {lead.confidence:.0%} |",
        f"| Generated | {lead.generated_at.strftime('%Y-%m-%d %H:%M UTC') if hasattr(lead.generated_at, 'strftime') else lead.generated_at} |",
        "",
        lead.summary,
        "",
    ]
    if lead.action_items:
        lines.append("**Actions:**")
        for item in lead.action_items:
            lines.append(f"- {item}")
        lines.append("")
    return "\n".join(lines)


def leads_to_markdown(leads: list[Lead]) -> str:
    """Render a list of leads as a Markdown document."""
    if not leads:
        return "# SPEC-1 Intelligence Leads\n\nNo actionable leads generated.\n"
    lines = [
        f"# SPEC-1 Intelligence Leads — {len(leads)} item(s)",
        "",
    ]
    for lead in leads:
        lines.append(lead_to_markdown(lead))
        lines.append("---")
        lines.append("")
    return "\n".join(lines)


def leads_to_json(leads: list[Lead]) -> list[dict]:
    """Return list of lead dicts suitable for JSON serialisation."""
    return [l.to_dict() for l in leads]
