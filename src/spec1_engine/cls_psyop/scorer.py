"""Psyop pattern scorer — spec1_engine.cls_psyop.

Detects psyop signatures by scoring clustered patterns across harvested signals
and building structured evidence chains for downstream briefing.

Pattern names and weights:
  NARRATIVE_CLUSTER  weight 2  — Same narrative appearing across 3+ media markets
  FARA_ACTIVE        weight 2  — FARA registrant active in same topic/entity space
  MODEL_LEGISLATION  weight 3  — Identical legislative language across states
  CONSENSUS_SPIKE    weight 1  — Rapid consensus with no prior buildup
  NO_ORGANIC_ORIGIN  weight 2  — No traceable grassroots origin

Classification thresholds:
  Score >= 8 → PSYOP_CONFIRMED
  Score >= 5 → PSYOP_CANDIDATE
  Score == 0 → CLEAN
  Else       → NOISE
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cls_psyop.evidence import EvidenceChain, EvidenceStore
from spec1_engine.intelligence.store import JsonlStore

# ─── Pattern name constants (strings) ────────────────────────────────────────
NARRATIVE_CLUSTER = "NARRATIVE_CLUSTER"
FARA_ACTIVE       = "FARA_ACTIVE"
MODEL_LEGISLATION = "MODEL_LEGISLATION"
CONSENSUS_SPIKE   = "CONSENSUS_SPIKE"
NO_ORGANIC_ORIGIN = "NO_ORGANIC_ORIGIN"

# ─── Numeric weights ──────────────────────────────────────────────────────────
_WEIGHTS: dict[str, int] = {
    NARRATIVE_CLUSTER: 2,
    FARA_ACTIVE:       2,
    MODEL_LEGISLATION: 3,
    CONSENSUS_SPIKE:   1,
    NO_ORGANIC_ORIGIN: 2,
}

# ─── Classification thresholds (exported for tests) ───────────────────────────
THRESHOLD_CONFIRMED = 8
THRESHOLD_CANDIDATE = 5

# ─── Detection thresholds ────────────────────────────────────────────────────
_NARRATIVE_CLUSTER_MIN_MARKETS = 3
_CONSENSUS_SPIKE_MIN_VELOCITY  = 0.3   # > 0.3 fires; ≤ 0.3 is noise

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

# ─── Module-level JSONL store (for legacy psyop_signals.jsonl output) ─────────
_DEFAULT_STORE_PATH = Path("data/psyop_signals.jsonl")
_store: JsonlStore | None = None


def _get_store(path: Path | None = None) -> JsonlStore:
    global _store
    target = path or _DEFAULT_STORE_PATH
    if _store is None or _store.path != Path(target):
        _store = JsonlStore(Path(target))
    return _store


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ─── Input validation ─────────────────────────────────────────────────────────

def _validate_input(signal: Any) -> None:
    if not isinstance(signal, dict):
        raise TypeError(f"signal must be dict, got {type(signal).__name__}")
    missing = REQUIRED_FIELDS - signal.keys()
    if missing:
        raise ValueError(f"signal missing required fields: {sorted(missing)}")


# ─── Classification ───────────────────────────────────────────────────────────

def _classify(score: int) -> str:
    if score == 0:
        return "CLEAN"
    if score >= THRESHOLD_CONFIRMED:
        return "PSYOP_CONFIRMED"
    if score >= THRESHOLD_CANDIDATE:
        return "PSYOP_CANDIDATE"
    return "NOISE"


# ─── Evidence-chain detectors ─────────────────────────────────────────────────

def _detect_narrative_cluster(signal: dict) -> EvidenceChain | None:
    """Return an EvidenceChain if 3+ narrative markets cover the same topic."""
    markets = signal.get("narrative_markets", [])
    if not isinstance(markets, (list, tuple, set, frozenset)):
        return None
    if len(markets) < _NARRATIVE_CLUSTER_MIN_MARKETS:
        return None

    signals_data: list[dict] = signal.get("signals_data", [])

    raw_excerpts = [
        {
            "signal_id": s.get("signal_id", ""),
            "source": s.get("source", ""),
            "text_snippet": s.get("text", "")[:280],
            "url": s.get("url", ""),
        }
        for s in signals_data
    ]

    # Per-source metadata and cross-reference detection
    source_map: dict[str, dict] = {}
    for s in signals_data:
        src = s.get("source", "")
        if src not in source_map:
            source_map[src] = {
                "source": src,
                "credibility_score": 0.7,
                "signal_count": 0,
                "first_seen": s.get("published_at", ""),
                "last_seen": s.get("published_at", ""),
            }
        source_map[src]["signal_count"] += 1
        source_map[src]["last_seen"] = s.get("published_at", "")

    source_metadata = list(source_map.values())

    cross_references: list[str] = []
    for meta in source_metadata:
        if meta["signal_count"] >= 2:
            for s in signals_data:
                if s.get("source") == meta["source"]:
                    sig_id = s.get("signal_id", "")
                    if sig_id:
                        cross_references.append(sig_id)

    n = len(markets)
    confidence = min(0.3 + n * 0.1, 0.95)
    summary = (
        f"{n} sources published {signal.get('topic', '—')} assessments — "
        f"pattern: {NARRATIVE_CLUSTER}, confidence: {confidence:.2f}"
    )

    return EvidenceChain(
        pattern_name=NARRATIVE_CLUSTER,
        confidence=confidence,
        supporting_signals=[s.get("signal_id", "") for s in signals_data],
        raw_excerpts=raw_excerpts,
        source_metadata=source_metadata,
        cross_references=cross_references,
        summary=summary,
    )


def _detect_consensus_spike(signal: dict) -> EvidenceChain | None:
    """Return an EvidenceChain if consensus velocity exceeds threshold."""
    try:
        velocity = float(signal.get("consensus_velocity", 0.0))
    except (TypeError, ValueError):
        return None

    if velocity <= _CONSENSUS_SPIKE_MIN_VELOCITY:
        return None

    sources = signal.get("sources", [])
    signals_data: list[dict] = signal.get("signals_data", [])

    raw_excerpts = [
        {
            "signal_id": s.get("signal_id", ""),
            "source": s.get("source", ""),
            "text_snippet": s.get("text", "")[:280],
            "url": s.get("url", ""),
        }
        for s in signals_data
    ]

    summary = (
        f"{len(sources)} outlets published on '{signal.get('topic', '—')}' "
        f"with velocity {velocity:.2f} — pattern: {CONSENSUS_SPIKE}, confidence: {velocity:.2f}"
    )

    return EvidenceChain(
        pattern_name=CONSENSUS_SPIKE,
        confidence=velocity,
        supporting_signals=[s.get("signal_id", "") for s in signals_data],
        raw_excerpts=raw_excerpts,
        source_metadata=[],
        cross_references=[],
        summary=summary,
    )


# ─── Public API ───────────────────────────────────────────────────────────────

def score_psyop(
    signal: dict[str, Any],
    run_id: str = "",
    store_path: Path | None = None,
    evidence_store_path: Path | None = None,
) -> dict:
    """Score a signal for psyop patterns, building structured evidence chains.

    Writes the scored result to store_path (psyop_signals.jsonl, append-only).
    Evidence chains are written to evidence_store_path when provided.

    Returns a dict with: topic, score, classification, patterns_fired,
    evidence_chains, timestamp, run_id.
    """
    _validate_input(signal)

    patterns_fired: list[str] = []
    evidence_chains: list[EvidenceChain] = []
    score = 0

    nc_chain = _detect_narrative_cluster(signal)
    if nc_chain is not None:
        patterns_fired.append(NARRATIVE_CLUSTER)
        score += _WEIGHTS[NARRATIVE_CLUSTER]
        evidence_chains.append(nc_chain)

    fara = signal.get("fara_matches")
    if (isinstance(fara, (list, tuple, set, frozenset)) and len(fara) > 0) or (isinstance(fara, bool) and fara):
        patterns_fired.append(FARA_ACTIVE)
        score += _WEIGHTS[FARA_ACTIVE]

    legis = signal.get("legislation_matches")
    if (isinstance(legis, (list, tuple, set, frozenset)) and len(legis) > 0) or (isinstance(legis, bool) and legis):
        patterns_fired.append(MODEL_LEGISLATION)
        score += _WEIGHTS[MODEL_LEGISLATION]

    cs_chain = _detect_consensus_spike(signal)
    if cs_chain is not None:
        patterns_fired.append(CONSENSUS_SPIKE)
        score += _WEIGHTS[CONSENSUS_SPIKE]
        evidence_chains.append(cs_chain)

    if not bool(signal.get("origin_traceable")):
        patterns_fired.append(NO_ORGANIC_ORIGIN)
        score += _WEIGHTS[NO_ORGANIC_ORIGIN]

    # Populate cross-references across chains using other chains' signal ids
    if len(evidence_chains) >= 2:
        for i, chain in enumerate(evidence_chains):
            other_ids: set[str] = set()
            for j, other in enumerate(evidence_chains):
                if j != i:
                    other_ids.update(other.supporting_signals)
            chain.cross_references = list(set(chain.cross_references) | other_ids)

    # Persist evidence chains to evidence_store_path
    if evidence_chains and evidence_store_path is not None:
        EvidenceStore(Path(evidence_store_path)).append_batch(evidence_chains, run_id=run_id)

    result: dict[str, Any] = {
        "topic": signal["topic"],
        "score": score,
        "classification": _classify(score),
        "patterns_fired": patterns_fired,
        "evidence_chains": [c.to_dict() for c in evidence_chains],
        "timestamp": _now(),
        "run_id": run_id,
    }

    # Legacy JSONL output for psyop_signals.jsonl
    _get_store(store_path).append(result)

    return result
