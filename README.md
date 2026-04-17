# SPEC-1 Intelligence Engine

SPEC-1 is a real-time open-source intelligence (OSINT) platform that harvests signals from
RSS feeds, FARA filings, congressional records, and narrative sources; scores them through a
4-gate pipeline; detects psychological operations; generates actionable leads and world briefs;
and persists everything to JSONL and SQLite.

## Architecture

```
RSS/FARA/Congress/Narrative
        │
        ▼
  cls_osint.feed ──────── cls_osint.adapters (fara, congressional, narrative)
        │
        ▼
  spec1_engine  (harvest → parse → score → investigate → verify → analyze)
        │
        ├── cls_psyop     (psychological operation detection)
        ├── cls_quant     (market intelligence)
        ├── cls_leads     (actionable leads)
        ├── cls_world_brief (daily intelligence brief)
        └── cls_db        (dual-write: JSONL + SQLite)
                │
                ▼
          spec1_api  (FastAPI HTTP server)
          mcp_server (MCP tools for Claude)
```

## Quick Start

```bash
pip install -e ".[dev]"

# One-shot intelligence cycle
python -m spec1_engine.app.cycle

# API server (http://localhost:8000)
python -m spec1_api.main

# MCP server (Claude integration)
python mcp_server.py
```

## Running Tests

```bash
pytest tests/ -v --tb=short
```

## Environment

Copy `.env.example` to `.env` and configure:

```bash
cp .env.example .env
# Edit .env — at minimum set ANTHROPIC_API_KEY
```

## Key Sources

**RSS Feeds**
- War on the Rocks, Cipher Brief, Just Security, RAND, Atlantic Council, Defense One

**OSINT Adapters**
- FARA (Foreign Agents Registration Act) filings
- Congressional records (bills, hearings)
- Narrative / influence-operation tracking

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | /health | Health check |
| GET | /signals | Latest harvested signals |
| GET | /intel | Intelligence records |
| GET | /leads | Actionable leads |
| GET | /brief | Latest world brief |
| GET | /psyop | PsyOp detections |
| GET | /fara | FARA filings |
| POST | /cycle/run | Trigger a full cycle |
