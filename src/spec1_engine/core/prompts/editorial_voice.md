<!--
  SPEC-1 Intelligence Engine — Editorial Voice & Briefing Format
  ==============================================================
  Source: src/spec1_engine/briefing/templates.py (USER_PROMPT_TEMPLATE)
  Core version: 0.2.0 (Frozen Core)

  IMMUTABILITY RULE: This file lives in core/prompts/ and must not be
  edited by agents or automated pipelines. Changes require a human
  review, a version bump in core/version.py, and a CHANGELOG.md entry.
-->

## Editorial Voice Rules

The following rules are enforced by the system prompt in `system_prompt.md`
and must be reflected in every generated brief.

1. **Precision** — Every claim is specific. Named officials, named agencies,
   specific dates, exact numbers. No weasel words (`recently`, `several`).

2. **Attribution** — Distinguish confirmed from assessed from unverified.
   Use exact language:
   - `"confirmed by two independent sources"`
   - `"assessed at 0.72 confidence"`
   - `"single-source, unconfirmed"`
   - `"pattern consistent with but not conclusive of"`
   - `"Insufficient signal depth to assess"` is a *legitimate finding*.

3. **Active voice only** — Actors act. Name them. Passive voice is banned.

4. **Brevity** — Cut every sentence that adds no new information.
   If a paragraph can be one sentence, make it one sentence.

5. **Domain voice** — Geopolitics: Pentagon voice. Cyber: NSA voice.
   Congressional: K Street voice. Different voice, same precision.

6. **Honesty over padding** — If signals are thin, say so plainly.

---

## Daily Brief Structure

The `USER_PROMPT_TEMPLATE` in `briefing/templates.py` instructs Claude to
produce a brief using the exact section structure below.

```markdown
## SPEC-1 DAILY BRIEF — {date}

### Executive Summary
[3 sentences. What happened today. What it means. What is uncertain.]

### Elevated Signals
[One paragraph per elevated signal. Source. What was observed.
Confidence score. What to watch next.
If zero elevated signals, say so plainly.]

### Domain Briefings

**Geopolitics**
[Narrative summary. Patterns, not lists. 2-4 paragraphs.]

**Cyber / Info Ops**
[Narrative summary. Attribution confidence where relevant. 2-4 paragraphs.]

### Story Leads
[3-5 specific, actionable leads. Each lead must follow this exact format:

**LEAD: [Headline-style title]**
Signal: [Which scored signal triggered this — include source name, pattern summary, and confidence score]
The question: [The specific thing a reporter needs to answer]
Who to call: [Source type — congressional staffer, DoD spokesperson,
              CISA, company IR, think tank analyst, etc.]
Documents to request: [FOIA targets, SEC filings, congressional records,
                       earnings calls, company disclosures — what is findable]
Window: [How long this lead stays fresh — 24hrs / 3 days / 1 week]
Confidence: [HIGH / MEDIUM / LOW — based on underlying signal score]

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

Do not invent leads. Every lead traces to a scored signal.
Low confidence leads are flagged, not dropped.
Every lead must include the CLAUDE PROMPT blockquote — it is not optional.]

### Watch List — Tomorrow
[3-5 specific things to monitor. Tied to today's signals. One line each.]

### Signal Notes
[Brief methodological note: source gaps, gate failure patterns,
anything that affected today's collection quality. 2-4 sentences.]
```

---

## User Prompt Input Variables

The template is filled with the following values by `briefing/generator.py`:

| Variable            | Source                                      |
|---------------------|---------------------------------------------|
| `{run_id}`          | `cycle_stats["run_id"]`                     |
| `{timestamp}`       | `cycle_stats["finished_at"]`                |
| `{signal_count}`    | `cycle_stats["signals_harvested"]`          |
| `{opportunity_count}` | `cycle_stats["opportunities_found"]`      |
| `{record_count}`    | `cycle_stats["records_stored"]`             |
| `{elevated_count}`  | Count of ELEVATED records                   |
| `{elevated_records}` | Formatted ELEVATED record blocks           |
| `{standard_records}` | Top-10 STANDARD records by confidence      |
| `{geo_count}`       | Count of geopolitics signals                |
| `{cyber_count}`     | Count of cyber/info-ops signals             |
| `{date}`            | `YYYY-MM-DD` in UTC                         |
