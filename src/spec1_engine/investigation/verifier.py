"""Investigation Verifier.

Makes a real Claude API call to assess the investigation hypothesis and
produce an Outcome record. Falls back gracefully on any API or parse error.
"""

from __future__ import annotations

import json
import logging
import os
import uuid

import anthropic

from spec1_engine.schemas.models import Investigation, Outcome

logger = logging.getLogger(__name__)

MODEL = "claude-haiku-4-5-20251001"
VALID_CLASSIFICATIONS = {
    "Corroborated", "Escalate", "Investigate", "Monitor", "Conflicted", "Archive"
}

_SYSTEM_PROMPT = (
    "You are an intelligence analyst verifying a hypothesis. "
    "Respond with JSON only — no prose, no markdown fences. "
    'Schema: {"verified": bool, "confidence": float, "reasoning": str, '
    '"classification": "Corroborated"|"Escalate"|"Investigate"|"Monitor"|"Conflicted"|"Archive"}'
)


def _build_user_prompt(investigation: Investigation) -> str:
    lines = [
        f"Hypothesis: {investigation.hypothesis}",
        "",
        "Queries raised:",
    ]
    for q in investigation.queries:
        lines.append(f"  - {q}")
    lines.append("")
    lines.append("Sources to check:")
    for s in investigation.sources_to_check:
        lines.append(f"  - {s}")
    if investigation.analyst_leads:
        lines.append("")
        lines.append("Analyst leads:")
        for a in investigation.analyst_leads:
            lines.append(f"  - {a}")
    lines.append("")
    lines.append(
        "Based on the hypothesis, queries, and sources, assess credibility. "
        "Return JSON only."
    )
    return "\n".join(lines)


def _fallback_outcome() -> Outcome:
    return Outcome(
        outcome_id=f"out-{uuid.uuid4().hex[:12]}",
        classification="Investigate",
        confidence=0.0,
        evidence=["Fallback: API error or parse failure — manual review required."],
    )


def verify_investigation(investigation: Investigation) -> Outcome:
    """Call Claude to verify an investigation hypothesis. Never raises."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        logger.warning("ANTHROPIC_API_KEY not set — using fallback outcome")
        return _fallback_outcome()

    try:
        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model=MODEL,
            max_tokens=512,
            system=_SYSTEM_PROMPT,
            messages=[
                {"role": "user", "content": _build_user_prompt(investigation)}
            ],
        )
        raw = message.content[0].text.strip()
        # Claude sometimes wraps the response in markdown fences despite the
        # system prompt; strip them before parsing.
        if raw.startswith("```"):
            parts = raw.split("```")
            # parts[0] is empty, parts[1] is "json\n{...}", parts[2] is ""
            inner = parts[1] if len(parts) >= 2 else raw
            if "\n" in inner:
                tag, body = inner.split("\n", 1)
                raw = body.strip() if tag.strip().isalpha() else inner.strip()
            else:
                raw = inner.strip()
    except Exception as exc:
        logger.error("Claude API call failed: %s", exc)
        return _fallback_outcome()

    try:
        data = json.loads(raw)
        classification = data.get("classification", "Investigate")
        if classification not in VALID_CLASSIFICATIONS:
            classification = "Investigate"
        confidence = float(data.get("confidence", 0.0))
        confidence = round(min(max(confidence, 0.0), 1.0), 4)
        verified = bool(data.get("verified", False))
        reasoning = str(data.get("reasoning", ""))
        evidence = [
            f"Claude assessment: {reasoning}",
            f"Verified: {verified}",
            f"Confidence: {confidence}",
            f"Hypothesis: {investigation.hypothesis}",
        ]
        return Outcome(
            outcome_id=f"out-{uuid.uuid4().hex[:12]}",
            classification=classification,
            confidence=confidence,
            evidence=evidence,
        )
    except Exception as exc:
        logger.error("Failed to parse Claude response %r: %s", raw, exc)
        return _fallback_outcome()
