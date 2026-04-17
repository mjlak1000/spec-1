"""Psyop scorer — scores text against known psyop patterns."""

from __future__ import annotations

import hashlib
from cls_psyop.patterns import PATTERNS, PsyopPattern
from cls_psyop.schemas import PsyopScore


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _count_indicators(text: str, indicators: list[str]) -> int:
    text_lower = text.lower()
    return sum(1 for ind in indicators if ind.lower() in text_lower)


def _classify_score(score: float, matched_count: int) -> str:
    if score >= 0.6 or matched_count >= 3:
        return "HIGH_RISK"
    if score >= 0.3 or matched_count >= 2:
        return "MEDIUM_RISK"
    if score > 0 or matched_count >= 1:
        return "LOW_RISK"
    return "CLEAN"


def score_text(text: str, patterns: list[PsyopPattern] | None = None) -> PsyopScore:
    """Score a piece of text against psyop patterns.

    Returns a PsyopScore with matched patterns and a 0–1 likelihood score.
    """
    if patterns is None:
        patterns = PATTERNS

    text_hash = _hash_text(text)
    matched_ids: list[str] = []
    matched_names: list[str] = []
    matched_categories: set[str] = set()
    total_indicator_hits = 0

    for pattern in patterns:
        hits = _count_indicators(text, pattern.indicators)
        if hits >= 1:
            matched_ids.append(pattern.pattern_id)
            matched_names.append(pattern.name)
            matched_categories.add(pattern.category)
            # Weight by threat level
            weight = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}.get(pattern.threat_level, 1)
            total_indicator_hits += hits * weight

    # Normalise to 0–1 (cap at 1.0)
    max_possible = len(patterns) * 3 * 2  # rough upper bound
    raw_score = total_indicator_hits / max_possible if max_possible > 0 else 0.0
    score = round(min(1.0, raw_score * 5.0), 3)  # scale up for sensitivity

    classification = _classify_score(score, len(matched_ids))

    return PsyopScore(
        score_id=PsyopScore.make_id(text_hash),
        text_hash=text_hash,
        text_excerpt=text[:200],
        patterns_matched=matched_ids,
        pattern_names=matched_names,
        score=score,
        classification=classification,
        threat_categories=sorted(matched_categories),
        metadata={"total_indicator_hits": total_indicator_hits},
    )


def score_records(records: list[dict]) -> list[PsyopScore]:
    """Score a list of record dicts; returns PsyopScore per record."""
    results: list[PsyopScore] = []
    for rec in records:
        text = rec.get("content", rec.get("text", rec.get("summary", "")))
        if not text:
            continue
        ps = score_text(str(text))
        ps.metadata["source_record_id"] = rec.get("record_id", rec.get("signal_id", ""))
        ps.metadata["source_name"] = rec.get("source_name", rec.get("source", ""))
        results.append(ps)
    return results


def filter_risky(scores: list[PsyopScore], min_classification: str = "LOW_RISK") -> list[PsyopScore]:
    """Return only scores at or above the given risk threshold."""
    order = {"CLEAN": 0, "LOW_RISK": 1, "MEDIUM_RISK": 2, "HIGH_RISK": 3}
    threshold = order.get(min_classification, 1)
    return [s for s in scores if order.get(s.classification, 0) >= threshold]
