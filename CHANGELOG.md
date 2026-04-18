# SPEC-1 Intelligence Engine — Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## Versioning Rules

| Change type                                            | Version bump |
|--------------------------------------------------------|--------------|
| Breaking schema, contract, or prompt change in `/core` | MAJOR        |
| New module, scorer, or adapter                         | MINOR        |
| Bug fix, CI, or infra change                           | PATCH        |

Every PR that touches `/core` **must** bump the version in
`src/spec1_engine/core/version.py` and add an entry here.

---

## [0.2.0] — 2026-04-18 — Frozen Core

### Summary

Directive #1: Establish a frozen core. All canonical schemas, scoring contracts,
prompt definitions, and version metadata are now consolidated under
`src/spec1_engine/core/`. This is the v0.2.0 freeze point.

### Added

- **`core/schemas.py`** — Canonical dataclasses for the full pipeline:
  `Signal`, `ParsedSignal`, `Opportunity`, `Investigation`, `Outcome`,
  `IntelligenceRecord`, `AnalystRecord`, `CaseFile`.
  Each class carries full docstrings and a `to_dict()` serialisation method.

- **`core/contracts.py`** — Authoritative scoring constants and gate interface
  contracts: credibility thresholds, volume tiers, velocity threshold, novelty
  terms, composite score weights, priority assignment thresholds, and valid
  outcome classification labels.

- **`core/prompts/system_prompt.md`** — Editorial voice and rules extracted
  from `briefing/templates.py (SYSTEM_PROMPT)`.

- **`core/prompts/investigation_prompts.md`** — Verifier system prompt and
  user prompt template extracted from `investigation/verifier.py`.

- **`core/prompts/editorial_voice.md`** — Daily brief structure and editorial
  formatting rules extracted from `briefing/templates.py (USER_PROMPT_TEMPLATE)`.

- **`core/version.py`** — Semantic version string (`"0.2.0"`), structured
  `VERSION` tuple, `RELEASE_NAME`, and `bump_version()` utility.

- **`core/__init__.py`** — Re-exports all canonical public types and version
  metadata; includes `__all__` list and immutability warning in docstring.

- **`CHANGELOG.md`** — This file. Documents v0.2.0 as the freeze point.

### Not Changed

- `src/spec1_engine/schemas/models.py` is **not** deleted (gradual migration).
  Existing imports across the codebase are unchanged.
- The 7-stage pipeline logic, gate thresholds, scoring weights, JSONL
  persistence, FastAPI endpoints, and the full test suite (740 tests) are
  all preserved unchanged.

### Immutability Contract

From this release forward:

- **No agent or automated pipeline may modify files under `core/`.**
- PRs that touch `core/` require human review, a version bump here, and a
  CHANGELOG entry.
- Branch conventions: `agent/*` for agent work, `dev` for integration,
  `main` for human-curated stable releases.

---

## [0.1.0] — Initial release

Initial pipeline: RSS harvesting → 4-gate scoring → Claude investigation →
JSONL storage → daily brief generation. FastAPI endpoints and MCP server.
