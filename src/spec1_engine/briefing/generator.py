"""Daily intelligence brief generator.

Calls Claude Sonnet to write a publishable brief from today's scored records.
Falls back to a raw-stats brief on any API error — never crashes the cycle.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

from dotenv import load_dotenv
load_dotenv()

from spec1_engine.briefing.templates import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE

logger = logging.getLogger(__name__)

MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 2500

# Sources that map to Cyber / Info Ops domain
_CYBER_SOURCES = {
    "cipher_brief", "just_security", "lawfare",
    "cyberscoop", "recordedfuture", "krebs",
}

# Sources that map to Geopolitics domain
_GEO_SOURCES = {
    "war_on_the_rocks", "rand", "atlantic_council",
    "defense_one", "foreign_affairs", "bellingcat",
}


def _classify_domain(record: dict) -> str:
    """Return 'cyber' or 'geo' based on signal source."""
    src = str(record.get("signal_source", "")).lower()
    if src in _CYBER_SOURCES:
        return "cyber"
    # Default geopolitics for national-security OSINT sources
    return "geo"


def _format_record(record: dict) -> str:
    """Format a single record for the prompt — readable, not raw JSON."""
    source = record.get("signal_source", record.get("source", "unknown"))
    pattern = record.get("pattern", "—")
    confidence = record.get("confidence", record.get("outcome_confidence", 0.0))
    classification = record.get("outcome_classification", record.get("classification", "—"))
    priority = record.get("opportunity_priority", "—")
    url = record.get("signal_url", "")
    url_str = f" | {url}" if url else ""
    return (
        f"{source.upper()} | {pattern} | "
        f"confidence={float(confidence):.2f} | classification={classification} | "
        f"priority={priority}{url_str}"
    )


def _build_prompt(records: list[dict], cycle_stats: dict) -> str:
    """Build the filled USER_PROMPT_TEMPLATE string."""
    # Split elevated vs standard
    elevated = [
        r for r in records
        if r.get("outcome_classification", r.get("classification", "")) in ("CORROBORATED", "ESCALATE")
    ]
    remaining = [r for r in records if r not in elevated]
    standard_top10 = sorted(
        remaining,
        key=lambda r: float(r.get("confidence", r.get("outcome_confidence", 0.0))),
        reverse=True,
    )[:10]

    # Domain counts
    geo_count = sum(1 for r in records if _classify_domain(r) == "geo")
    cyber_count = sum(1 for r in records if _classify_domain(r) == "cyber")

    # Format record blocks
    elevated_block = (
        "\n".join(_format_record(r) for r in elevated)
        if elevated else "(none)"
    )
    standard_block = (
        "\n".join(_format_record(r) for r in standard_top10)
        if standard_top10 else "(none)"
    )

    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    return USER_PROMPT_TEMPLATE.format(
        run_id=cycle_stats.get("run_id", "—"),
        timestamp=cycle_stats.get("finished_at", cycle_stats.get("timestamp", "—")),
        signal_count=cycle_stats.get("signals_harvested", cycle_stats.get("signal_count", 0)),
        opportunity_count=cycle_stats.get("opportunities_found", 0),
        record_count=cycle_stats.get("records_stored", cycle_stats.get("record_count", len(records))),
        elevated_count=len(elevated),
        elevated_records=elevated_block,
        standard_records=standard_block,
        geo_count=geo_count,
        cyber_count=cyber_count,
        date=date_str,
    )


def _fallback_brief(cycle_stats: dict) -> str:
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    run_id = cycle_stats.get("run_id", "—")
    harvested = cycle_stats.get("signals_harvested", 0)
    opportunities = cycle_stats.get("opportunities_found", 0)
    stored = cycle_stats.get("records_stored", 0)
    errors = cycle_stats.get("errors", [])
    finished = cycle_stats.get("finished_at", "—")

    error_block = ""
    if errors:
        error_lines = "\n".join(f"  - {e}" for e in errors)
        error_block = f"\n\n**Harvest errors ({len(errors)}):**\n{error_lines}"

    return (
        f"## SPEC-1 DAILY BRIEF — {date_str}\n\n"
        f"*AI brief unavailable — API key not configured. Cycle stats below.*\n\n"
        f"**Run:** {run_id}  \n"
        f"**Completed:** {finished}  \n"
        f"**Signals harvested:** {harvested}  \n"
        f"**Opportunities found:** {opportunities}  \n"
        f"**Records stored:** {stored}"
        f"{error_block}"
    )


def generate_brief(records: list[dict], cycle_stats: dict) -> str:
    """Generate the daily intelligence brief via Claude.

    Returns a markdown string. On any failure returns a fallback brief.
    Never raises.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("[briefing] ANTHROPIC_API_KEY not set in environment — returning fallback brief")
        logger.warning("ANTHROPIC_API_KEY not set — returning fallback brief")
        return _fallback_brief(cycle_stats)

    prompt = _build_prompt(records, cycle_stats)

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        brief = message.content[0].text.strip()
        logger.info("Brief generated — %d words", len(brief.split()))
        return brief
    except Exception as exc:
        print(f"[briefing] API call failed: {type(exc).__name__}: {exc}")
        logger.error("Brief generation failed: %s", exc)
        return _fallback_brief(cycle_stats)
