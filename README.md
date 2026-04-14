# SPEC-1

A loop-centric intelligence learning system for geopolitics and cyber operations.

## What it does

SPEC-1 observes public signals from credible sources, scores them through validation gates, generates structured investigation plans, verifies what holds up, and stores intelligence patterns that make the next cycle smarter.

```
Signal → Opportunity → Investigation → Outcome → Intelligence
```

The system learns which sources, analysts, and narratives produce reliable intelligence over time.

---

## The loop

| Step | Module | Description |
|------|--------|-------------|
| Signal | `signal/harvester.py` | Collect raw observations from monitored sources |
| Opportunity | `signal/scorer.py` | Score through 4 gates, rank by priority |
| Investigation | `investigation/generator.py` | Build structured investigation plan |
| Outcome | `investigation/verifier.py` | Verify, classify, measure confidence |
| Intelligence | `intelligence/analyzer.py` | Extract patterns, update source weights |

---

## Source categories

**Publications**
- War on the Rocks
- The Cipher Brief
- Lawfare
- Small Wars Journal
- Defense One / Breaking Defense / The Drive

**Think tanks**
- RAND Corporation
- CSIS
- Atlantic Council
- Council on Foreign Relations

**Journalists**
- Julian E. Barnes (NYT)
- Ken Dilanian (NBC)
- Natasha Bertrand (CNN)
- Shane Harris (WaPo)

**Platforms**
- Substack
- X / Twitter
- RSS feeds
- Podcast transcripts

---

## Outcome classifications

| Classification | Meaning |
|---------------|---------|
| `Corroborated` | Multiple credible sources confirm |
| `Escalate` | High confidence + high importance |
| `Investigate` | Promising, needs more work |
| `Monitor` | Low confidence, watch for developments |
| `Conflicted` | Contradictory signals |
| `Archive` | Not actionable, store for reference |

---

## Installation

```bash
git clone https://github.com/mjlak1000/spec-1
cd spec-1
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

## Run one cycle

```bash
python -m spec1_engine.app.cycle
```

## Run tests

```bash
pytest
pytest -v                        # verbose
pytest --cov=spec1_engine    # with coverage
```

---

## Architecture

```
src/spec1_engine/
├── core/           # engine, IDs, logging — domain-agnostic
├── schemas/        # typed dataclasses — all loop objects
├── signal/         # harvester + scorer (4-gate validation)
├── investigation/  # generator + verifier
├── intelligence/   # analyzer + in-memory store
├── analysts/       # registry, credibility, discovery
└── app/            # cycle.py — public entrypoint
```

**Design rules:**
- Core never contains domain logic
- All records append-only — no deletes, no overwrites
- Every object carries `run_id` for full traceability
- Kill switch: `touch .cls_kill` halts all processing
- v0.1 uses mocked collectors — replace with real adapters in v1.0

---

## Roadmap

**Phase 1 (current):** Mocked OSINT cycle, full loop, analyst tracking stubs

**Phase 2:** Real source adapters — RSS feeds, HTTP scraping via n8n

**Phase 3:** Claude API integration for signal analysis and briefing generation

**Phase 4:** PostgreSQL persistence, append-only schema, run_id traceability

**Phase 5:** FastAPI layer, scheduled daily runs, kill switch, audit log

---

## Author

Matt Lakamp · Portland, OR  
503-317-7821 · Lakamp@evastararcana.com  
Continuous Learning System — OSINT Core Engine
