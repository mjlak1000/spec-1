"""Psyop pattern scorer — cls_psyop.

Detects psyop signatures by scoring clustered patterns across available signals.
A psyop is not a single data point — it's a convergence of detectable patterns
in public data.

Pattern signatures and weights:
  NARRATIVE_CLUSTER = 2  — Same narrative appearing across 3+ media markets simultaneously
  FARA_ACTIVE       = 2  — FARA registrant active in same topic/entity space
  MODEL_LEGISLATION = 3  — Identical or near-identical legislative language across states
  CONSENSUS_SPIKE   = 1  — Expert consensus materialized rapidly with no prior buildup
  NO_ORGANIC_ORIGIN = 2  — No traceable grassroots or organic origin for the narrative

Classification thresholds:
  Score >= 8 → PSYOP_CONFIRMED
  Score >= 5 → PSYOP_CANDIDATE
  Below   5  → NOISE

Input:
  A dict with fields: topic, entities, sources, fara_matches, legislation_matches,
  narrative_markets, consensus_velocity, origin_traceable.

Output:
  Dict: topic, score, classification, patterns_fired, timestamp, run_id.
  Result is also appended to data/psyop_signals.jsonl (append-only, single-writer).
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from spec1_engine.intelligence.store import JsonlStore

# ─── Pattern weights ─────────────────────────────────────────────────────────
NARRATIVE_CLUSTER = 2   # Same narrative appearing across 3+ media markets simultaneously
FARA_ACTIVE       = 2   # FARA registrant active in same topic/entity space
MODEL_LEGISLATION = 3   # Identical or near-identical legislative language across states
CONSENSUS_SPIKE   = 1   # Expert consensus materialized rapidly with no prior buildup
NO_ORGANIC_ORIGIN = 2   # No traceable grassroots or organic origin for the narrative

# ─── Classification thresholds ────────────────────────────────────────────────
THRESHOLD_CONFIRMED = 8   # score >= 8 → PSYOP_CONFIRMED
THRESHOLD_CANDIDATE = 5   # score >= 5 → PSYOP_CANDIDATE
# below 5 → NOISE

# ─── JSONL output ─────────────────────────────────────────────────────────────
DEFAULT_STORE_PATH = Path("data/psyop_signals.jsonl")

# ─── Required input fields ────────────────────────────────────────────────────
REQUIRED_FIELDS: frozenset[str] = frozenset({
    "topic",
    "entities",
    "sources",
    "fara_matches",
    "legislation_matches",
    "narrative_markets",
    "consensus_velocity",
    "origin_traceable",
})

# ─── Single-writer store (module-level singleton) ─────────────────────────────
_store: JsonlStore | None = None


def _get_store(path: Path | None = None) -> JsonlStore:
    """Return the module-level JsonlStore, creating or re-creating as needed."""
    global _store
    target = path or DEFAULT_STORE_PATH
    if _store is None or _store.path != Path(target):
        _store = JsonlStore(Path(target))
    return _store


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ─── Input validation ─────────────────────────────────────────────────────────

def _validate_input(signal: Any) -> None:
    """Raise if signal is not a dict or is missing required fields.

    Args:
        signal: The value to validate.

    Raises:
        TypeError: If signal is not a dict.
        ValueError: If any required field is absent.
    """
    if not isinstance(signal, dict):
        raise TypeError(f"signal must be dict, got {type(signal).__name__}")
    missing = REQUIRED_FIELDS - signal.keys()
    if missing:
        raise ValueError(f"signal missing required fields: {sorted(missing)}")


# ─── Pattern check functions ──────────────────────────────────────────────────

def _check_narrative_cluster(signal: dict) -> bool:
    """Return True if the same narrative appears across 3+ media markets simultaneously."""
    markets = signal.get("narrative_markets")
    if not isinstance(markets, (list, tuple, set, frozenset)):
        return False
    return len(markets) >= 3


def _check_fara_active(signal: dict) -> bool:
    """Return True if a FARA registrant is active in the same topic/entity space."""
    matches = signal.get("fara_matches")
    if isinstance(matches, bool):
        return matches
    if isinstance(matches, (list, tuple, set, frozenset)):
        return len(matches) > 0
    return bool(matches)


def _check_model_legislation(signal: dict) -> bool:
    """Return True if identical or near-identical legislative language was found across states."""
    matches = signal.get("legislation_matches")
    if isinstance(matches, bool):
        return matches
    if isinstance(matches, (list, tuple, set, frozenset)):
        return len(matches) > 0
    return bool(matches)


def _check_consensus_spike(signal: dict) -> bool:
    """Return True if expert consensus materialized rapidly with no prior buildup."""
    velocity = signal.get("consensus_velocity")
    if velocity is None:
        return False
    try:
        return float(velocity) > 0.0
    except (TypeError, ValueError):
        return False


def _check_no_organic_origin(signal: dict) -> bool:
    """Return True if no traceable grassroots or organic origin exists for the narrative."""
    return not bool(signal.get("origin_traceable"))


# ─── Classification ───────────────────────────────────────────────────────────

def _classify(score: int) -> str:
    """Map a numeric score to a classification label.

    Args:
        score: Accumulated pattern weight sum.

    Returns:
        'PSYOP_CONFIRMED', 'PSYOP_CANDIDATE', or 'NOISE'.
    """
    if score >= THRESHOLD_CONFIRMED:
        return "PSYOP_CONFIRMED"
    if score >= THRESHOLD_CANDIDATE:
        return "PSYOP_CANDIDATE"
    return "NOISE"


# ─── Public API ───────────────────────────────────────────────────────────────

def score_psyop(
    signal: dict[str, Any],
    run_id: str = "",
    store_path: Path | None = None,
) -> dict:
    """Score a signal record for psyop pattern signatures.

    Validates input, evaluates all five pattern checks, classifies the result,
    appends it to the JSONL store, and returns the scored result dict.

    Args:
        signal: Dict with fields: topic, entities, sources, fara_matches,
                legislation_matches, narrative_markets, consensus_velocity,
                origin_traceable.
        run_id: Run identifier for traceability. Defaults to empty string.
        store_path: Override the default JSONL output path
                    (data/psyop_signals.jsonl). Useful in tests.

    Returns:
        Dict containing: topic, score, classification, patterns_fired,
        timestamp, run_id.

    Raises:
        TypeError: If signal is not a dict.
        ValueError: If signal is missing one or more required fields.
    """
    _validate_input(signal)

    patterns_fired: list[str] = []
    score = 0

    if _check_narrative_cluster(signal):
        patterns_fired.append("NARRATIVE_CLUSTER")
        score += NARRATIVE_CLUSTER

    if _check_fara_active(signal):
        patterns_fired.append("FARA_ACTIVE")
        score += FARA_ACTIVE

    if _check_model_legislation(signal):
        patterns_fired.append("MODEL_LEGISLATION")
        score += MODEL_LEGISLATION

    if _check_consensus_spike(signal):
        patterns_fired.append("CONSENSUS_SPIKE")
        score += CONSENSUS_SPIKE

    if _check_no_organic_origin(signal):
        patterns_fired.append("NO_ORGANIC_ORIGIN")
        score += NO_ORGANIC_ORIGIN

    result: dict[str, Any] = {
        "topic": signal["topic"],
        "score": score,
        "classification": _classify(score),
        "patterns_fired": patterns_fired,
        "timestamp": _now(),
        "run_id": run_id,
    }

    _get_store(store_path).append(result)
    return result
