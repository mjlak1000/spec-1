# SPEC-1 Intelligence Engine — Architecture Guide

## Overview

SPEC-1 is a real-time open-source intelligence (OSINT) platform that:
- Harvests signals from RSS feeds, FARA filings, congressional records, and narrative sources
- Scores and prioritises signals through a 4-gate pipeline
- Generates and verifies investigations
- Detects psychological operations (psyop) patterns
- Produces quantitative market intelligence
- Publishes world briefs and actionable leads
- Persists all data to JSONL and SQLite via dual-write
- Exposes a FastAPI HTTP API and an MCP server for Claude integration

## Repository Layout

```
spec-1/
├── src/
│   ├── spec1_engine/        # Core OSINT pipeline (harvest → score → investigate → store)
│   │   ├── schemas/models.py
│   │   ├── core/
│   │   │   ├── engine.py
│   │   │   ├── ids.py
│   │   │   └── logging_utils.py
│   │   ├── signal/          # harvester, parser, scorer
│   │   ├── investigation/   # generator, verifier
│   │   ├── intelligence/    # analyzer, store
│   │   ├── analysts/        # credibility weighting, source discovery, registry
│   │   ├── briefing/        # generator, templates, writer
│   │   ├── quant/           # analyzer, collector, cycle, parser, scorer
│   │   ├── workspace/       # case tracking, researcher, CLI (__main__.py)
│   │   ├── api/             # internal API app, routes, scheduler
│   │   ├── app/cycle.py
│   │   └── main.py
│   │
│   ├── cls_osint/           # Extended OSINT adapters
│   │   ├── schemas.py       # OSINTRecord, FaraRecord, CongressRecord, NarrativeRecord
│   │   ├── sources.py       # Source registry (FARA, congress, narrative feeds)
│   │   ├── feed.py          # Generic feed fetcher used by adapters
│   │   ├── pipeline.py      # Full OSINT processing pipeline
│   │   ├── store.py         # JSONL persistence for OSINT records
│   │   └── adapters/
│   │       ├── fara.py      # Foreign Agents Registration Act adapter
│   │       ├── congressional.py  # Congressional record adapter
│   │       ├── narrative.py      # Narrative / influence-op adapter
│   │       └── verifier.py       # Cross-source verification
│   │
│   ├── cls_world_brief/     # Daily world intelligence brief
│   │   ├── schemas.py       # WorldBrief dataclass
│   │   ├── producer.py      # Assembles briefs from intelligence records
│   │   ├── formatter.py     # Markdown and plain-text rendering
│   │   └── store.py         # Persists briefs as JSONL + .md files
│   │
│   ├── cls_leads/           # Actionable intelligence leads
│   │   ├── schemas.py       # Lead dataclass
│   │   ├── generator.py     # Derives leads from intelligence records
│   │   ├── formatter.py     # Formats leads for human consumption
│   │   └── store.py         # JSONL persistence
│   │
│   ├── cls_psyop/           # Psychological-operation detection
│   │   ├── schemas.py       # PsyopPattern, PsyopScore
│   │   ├── patterns.py      # Known psyop signatures (amplification, framing, etc.)
│   │   ├── scorer.py        # Scores text for psyop likelihood
│   │   ├── pipeline.py      # End-to-end psyop pipeline
│   │   └── store.py         # JSONL persistence
│   │
│   ├── cls_quant/           # Quantitative / market intelligence
│   │   ├── schemas.py       # QuantSignal, MarketBar
│   │   ├── sources.py       # Ticker watchlists (defence, cyber, energy, macro)
│   │   ├── collector.py     # Fetches OHLCV data via yfinance
│   │   ├── indicators.py    # RSI, MACD, Bollinger Bands, ATR
│   │   ├── scorer.py        # 4-gate signal scorer for quant data
│   │   ├── pipeline.py      # Full quant pipeline
│   │   └── store.py         # JSONL persistence
│   │
│   ├── cls_db/              # Structured persistence layer
│   │   ├── database.py      # SQLite connection pool + session factory
│   │   ├── models.py        # Table schemas (signals, records, leads, briefs, psyop)
│   │   ├── repository.py    # Generic CRUD repository
│   │   ├── dual_write.py    # Write to JSONL + SQLite atomically
│   │   └── migrate.py       # Schema migration runner
│   │
│   ├── spec1_api/           # FastAPI application
│   │   ├── main.py          # App factory + lifespan
│   │   ├── scheduler.py     # APScheduler daily cycle
│   │   ├── dependencies.py  # Dependency injection (store, db, engine)
│   │   ├── schemas.py       # Pydantic request/response models
│   │   └── routers/
│   │       ├── health.py    # GET /health
│   │       ├── signals.py   # GET /signals
│   │       ├── intel.py     # GET /intel
│   │       ├── leads.py     # GET /leads, POST /leads
│   │       ├── brief.py     # GET /brief
│   │       ├── psyop.py     # GET /psyop
│   │       ├── fara.py      # GET /fara
│   │       └── cycle.py     # POST /cycle/run
│   │
│   └── spec1_labels.py      # Shared label/category constants
│
├── tests/                   # pytest test suite
│   ├── test_engine.py       # Core engine pipeline
│   ├── test_feed.py         # Feed fetching
│   ├── test_pipeline.py     # OSINT pipeline
│   ├── test_fara.py         # FARA adapter
│   ├── test_congressional.py
│   ├── test_narrative.py
│   ├── test_verifier.py     # Cross-source verifier
│   ├── test_harvester.py    # Signal harvester
│   ├── test_analysts.py     # Analyst credibility + discovery
│   ├── test_briefing.py     # Briefing generation
│   ├── test_cycle.py        # Full cycle integration
│   ├── test_world_brief.py
│   ├── test_leads.py
│   ├── test_psyop.py
│   ├── test_quant.py
│   ├── test_workspace.py    # Case management workspace
│   ├── test_store.py        # Store persistence
│   ├── test_logging_utils.py
│   ├── test_persistence.py  # cls_db dual-write
│   ├── test_api.py          # FastAPI endpoints
│   └── test_mcp_server.py   # MCP server tools
│
├── briefs/                  # Generated brief output files (.md)
├── mcp_server.py            # MCP server exposing SPEC-1 tools to Claude
├── pyproject.toml
├── requirements.txt
├── .env.example
├── CLAUDE.md
├── PORTFOLIO_SUMMARY.md     # High-level project overview for stakeholders
└── README.md
```

## Data Flow

```
RSS/FARA/Congress/Narrative
         │
         ▼
   cls_osint.feed  ──────────────────────────────────┐
         │                                            │
         ▼                                            ▼
  spec1_engine.signal                         cls_osint.adapters
  ├── harvester  → Signal[]                   ├── fara       → FaraRecord[]
  ├── parser     → ParsedSignal[]             ├── congressional → CongressRecord[]
  └── scorer     → Opportunity[]             └── narrative   → NarrativeRecord[]
         │                                            │
         ▼                                            ▼
  spec1_engine.investigation          cls_psyop.pipeline → PsyopScore[]
  ├── generator  → Investigation[]
  └── verifier   → Outcome[]
         │
         ▼
  spec1_engine.intelligence
  ├── analyzer   → IntelligenceRecord[]
  └── store      → spec1_intelligence.jsonl
         │
         ├──────────────────────────────────────┐
         ▼                                      ▼
  cls_world_brief.producer              cls_leads.generator
  → WorldBrief[]                        → Lead[]
         │                                      │
         ▼                                      ▼
  cls_world_brief.store             cls_leads.store
         │                                      │
         └──────────────┬───────────────────────┘
                        ▼
                 cls_db.dual_write
                 ├── JSONL (append-only)
                 └── SQLite (queryable)
                        │
                        ▼
                  spec1_api (FastAPI)
                  └── mcp_server.py (Claude MCP)
```

## Key Data Models

### spec1_engine (core)
- `Signal` — raw RSS/OSINT item (signal_id, source, text, url, author, published_at)
- `ParsedSignal` — cleaned + keywords extracted
- `Opportunity` — passed all 4 gates (credibility, volume, velocity, novelty)
- `Investigation` — hypothesis + queries + analyst leads
- `Outcome` — verified classification (Corroborated/Escalate/Investigate/Monitor/Archive)
- `IntelligenceRecord` — final analyzed record with confidence score

### cls_osint
- `OSINTRecord` — generic OSINT record (record_id, source_type, content, url, collected_at)
- `FaraRecord` — FARA filing (registrant, foreign_principal, activities, filed_at)
- `CongressRecord` — Congressional item (bill_id, title, sponsor, status, date)
- `NarrativeRecord` — Detected narrative (theme, amplifiers, reach_score)

### cls_world_brief
- `WorldBrief` — (brief_id, date, headline, sections, sources, confidence)

### cls_leads
- `Lead` — (lead_id, title, summary, priority, source_record_ids, generated_at)

### cls_psyop
- `PsyopPattern` — (pattern_id, name, description, indicators)
- `PsyopScore` — (score_id, text_hash, patterns_matched, score, classification)

### cls_quant
- `MarketBar` — (ticker, date, open, high, low, close, volume)
- `QuantSignal` — (signal_id, ticker, pattern, score, triggered_at)

## 4-Gate Scoring System

Every signal must pass ALL four gates to become an Opportunity:

| Gate | Criterion | Default Threshold |
|------|-----------|-------------------|
| credibility | Known source / analyst weight ≥ 0.5 | 0.5 |
| volume | Word count ≥ 50 | 50 words |
| velocity | Signal recency ≤ 48 hours | 48h |
| novelty | Not duplicate (hash-based dedup) | — |

## Environment Variables

```
SPEC1_STORE_PATH=spec1_intelligence.jsonl
SPEC1_DB_PATH=spec1.db
SPEC1_ENVIRONMENT=production
SPEC1_LOG_LEVEL=INFO
ANTHROPIC_API_KEY=sk-ant-...
SPEC1_API_HOST=0.0.0.0
SPEC1_API_PORT=8000
SPEC1_CRON_HOUR=6
SPEC1_CRON_MINUTE=0
SPEC1_TIMEZONE=America/Los_Angeles
SPEC1_FEED_TIMEOUT=15
SPEC1_QUANT_ENABLED=false
```

## Running the System

```bash
# Full intelligence cycle (one-shot)
python -m spec1_engine.app.cycle

# API server
python -m spec1_api.main

# MCP server (for Claude integration)
python mcp_server.py

# Workspace CLI (case management)
python -m spec1_engine.workspace
```

## Testing

```bash
pip install -e ".[dev]"
pytest tests/ -v --tb=short
```

All test functions must be fully implemented — no `pass` stubs, no `pytest.skip`.

## Implementation Rules

1. No stubs — every function body must be implemented
2. Use `dataclasses` for internal models, `pydantic` for API schemas
3. All stores write append-only JSONL; `cls_db` additionally writes SQLite
4. `cls_db.dual_write` wraps every store write so JSONL and SQLite stay in sync
5. API routers read from JSONL stores (via repository) — not direct DB queries
6. `mcp_server.py` exposes tools: `run_cycle`, `get_signals`, `get_intel`, `get_leads`, `get_brief`, `get_psyop`, `get_fara`
7. Tests use `tmp_path` fixtures and mock external network calls
8. `pyproject.toml` lists all packages under `[tool.setuptools.packages.find]`
