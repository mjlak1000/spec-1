# SPEC-1 Intelligence Engine

SPEC-1 is a real-time open-source intelligence (OSINT) engine that harvests RSS feeds from authoritative national security sources, parses and scores signals through a 4-gate pipeline, generates investigations, verifies outcomes, and stores intelligence records to JSONL.

## Architecture

```
RSS Harvest → Parse → Score (4 gates) → Investigation → Verify → Intelligence → JSONL Store
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

## Running Tests

```bash
pytest tests/ -v
```
