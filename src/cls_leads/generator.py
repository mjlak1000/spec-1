"""Lead generator — derives actionable leads from intelligence records."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Sequence

from cls_leads.schemas import Lead

# Priority rules: (keywords, priority, category)
_PRIORITY_RULES: list[tuple[list[str], str, str]] = [
    # CRITICAL
    (["nuclear", "wmd", "dirty bomb", "radiological", "bioweapon"], "CRITICAL", "military"),
    (["invasion", "attack", "airstrike", "missile launch", "troops cross"], "CRITICAL", "military"),
    (["chemical attack", "chlorine", "sarin", "nerve agent"], "CRITICAL", "military"),
    # HIGH
    (["escalation", "mobilization", "troop build", "naval blockade", "no-fly zone"], "HIGH", "military"),
    (["apt41", "apt10", "volt typhoon", "critical infrastructure hack"], "HIGH", "cyber"),
    (["election interference", "voter system breach", "campaign hack"], "HIGH", "cyber"),
    (["sanctions", "asset freeze", "regime change"], "HIGH", "geopolitical"),
    (["fara", "foreign agent", "lobbying", "undisclosed foreign"], "HIGH", "fara"),
    (["influence operation", "disinformation campaign", "narrative injection"], "HIGH", "psyop"),
    # MEDIUM
    (["military exercise", "joint drill", "wargame", "troop deployment"], "MEDIUM", "military"),
    (["cyber espionage", "data breach", "phishing campaign", "ransomware"], "MEDIUM", "cyber"),
    (["diplomatic tension", "ambassador recalled", "consulate closed"], "MEDIUM", "geopolitical"),
    (["propaganda", "state media", "narrative amplification"], "MEDIUM", "psyop"),
    (["bill introduced", "legislation", "congressional hearing"], "MEDIUM", "geopolitical"),
    # LOW (catch-all)
    (["report", "analysis", "assessment", "intelligence"], "LOW", "geopolitical"),
]


def _score_record(text: str) -> tuple[str, str]:
    """Return (priority, category) for a record's text."""
    text_lower = text.lower()
    for keywords, priority, category in _PRIORITY_RULES:
        if any(kw in text_lower for kw in keywords):
            return priority, category
    return "LOW", "geopolitical"


def _build_action_items(priority: str, category: str, text: str) -> list[str]:
    """Generate action items based on priority and category."""
    actions: list[str] = []
    if priority == "CRITICAL":
        actions.append("Escalate immediately to senior analyst")
        actions.append("Cross-reference with additional classified sources")
        actions.append("Prepare incident brief within 2 hours")
    elif priority == "HIGH":
        actions.append("Review and verify within 4 hours")
        actions.append("Cross-reference with existing case files")
    elif priority == "MEDIUM":
        actions.append("Include in next daily brief")
        actions.append("Monitor for further developments")
    else:
        actions.append("File for background monitoring")

    category_actions = {
        "cyber": ["Notify SOC team", "Check for related IOCs"],
        "fara": ["Review DOJ FARA database for full filing", "Check related registrants"],
        "psyop": ["Map amplification network", "Assess reach and target audience"],
        "military": ["Check ORBAT implications", "Review force posture"],
    }
    actions.extend(category_actions.get(category, []))
    return actions


def generate_leads(
    records: Sequence[dict],
    min_confidence: float = 0.3,
    max_leads: int = 50,
) -> list[Lead]:
    """Generate Lead objects from a list of record dicts.

    Each qualifying record produces at most one lead.
    Leads are sorted by priority (CRITICAL → HIGH → MEDIUM → LOW).
    """
    now = datetime.now(timezone.utc)
    leads: list[Lead] = []
    priority_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}

    for rec in records:
        confidence = float(rec.get("confidence", rec.get("reach_score", rec.get("score", 0.5))))
        if confidence < min_confidence:
            continue

        # Extract text
        text = rec.get("content", rec.get("pattern", rec.get("theme", rec.get("title", ""))))
        if not text:
            continue

        priority, category = _score_record(text)
        title = text[:80].rstrip("., ") + ("..." if len(text) > 80 else "")
        summary = text[:300]
        record_id = rec.get("record_id", rec.get("signal_id", rec.get("lead_id", "")))
        action_items = _build_action_items(priority, category, text)

        generated_at_str = now.isoformat()
        lead_id = Lead.make_id(title, generated_at_str)

        leads.append(
            Lead(
                lead_id=lead_id,
                title=title,
                summary=summary,
                priority=priority,
                category=category,
                source_record_ids=[record_id] if record_id else [],
                action_items=action_items,
                confidence=confidence,
                generated_at=now,
                metadata={"source_type": rec.get("source_type", "unknown")},
            )
        )

    # Sort by priority
    leads.sort(key=lambda l: priority_order.get(l.priority, 99))
    return leads[:max_leads]


def generate_from_intelligence(
    intel_records: Sequence[dict],
    osint_records: Sequence[dict] | None = None,
) -> list[Lead]:
    """Generate leads from intelligence records, optionally enriched with OSINT."""
    all_records = list(intel_records)
    if osint_records:
        all_records.extend(osint_records)
    return generate_leads(all_records)
