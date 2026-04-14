"""Claude API-driven case research for investigation workspace."""

from __future__ import annotations

from spec1_engine.schemas.models import CaseFile, Signal
from spec1_engine.core import logging_utils

logger = logging_utils.get_logger(__name__)

# Will import on demand to allow optional dependency
_anthropic = None


def run_research(case: CaseFile, new_signals: list[Signal]) -> str:
    """
    Run Claude research on a case file.
    Analyzes new signals, integrates with prior findings, produces a finding update.

    Args:
        case: CaseFile to research
        new_signals: List of Signal objects matched to this case this cycle

    Returns:
        Finding string from Claude, or fallback if API unavailable
    """
    global _anthropic

    if not new_signals:
        return ""

    # Lazy import
    if _anthropic is None:
        try:
            import anthropic
            _anthropic = anthropic
        except ImportError:
            logger.warning("anthropic_not_installed")
            return "No new finding — Anthropic SDK not installed"

    try:
        client = _anthropic.Anthropic()

        # Build prompt
        system_prompt = (
            "You are an investigative research assistant working a case file. "
            "Be specific. Be skeptical. Cite signal sources. "
            "Flag low confidence. Do not speculate beyond the evidence."
        )

        signal_text = "\n".join(
            f"  - [{s.source}] {s.text[:200]}" for s in new_signals
        )

        prior_findings_text = "\n".join(
            f"  - {f[:200]}" for f in case.findings[-5:]  # Last 5 findings
        ) if case.findings else "  (none)"

        user_prompt = (
            f"CASE: {case.title}\n"
            f"QUESTION: {case.question}\n"
            f"TAGS: {', '.join(case.tags)}\n"
            f"\n"
            f"SIGNALS MATCHED THIS CYCLE ({len(new_signals)}):\n"
            f"{signal_text}\n"
            f"\n"
            f"PRIOR FINDINGS ({len(case.findings)}):\n"
            f"{prior_findings_text}\n"
            f"\n"
            f"Based on the new signals, write a finding update for this case:\n"
            f"- What new evidence emerged today\n"
            f"- How it connects to prior findings\n"
            f"- What it changes about the investigation\n"
            f"- What to look for next cycle\n"
            f"- Confidence assessment: HIGH / MEDIUM / LOW and why"
        )

        # Call Claude Sonnet
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            system=system_prompt,
            messages=[
                {
                    "role": "user",
                    "content": user_prompt,
                }
            ],
        )

        finding = response.content[0].text

        logger.info(f"research_complete: case_id={case.case_id}, signals_analyzed={len(new_signals)}, tokens_used={response.usage.input_tokens + response.usage.output_tokens}")

        return finding

    except Exception as e:
        logger.error(f"research_failed: case_id={case.case_id}, error={str(e)}")
        return f"No new finding — Claude API unavailable: {str(e)}"
