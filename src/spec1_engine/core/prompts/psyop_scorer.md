# SPEC-1 Psyop Scorer

Scores a signal batch for psychological-operation signatures.
A psyop is not a single data point — it is a convergence of detectable
patterns in public data.

## Input Schema

```python
{
    "topic": str,                    # dominant topic keyword
    "entities": list[str],           # named entities across signals
    "sources": list[str],            # unique source feed names
    "fara_matches": list | bool,     # FARA registrants active in topic space
    "legislation_matches": list | bool,  # identical legislative language across states
    "narrative_markets": list[str],  # media markets where narrative appears
    "consensus_velocity": float,     # rate at which expert consensus formed (0.0+)
    "origin_traceable": bool,        # True if organic origin is traceable
}
```

## Output Schema

```python
{
    "topic": str,
    "score": int,
    "classification": str,       # "NOISE" | "PSYOP_CANDIDATE" | "PSYOP_CONFIRMED"
    "patterns_fired": list[str], # subset of pattern names below
    "timestamp": str,            # ISO 8601 UTC
    "run_id": str,
}
```

## Scoring Dimensions

| Pattern | Weight | Fires when |
|---------|--------|------------|
| `NARRATIVE_CLUSTER` | 2 | Same narrative in 3+ media markets simultaneously |
| `FARA_ACTIVE` | 2 | FARA registrant active in topic/entity space |
| `MODEL_LEGISLATION` | 3 | Identical legislative language across states |
| `CONSENSUS_SPIKE` | 1 | Expert consensus formed with no prior buildup (`consensus_velocity > 0`) |
| `NO_ORGANIC_ORIGIN` | 2 | No traceable grassroots origin (`origin_traceable == False`) |

## Classification Thresholds

| Score | Classification |
|-------|---------------|
| ≥ 8 | `PSYOP_CONFIRMED` |
| ≥ 5 | `PSYOP_CANDIDATE` |
| < 5 | `NOISE` |

## Implementation

Module: `src/spec1_engine/cls_psyop/scorer.py`

The scorer is stateless with respect to scoring logic. Each call is independent.
Results are appended to `data/psyop_signals.jsonl` (side-effect, not part of
the scoring contract).

## Determinism

Given identical input, `score_psyop()` produces identical `score`,
`classification`, and `patterns_fired`. Only `timestamp` and `run_id` vary.

## Version

This document describes the scorer as of SPEC-1 v0.4.0.
Pattern weights and thresholds constitute a versioned contract.
Changes require a MINOR version bump (or MAJOR if thresholds change).
