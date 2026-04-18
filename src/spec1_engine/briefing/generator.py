"""Daily intelligence brief generator.

Calls Claude Sonnet to write a publishable brief from today's scored records.
Falls back to a raw-stats brief on any API error — never crashes the cycle.
"""

import os
try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    load_dotenv = None

if load_dotenv is not None:
    load_dotenv()

import logging
from datetime import datetime, timezone

import anthropic

from spec1_engine.briefing.templates import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE

logger = logging.getLogger(__name__)

MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 4000

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

    geo_count = sum(1 for r in records if _classify_domain(r) == "geo")
    cyber_count = sum(1 for r in records if _classify_domain(r) == "cyber")

    elevated_block = (
        "\n".join(_format_record(r) for r in elevated)
        if elevated else "(none)"
    )
    standard_block = (
        "\n".join(_format_record(r) for r in standard_top10)
        if standard_top10 else "(none)"
    )

    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Psyop assessment block
    psyop_cls = cycle_stats.get("psyop_classification", "")
    psyop_score = cycle_stats.get("psyop_score", 0)
    psyop_patterns = cycle_stats.get("psyop_patterns_fired", [])
    if psyop_cls:
        psyop_assessment = (
            f"Classification: {psyop_cls} | Score: {psyop_score} | "
            f"Patterns fired: {', '.join(psyop_patterns) if psyop_patterns else '(none)'}"
        )
    else:
        psyop_assessment = "(not run this cycle)"

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
        psyop_assessment=psyop_assessment,
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


def generate_brief(records: list[dict], cycle_stats: dict) -> tuple[str, str]:
    """Generate the daily intelligence brief via Claude.

    Returns a (brief, prompts_text) tuple where *brief* is the generated
    markdown and *prompts_text* is the full prompts payload (system + user)
    that was sent to the model.  On any failure the brief is a fallback
    string; prompts_text is still populated when available.
    Never raises.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip().lstrip('\ufeff')
    if not api_key:
        print("[briefing] ANTHROPIC_API_KEY not set in environment — returning fallback brief")
        logger.warning("ANTHROPIC_API_KEY not set — returning fallback brief")
        return _fallback_brief(cycle_stats), ""

    prompts_text = ""

    try:
        user_prompt = _build_prompt(records, cycle_stats)
        prompts_text = f"## SYSTEM PROMPT\n\n{SYSTEM_PROMPT.strip()}\n\n---\n\n## USER PROMPT\n\n{user_prompt.strip()}\n"
        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )
        brief = message.content[0].text.strip()
        logger.info("Brief generated — %d words", len(brief.split()))
        return brief, prompts_text
    except Exception as exc:
        print(f"[briefing] API call failed: {type(exc).__name__}: {exc}")
        logger.error("Brief generation failed: %s", exc)
        return _fallback_brief(cycle_stats), prompts_text
