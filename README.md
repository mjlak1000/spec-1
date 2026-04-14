# SPEC-1 Intelligence Engine

SPEC-1 is a real-time open-source intelligence (OSINT) engine that harvests RSS feeds from authoritative national security sources, parses and scores signals through a 4-gate pipeline, generates investigations, verifies outcomes, and stores intelligence records to JSONL and (optionally) PostgreSQL.

## Architecture

```
RSS Harvest → Parse → Score (4 gates) → Investigation → Verify → Intelligence → JSONL + PostgreSQL Store
```

## Sources

- War on the Rocks
- Cipher Brief
- Lawfare
- RAND
- Atlantic Council
- Defense One

## Quick Start

```bash
pip install -e ".[dev]"
python -m spec1_engine.app.cycle
```

## API

The FastAPI service exposes 10 endpoints under `/api/v1`:

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Service health check |
| POST | `/cycle/run` | Trigger an immediate pipeline cycle |
| GET | `/cycle/status` | Status of the last completed cycle |
| GET | `/signals/latest` | Most recent harvested signals |
| GET | `/intelligence/latest` | Most recent intelligence records |
| GET | `/brief/latest` | The most recently generated daily brief |
| GET | `/brief/index` | Brief index (all briefs, newest first) |
| GET | `/brief/{date}` | Brief for a specific date (YYYY-MM-DD) |
| POST | `/kill` | Engage the kill switch (halts scheduled cycles) |
| DELETE | `/kill` | Clear the kill switch |

Start the server:

```bash
python -m spec1_engine.main
```

## Persistence

### JSONL (always active)

Records are appended to `spec1_intelligence.jsonl` — an append-only audit trail.

### PostgreSQL (optional)

Set `DATABASE_URL` to activate dual-write to PostgreSQL. The JSONL store remains
the primary audit trail; PostgreSQL enables SQL queries across runs.

```bash
export DATABASE_URL="postgresql://user:password@localhost/spec1"
python -m spec1_engine.app.cycle
```

Install the optional PostgreSQL driver:

```bash
pip install "spec1-engine[postgres]"
```

## Kill Switch

Touch `.cls_kill` in the working directory (or call `POST /api/v1/kill`) to halt
all scheduled cycle runs without stopping the server.

## Running Tests

```bash
pytest tests/ -v
```
