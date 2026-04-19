# SPEC-1 Intelligence Engine

SPEC-1 is a real-time open-source intelligence (OSINT) platform that harvests signals from
RSS feeds, FARA filings, congressional records, and narrative sources; scores them through a
4-gate pipeline; detects psychological operations; generates actionable leads and world briefs;
and persists everything to JSONL and SQLite.

For a high-level overview of the project's purpose and design decisions, see
[PORTFOLIO_SUMMARY.md](PORTFOLIO_SUMMARY.md).

## Architecture

```
RSS/FARA/Congress/Narrative
        │
        ▼
  cls_osint.feed ──────── cls_osint.adapters (fara, congressional, narrative)
        │
        ▼
  spec1_engine  (harvest → parse → score → investigate → verify → analyze)
  ├── analysts      (credibility weighting, source discovery)
  ├── briefing      (daily brief generation)
  ├── quant         (market signal analysis)
  └── workspace     (case tracking, researcher CLI)
        │
        ├── cls_psyop       (psychological operation detection)
        ├── cls_quant       (market intelligence)
        ├── cls_leads       (actionable leads)
        ├── cls_world_brief (daily intelligence brief)
        └── cls_db          (dual-write: JSONL + SQLite)
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

# Workspace CLI (case management)
python -m spec1_engine.workspace
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

Key variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | — | Required for investigation and briefing |
| `SPEC1_STORE_PATH` | `spec1_intelligence.jsonl` | Intelligence record store |
| `SPEC1_DB_PATH` | `spec1.db` | SQLite database path |
| `SPEC1_API_HOST` | `0.0.0.0` | API bind address |
| `SPEC1_API_PORT` | `8000` | API port |
| `SPEC1_CRON_HOUR` | `6` | Scheduled cycle hour (24h) |
| `SPEC1_TIMEZONE` | `America/Los_Angeles` | Scheduler timezone |
| `SPEC1_FEED_TIMEOUT` | `15` | Feed fetch timeout (seconds) |
| `SPEC1_QUANT_ENABLED` | `false` | Enable quantitative market pipeline |

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
| POST | /leads | Create a lead |
| GET | /brief | Latest world brief |
| GET | /psyop | PsyOp detections |
| GET | /fara | FARA filings |
| POST | /cycle/run | Trigger a full cycle |
