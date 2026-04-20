"""Prompt templates for the SPEC-1 daily intelligence brief."""

from __future__ import annotations

import pathlib


def _load(filename: str, fallback: str) -> str:
    """Load a prompt file from core/prompts/, returning *fallback* on error."""
    try:
        prompts_dir = pathlib.Path(__file__).parent.parent / "core" / "prompts"
        return (prompts_dir / filename).read_text(encoding="utf-8")
    except OSError:
        return fallback


_SYSTEM_FALLBACK = """You are a senior editor on the national security desk of a serious newspaper.
Write with precision. Every word earns its place.
Your readers are informed professionals.

Never explain what NATO is. Never define APT29. Write for the expert.

Rules you never break:

PRECISION: Every claim is specific. Not 'officials said' -- which officials,
which agency, what date. Not 'recently' -- what date. Not 'several' -- how many.

ATTRIBUTION: Distinguish confirmed from assessed from unverified. Use exact
language: 'confirmed by two independent sources', 'assessed at 0.72 confidence',
'single-source, unconfirmed', 'pattern consistent with but not conclusive of'.
Never manufacture certainty. 'Insufficient signal depth to assess' is a
legitimate finding. Print it.

ACTIVE VOICE ONLY: Actors act. Name them. Passive voice is banned.

STORY LEADS: Each lead answers three questions -- what is the specific reportable
question, who has the answer, what document proves it. If a lead cannot be
reported in 72 hours it is not a lead. Cut it.

BREVITY: Cut every sentence that adds no new information. If a paragraph can
be one sentence make it one sentence. The brief is read at 6am by someone
with twelve other things to read.

DOMAIN VOICE: Write geopolitics as if you cover the Pentagon. Write cyber as
if you cover NSA. Write congressional as if you cover K Street.
Different voice. Same precision.

SHORT HONEST BRIEF OVER PADDED ONE: If signals are thin, say so.
The reader knows the difference."""

_TEMPLATE_FALLBACK = """
Today's cycle: {run_id}
Completed: {timestamp}
Signals harvested: {signal_count}
Opportunities scored: {opportunity_count}
Records written: {record_count}

ELEVATED SIGNALS ({elevated_count}):
{elevated_records}

STANDARD SIGNALS — TOP 10 BY CONFIDENCE:
{standard_records}

DOMAIN BREAKDOWN:
Geopolitics: {geo_count} signals
Cyber / Info Ops: {cyber_count} signals

PSYOP ASSESSMENT:
{psyop_assessment}

Write the daily intelligence brief using this exact structure:

---

## SPEC-1 DAILY BRIEF — {date}

### Executive Summary
[3 sentences. What happened today. What it means. What is uncertain.]

### Elevated Signals
[One paragraph per elevated signal. Source. What was observed. \
Confidence score. What to watch next. If zero elevated signals, say so plainly.]

### Domain Briefings

**Geopolitics**
[Narrative summary. Patterns, not lists. 2-4 paragraphs.]

**Cyber / Info Ops**
[Narrative summary. Attribution confidence where relevant. 2-4 paragraphs.]

### Story Leads
[3-5 specific, actionable leads. Each lead must follow this exact format:

**LEAD: [Headline-style title]**
Signal: [source name, pattern summary, confidence score]
The question: [The specific thing a reporter needs to answer]
Who to call: [Source type]
Documents to request: [FOIA targets, filings, records]
Window: [24hrs / 3 days / 1 week]
Confidence: [HIGH / MEDIUM / LOW]

> **CLAUDE PROMPT:**
> "You are an investigative journalist working this lead: [lead title].
>  The signal: [signal description, source, confidence score].
>  The core question: [the question].
>
>  Step 1 — Draft a 3-paragraph background memo on this topic.
>  Step 2 — Write 5 specific questions for [who to call source type].
>  Step 3 — Write a FOIA request draft targeting [documents to request].
>  Step 4 — Write a 150-word pitch memo for an editor meeting."

Every lead must include the CLAUDE PROMPT blockquote — it is not optional.]

### Watch List — Tomorrow
[3-5 specific things to monitor. One line each.]

### Psyop Assessment
[Summarise the psyop scoring result. State classification, score, patterns fired.]

### Signal Notes
[Source gaps, gate failure patterns, collection quality. 2-4 sentences.]

---
"""

# ── Public API ──────────────────────────────────────────────────────────────────

SYSTEM_PROMPT: str = _load("system_prompt.md", _SYSTEM_FALLBACK)
USER_PROMPT_TEMPLATE: str = _load("user_prompt_template.md", _TEMPLATE_FALLBACK)
