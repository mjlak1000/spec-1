# SPEC-1 Intelligence Engine — Architecture Guide

## Overview

SPEC-1 is a real-time open-source intelligence (OSINT) platform that:
- Harvests signals from RSS feeds, FARA filings, congressional records, and narrative sources
- Scores and prioritises signals through a 4-gate pipeline
- Generates and verifies investigations
- Detects psychological-operation patterns
- Produces quantitative market intelligence
- Publishes daily world briefs and actionable leads
- Records human verdicts and surfaces calibration drift (descriptive, not auto-tuning)
- Persists all data to JSONL and SQLite via dual-write
- Exposes a FastAPI HTTP API and an MCP server for Claude integration

## Repository Layout

```
spec-1/
├── src/
│   ├── spec1_engine/        # Core OSINT pipeline (harvest → score → investigate → analyze)
│   │   ├── schemas/models.py     # Signal, ParsedSignal, Opportunity, Investigation, Outcome,
│   │   │                         # IntelligenceRecord, AnalystRecord
│   │   ├── core/                 # engine, ids, logging_utils  (frozen — change with care)
│   │   ├── signal/               # harvester, parser, scorer, complexity
│   │   ├── investigation/        # generator, verifier
│   │   ├── intelligence/         # analyzer, store
│   │   ├── analysts/             # registry, credibility, discovery (analyst weighting)
│   │   ├── briefing/             # generator (Claude Sonnet) + writer + templates
│   │   │                         # rule-based fallback if API call fails
│   │   ├── congressional/        # collector, parser, scorer, analyzer, cycle
│   │   ├── quant/                # collector, parser, scorer, analyzer, cycle
│   │   ├── workspace/            # persistent investigation case files (case, tracker,
│   │   │                         # researcher, CLI)
│   │   ├── tools/                # Operational CLIs
│   │   │                         #   - historical_briefs: backfill briefs for past run_ids
│   │   │                         #   - calibration_propose: build calibration report from verdicts
│   │   │                         #   - pdf_render: out-of-process weasyprint subprocess
│   │   ├── cls_leads/            # Re-export shim → cls_leads (top-level)
│   │   ├── cls_psyop/            # Re-export shim → cls_psyop (top-level)
│   │   ├── cls_world_brief/      # Re-export shim → cls_world_brief (top-level)
│   │   ├── api/                  # Legacy in-engine FastAPI app (mount /api/v1)
│   │   ├── app/cycle.py          # `python -m spec1_engine.app.cycle` — one-shot cycle
│   │   └── main.py               # `python -m spec1_engine.main` — alt entry point
│   │
│   ├── cls_osint/                # Extended OSINT adapters
│   │   ├── schemas.py            # OSINTRecord, FaraRecord, CongressRecord, NarrativeRecord
│   │   ├── sources.py            # Source registry
│   │   ├── feed.py               # Generic feed fetcher
│   │   ├── pipeline.py           # Full OSINT processing pipeline
│   │   ├── store.py              # JSONL persistence
│   │   └── adapters/             # fara, congressional, narrative, verifier
│   │
│   ├── cls_world_brief/          # Daily world intelligence brief
│   │   └── schemas / producer / formatter / store
│   │
│   ├── cls_leads/                # Actionable intelligence leads
│   │   └── schemas / generator / formatter / store
│   │
│   ├── cls_psyop/                # Psychological-operation detection
│   │   └── schemas / patterns / scorer / pipeline / evidence / store
│   │
│   ├── cls_quant/                # Quantitative / market intelligence
│   │   └── schemas / sources / collector / indicators / scorer / pipeline / store
│   │
│   ├── cls_verdicts/             # Phase 1 feedback loop — human ground truth
│   │   ├── schemas.py            # Verdict, VerdictKind ('correct'|'incorrect'|'partial'|'unclear')
│   │   └── store.py              # Append-only JSONL; multiple verdicts per record allowed
│   │
│   ├── cls_calibration/          # Phase 2 feedback loop — drift surfacing
│   │   ├── schemas.py            # Bucket, CalibrationReport, ProposalReport, SuggestedAdjustment
│   │   ├── aggregator.py         # produce_report, score_verdict
│   │   ├── proposer.py           # propose_adjustments (descriptive only — no auto-tune)
│   │   └── formatter.py          # to_markdown
│   │
│   ├── cls_db/                   # Structured persistence layer
│   │   ├── database.py           # SQLite connection pool + session factory
│   │   ├── models.py             # Table schemas (signals, records, leads, briefs, psyop,
│   │   │                         # verdicts, calibration)
│   │   ├── repository.py         # Generic CRUD repository
│   │   ├── dual_write.py         # Atomic JSONL + SQLite write
│   │   └── migrate.py            # Schema migration runner
│   │
│   ├── spec1_api/                # FastAPI application (canonical HTTP surface)
│   │   ├── main.py               # App factory + lifespan
│   │   ├── scheduler.py          # APScheduler daily cycle
│   │   ├── dependencies.py       # DI for stores, db, engine
│   │   ├── schemas.py            # Pydantic request/response models
│   │   └── routers/
│   │       ├── health.py         # GET /health
│   │       ├── signals.py        # GET /signals
│   │       ├── intel.py          # GET /intel
│   │       ├── leads.py          # GET /leads, POST /leads
│   │       ├── brief.py          # GET /brief
│   │       ├── psyop.py          # GET /psyop
│   │       ├── fara.py           # GET /fara
│   │       ├── verdicts.py       # GET/POST /verdicts
│   │       ├── calibration.py    # GET /calibration
│   │       └── cycle.py          # POST /cycle/run
│   │
│   ├── data/                     # Bundled JSONL fixtures (e.g. psyop_signals.jsonl)
│   └── spec1_labels.py           # Canonical label/enum strings — import from here, never hard-code
│
├── tests/                        # pytest suite — 27 files, ~780 tests passing
│   ├── test_engine.py / test_pipeline.py / test_cycle.py
│   ├── test_harvester.py / test_scorer.py / test_verifier.py
│   ├── test_feed.py / test_fara.py / test_congressional.py / test_narrative.py
│   ├── test_world_brief.py / test_briefing.py / test_leads.py
│   ├── test_psyop.py / test_psyop_evidence.py
│   ├── test_quant.py            # requires numpy — skips/errors without it
│   ├── test_persistence.py / test_store.py
│   ├── test_analysts.py / test_workspace.py
│   ├── test_verdicts.py / test_calibration.py / test_calibration_proposer.py
│   ├── test_pdf_render.py / test_logging_utils.py
│   ├── test_api.py              # FastAPI endpoints
│   └── test_mcp_server.py       # MCP tool surface
│
├── briefs/                       # Generated daily briefs + per-day analyst prompts
├── mcp_server.py                 # MCP server exposing SPEC-1 tools to Claude
├── verifier.py                   # Top-level verifier shim
├── pyproject.toml
├── requirements.txt
├── .env.example
├── CASE_STUDY.md
├── PORTFOLIO_SUMMARY.md
├── CLAUDE.md
└── README.md
```

## Data Flow

```
RSS / FARA / Congress / Narrative
         │
         ▼
   cls_osint.feed ───────────────────────────────────┐
         │                                            │
         ▼                                            ▼
  spec1_engine.signal                          cls_osint.adapters
  ├── harvester  → Signal[]                    ├── fara          → FaraRecord[]
  ├── parser     → ParsedSignal[]              ├── congressional → CongressRecord[]
  └── scorer     → Opportunity[]               └── narrative     → NarrativeRecord[]
         │                                            │
         ▼                                            ▼
  spec1_engine.investigation             cls_psyop.pipeline → PsyopScore[]
  ├── generator  → Investigation[]
  └── verifier   → Outcome[]
         │
         ▼
  spec1_engine.intelligence
  ├── analyzer   → IntelligenceRecord[]
  └── store      → spec1_intelligence.jsonl
         │
         ├──────────────────┬─────────────────────┬─────────────────┐
         ▼                  ▼                     ▼                 ▼
  cls_world_brief      cls_leads            spec1_engine.briefing  cls_verdicts
  → WorldBrief[]       → Lead[]             → daily brief .md       (human input)
                                              + analyst prompts            │
                                                                           ▼
                                                                cls_calibration
                                                                → CalibrationReport
                                                                  (drift report —
                                                                   descriptive only)
         │
         ▼
  cls_db.dual_write
  ├── JSONL (append-only)
  └── SQLite (queryable)
         │
         ▼
  spec1_api (FastAPI)  ──── routers: health, signals, intel, leads, brief, psyop,
         │                          fara, verdicts, calibration, cycle
         │
  mcp_server.py (Claude MCP)
```

## Key Data Models

### spec1_engine (core)
- `Signal` — raw RSS/OSINT item
- `ParsedSignal` — cleaned + keywords/entities extracted
- `Opportunity` — passed all 4 gates (credibility, volume, velocity, novelty)
- `Investigation` — hypothesis + queries + analyst leads
- `Outcome` — verified classification (Corroborated / Escalate / Investigate / Monitor / Archive)
- `IntelligenceRecord` — final analyzed record with confidence score
- `AnalystRecord` — name, affiliation, domains, credibility_score (used by signal scorer)

### cls_osint
- `OSINTRecord`, `FaraRecord`, `CongressRecord`, `NarrativeRecord`

### cls_world_brief
- `WorldBrief` — (brief_id, date, headline, sections, sources, confidence)
- `BriefSection`

### cls_leads
- `Lead` — (lead_id, title, summary, priority, source_record_ids, generated_at)

### cls_psyop
- `PsyopPattern`, `PsyopScore`

### cls_quant
- `MarketBar`, `QuantSignal`

### cls_verdicts
- `Verdict` — human ground-truth on a record (`record_id`, `kind`, reviewer, notes, ts)
- `VerdictKind` — `correct | incorrect | partial | unclear`

### cls_calibration
- `Bucket` — verdict-kind counts + accuracy (correct=1.0, partial=0.5, incorrect=0.0; unclear excluded)
- `CalibrationReport` — overall + per-classification accuracy + reliability buckets across
  confidence, source_weight, analyst_weight
- `ProposalReport` / `SuggestedAdjustment` — descriptive proposals; humans apply changes

## 4-Gate Scoring System

Every signal must pass ALL four gates to become an Opportunity:

| Gate | Criterion | Default Threshold |
|------|-----------|-------------------|
| credibility | Known source / analyst weight ≥ 0.5 | 0.5 |
| volume | Word count ≥ 50 | 50 words |
| velocity | Signal recency ≤ 48 hours | 48h |
| novelty | Not duplicate (hash-based dedup) | — |

Calibration drift across these gates is surfaced by `cls_calibration` — never auto-applied.

## MCP Tools Exposed (mcp_server.py)

`run_cycle`, `get_signals`, `get_intel`, `get_leads`, `get_brief`, `get_psyop`, `get_fara`,
`analyse_psyop`, `get_stats`

## Environment Variables

```
SPEC1_STORE_PATH=spec1_intelligence.jsonl
SPEC1_DB_PATH=spec1.db
SPEC1_ENVIRONMENT=production
SPEC1_LOG_LEVEL=INFO
ANTHROPIC_API_KEY=sk-ant-...
SPEC1_API_HOST=0.0.0.0
SPEC1_API_PORT=8000
```

## Running the System

```bash
# Full intelligence cycle (one-shot)
python -m spec1_engine.app.cycle

# API server (canonical)
python -m spec1_api.main

# MCP server (for Claude integration)
python mcp_server.py

# Backfill briefs for run_ids that don't have one
python -m spec1_engine.tools.historical_briefs

# Build a calibration proposal report from intel + verdicts
PYTHONPATH=src python -m spec1_engine.tools.calibration_propose \
    --intel spec1_intelligence.jsonl \
    --verdicts verdicts.jsonl \
    --out-dir generated/
```

## Testing

```bash
pip install -e ".[dev]"
pytest tests/ -v --tb=short
```

All test functions must be fully implemented — no `pass` stubs, no `pytest.skip`.
`test_quant.py` requires `numpy`; install it or `--ignore` the file in environments without it.

## Implementation Rules

1. No stubs — every function body must be implemented.
2. Use `dataclasses` for internal models, `pydantic` for API schemas.
3. All stores write append-only JSONL; `cls_db` additionally writes SQLite.
4. `cls_db.dual_write` wraps every store write so JSONL and SQLite stay in sync.
5. API routers read from JSONL stores (via repository) — not direct DB queries.
6. `mcp_server.py` exposes: `run_cycle`, `get_signals`, `get_intel`, `get_leads`, `get_brief`,
   `get_psyop`, `get_fara`, `analyse_psyop`, `get_stats`.
7. Tests use `tmp_path` fixtures and mock external network calls.
8. `pyproject.toml` lists all packages under `[tool.setuptools.packages.find]`.
9. Import canonical strings from `spec1_labels` — never hard-code label values.
10. The briefing module calls Claude Sonnet but always falls back to a rule-based brief
    on API error — the cycle never crashes on LLM failure.
11. Calibration is **descriptive**: it surfaces drift, it does not change thresholds. Tuning is
    a human decision. This preserves the "deterministic, legible" design philosophy.
12. Verdicts are append-only; multiple verdicts per record are allowed and aggregators decide
    how to fold them.
13. PDF rendering runs as a subprocess (`spec1_engine.tools.pdf_render`) so the API/engine
    processes never import weasyprint or its native deps.
