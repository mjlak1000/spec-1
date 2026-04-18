<!--
  SPEC-1 Intelligence Engine — Investigation Prompts
  ===================================================
  Source: src/spec1_engine/investigation/verifier.py (_SYSTEM_PROMPT, _build_user_prompt)
  Core version: 0.2.0 (Frozen Core)

  IMMUTABILITY RULE: This file lives in core/prompts/ and must not be
  edited by agents or automated pipelines. Changes require a human
  review, a version bump in core/version.py, and a CHANGELOG.md entry.
-->

## Verifier System Prompt

Used by `investigation/verifier.py` as the `system` message sent to Claude
when verifying an investigation hypothesis.

```
You are an intelligence analyst verifying a hypothesis.
Respond with JSON only — no prose, no markdown fences.
Schema: {"verified": bool, "confidence": float, "reasoning": str,
         "classification": "CORROBORATED"|"ESCALATE"|"INVESTIGATE"|"MONITOR"|"CONFLICTED"|"ARCHIVE"}
```

### Valid Classification Values

| Classification | Meaning |
|----------------|---------|
| `CORROBORATED` | Hypothesis supported by multiple independent sources |
| `ESCALATE`     | High-confidence finding requiring immediate attention |
| `INVESTIGATE`  | Credible but unconfirmed — warrants further research |
| `MONITOR`      | Low-confidence or developing situation — watch only |
| `CONFLICTED`   | Evidence exists on both sides — cannot assess |
| `ARCHIVE`      | Insufficient signal or irrelevant — close the case |

---

## Verifier User Prompt Template

The `_build_user_prompt` function constructs a message with the following
structure and sends it as the `user` message alongside the system prompt above.

```
Hypothesis: {investigation.hypothesis}

Queries raised:
  - {query_1}
  - {query_2}
  ...

Sources to check:
  - {source_url_1}
  - {source_url_2}
  ...

Analyst leads:
  - {analyst_name_1}
  - {analyst_name_2}
  ...

Based on the hypothesis, queries, and sources, assess credibility.
Return JSON only.
```

### Notes

- The `analyst_leads` block is omitted when the list is empty.
- Confidence is a float in `[0.0, 1.0]`, rounded to 4 decimal places.
- The model is `claude-haiku-4-5-20251001` with `max_tokens=512`.
- On any API or parse error the verifier returns a fallback `Outcome` with
  `classification="INVESTIGATE"` and `confidence=0.0`.
