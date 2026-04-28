# SPEC-1 Investigation Prompts

Investigation prompts are embedded in each Story Lead block of the daily brief.
They are blockquoted sections beginning with `> **CLAUDE PROMPT:**`.

## Format

Each lead in the brief must include one CLAUDE PROMPT blockquote. The format is:

```
> **CLAUDE PROMPT:**
> "You are an investigative journalist working this lead: [lead title].
>  The signal: [signal description, source, confidence score].
>  The core question: [the question].
>
>  Step 1 — Draft a 3-paragraph background memo on this topic using
>  only publicly available information. Cite specific sources.
>
>  Step 2 — Write 5 specific questions for [who to call source type].
>  Each question should be answerable with a yes/no or a specific fact.
>  Avoid open-ended questions that give a spokesperson room to deflect.
>
>  Step 3 — Write a FOIA request draft targeting [documents to request].
>  Use formal FOIA language. Specify the agency, the date range,
>  and the specific records requested.
>
>  Step 4 — Write a 150-word pitch memo for an editor meeting.
>  State the story, the stakes, what you have, what you still need."
```

## Rules

- Every lead **must** include a CLAUDE PROMPT blockquote — it is not optional
- Do not invent leads; every lead must trace to a scored signal
- Low-confidence leads are flagged, not dropped
- The prompt must name the specific source type, document type, and agency

## Extraction

The brief writer (`briefing/writer.py`) extracts these blockquotes automatically
using the `_extract_prompts()` function and stores them in `spec1_prompts_*.md`.
