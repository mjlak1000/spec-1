"""World brief producer.

Assembles a WorldBrief from IntelligenceRecords and OSINTRecords
using a rule-based approach (no LLM required; LLM path is optional).
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Sequence

from cls_world_brief.schemas import BriefSection, WorldBrief

# Topic clusters used to build brief sections
_SECTION_TOPICS: list[tuple[str, list[str]]] = [
    ("Military & Defense", ["defense", "military", "army", "navy", "air force", "nato", "pentagon"]),
    ("Intelligence & Cyber", ["intelligence", "cyber", "espionage", "hack", "cia", "nsa", "spying"]),
    ("Geopolitics", ["china", "russia", "iran", "north korea", "ukraine", "taiwan", "sanctions"]),
    ("Terrorism & Extremism", ["terrorism", "isis", "jihad", "extremism", "insurgency", "al-qaeda"]),
    ("US Congress & Policy", ["congress", "senate", "house", "legislation", "bill", "budget", "ndaa"]),
    ("Foreign Agents (FARA)", ["fara", "foreign agent", "lobbying", "registrant", "foreign principal"]),
    ("Influence Operations", ["narrative", "disinformation", "influence", "propaganda", "psyop"]),
]


def _score_text_for_topic(text: str, keywords: list[str]) -> int:
    text_lower = text.lower()
    return sum(1 for kw in keywords if kw in text_lower)


def _build_headline(records: list[dict]) -> str:
    """Derive a headline from the highest-scoring records."""
    if not records:
        return "No significant intelligence activity detected."
    # Use the first high-confidence record text as basis
    top = sorted(records, key=lambda r: r.get("confidence", r.get("reach_score", 0.5)), reverse=True)
    for r in top[:3]:
        text = r.get("content", r.get("pattern", r.get("theme", "")))
        if text and len(text) > 20:
            # Truncate to ~120 chars
            return text[:120].rstrip() + ("..." if len(text) > 120 else "")
    return "Multiple intelligence signals detected across sources."


def _build_summary(sections: list[BriefSection], total_records: int) -> str:
    """Build a 2-3 paragraph executive summary from sections."""
    date_str = datetime.now(timezone.utc).strftime("%d %B %Y")
    active_sections = [s for s in sections if s.body.strip()]
    section_titles = ", ".join(s.title for s in active_sections[:4])

    para1 = (
        f"SPEC-1 intelligence cycle completed on {date_str}, processing {total_records} "
        f"signals from open sources. Key activity detected across: {section_titles or 'multiple domains'}."
    )
    para2_parts = []
    for sec in active_sections[:3]:
        first_sentence = sec.body.split(".")[0].strip()
        if first_sentence:
            para2_parts.append(first_sentence)
    para2 = ". ".join(para2_parts) + "." if para2_parts else "Analysis ongoing."

    para3 = (
        f"A total of {len(active_sections)} intelligence domain(s) show elevated activity. "
        "Analysts should prioritise records classified as Corroborated or Escalate."
    )
    return "\n\n".join([para1, para2, para3])


def _records_for_section(
    records: list[dict], keywords: list[str], max_items: int = 5
) -> tuple[list[str], list[str]]:
    """Return (body_lines, source_urls) for records matching keywords."""
    matching = []
    for rec in records:
        text = rec.get("content", rec.get("pattern", rec.get("theme", "")))
        if _score_text_for_topic(text, keywords) >= 1:
            matching.append(rec)

    matching.sort(
        key=lambda r: r.get("confidence", r.get("reach_score", r.get("score", 0.5))),
        reverse=True,
    )
    lines: list[str] = []
    urls: list[str] = []
    ids: list[str] = []
    for rec in matching[:max_items]:
        text = rec.get("content", rec.get("pattern", ""))
        if text:
            lines.append(f"• {text[:200].rstrip()}")
        url = rec.get("url", rec.get("doc_url", ""))
        if url:
            urls.append(url)
        rid = rec.get("record_id", rec.get("signal_id", ""))
        if rid:
            ids.append(rid)
    return lines, urls, ids


def produce_brief(
    records: Sequence[dict],
    date: str | None = None,
) -> WorldBrief:
    """Produce a WorldBrief from a list of record dicts.

    Works with IntelligenceRecord, OSINTRecord, or any dict with a 'content' key.
    """
    records_list = list(records)
    if date is None:
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    brief_id = WorldBrief.make_id(date)
    all_sources: list[str] = []
    sections: list[BriefSection] = []

    for section_title, keywords in _SECTION_TOPICS:
        lines, urls, ids = _records_for_section(records_list, keywords)
        all_sources.extend(urls)
        if lines:
            body = "\n".join(lines)
            sections.append(BriefSection(title=section_title, body=body, source_record_ids=ids))

    headline = _build_headline(records_list)
    summary = _build_summary(sections, len(records_list))
    confidence = min(1.0, len(records_list) / 20) if records_list else 0.0
    confidence = round(confidence, 3)

    return WorldBrief(
        brief_id=brief_id,
        date=date,
        headline=headline,
        summary=summary,
        sections=sections,
        sources=list(dict.fromkeys(all_sources))[:20],  # deduplicate, keep order
        confidence=confidence,
        produced_at=datetime.now(timezone.utc),
        metadata={"total_records_processed": len(records_list)},
    )
