## Summary

<!-- 1-3 bullet points describing what this PR does -->
-

## Version Bump

<!-- Required. Select one and justify. -->
- [ ] PATCH — bug fix, CI, infra, docs
- [ ] MINOR — new module, scorer, adapter, or prompt surface
- [ ] MAJOR — breaking change to `/core` contracts or schemas

**Justification:**

## Core Modified?

- [ ] No — `/core` was not touched
- [ ] Yes — see justification below and confirm version bump is MAJOR

**If yes, what changed and why:**

## Test Status

- [ ] `pytest tests/ -q` passes locally
- [ ] `flake8 . --select=E9,F63,F7,F82` is clean
- [ ] New behaviour is covered by tests

## Checklist

- [ ] PR touches only one concern (no mixed refactor + feature)
- [ ] No inline prompt strings added outside `core/prompts/`
- [ ] Generated artifacts (briefs, logs) are not committed to this branch
- [ ] Agent write-surfaces respected (no edits to `/core`, version metadata, or top-level prompts without approval)
