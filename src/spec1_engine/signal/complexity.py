"""Signal complexity scorer.

Assigns a 0.0–1.0 complexity score to a raw signal before it enters the
4-gate scorer. Low-complexity signals (score < BYPASS_THRESHOLD) skip the
expensive LLM investigation gate and write directly to append-only storage.

No external deps. Pure Python. Designed to run in < 1 ms per signal.

Factors and weights:
  word_count    0.25  — volume proxy; short signals are rarely actionable
  entity_count  0.30  — named-entity density; high entity load → complex
  novelty_hits  0.30  — high-value intel keywords from the 4-gate scorer
  avg_sent_len  0.15  — longer sentences correlate with analytical depth
"""

from __future__ import annotations

import re

from spec1_engine.signal.scorer import NOVELTY_TERMS

BYPASS_THRESHOLD = 0.35   # score < this → skip LLM gate
LLM_GATE_THRESHOLD = BYPASS_THRESHOLD

_SENT_SPLIT = re.compile(r"[.!?]+")


def complexity_score(text: str, keywords: list[str], entities: list[str]) -> float:
    """Return a complexity score in [0.0, 1.0].

    Args:
        text:     Cleaned signal text (HTML already stripped).
        keywords: Pre-extracted keyword list (from parser).
        entities: Pre-extracted entity list (from parser).

    Returns:
        Float in [0.0, 1.0]. Higher = more complex = more likely to need LLM.
    """
    words = text.split()
    word_count = len(words)

    word_score = min(word_count / 300, 1.0)
    entity_score = min(len(entities) / 8, 1.0)

    lower = text.lower()
    kw_lower = {k.lower() for k in keywords}
    novelty_hits = sum(
        1 for term in NOVELTY_TERMS if term in lower or term in kw_lower
    )
    novelty_score = min(novelty_hits / 4, 1.0)

    sentences = [s.strip() for s in _SENT_SPLIT.split(text) if s.strip()]
    avg_len = (word_count / len(sentences)) if sentences else 0.0
    sentence_score = min(avg_len / 25, 1.0)

    return round(
        word_score    * 0.25
        + entity_score  * 0.30
        + novelty_score * 0.30
        + sentence_score * 0.15,
        4,
    )


def route(score: float) -> str:
    """Map a complexity score to a routing label."""
    return "BYPASS" if score < BYPASS_THRESHOLD else "LLM_GATE"
