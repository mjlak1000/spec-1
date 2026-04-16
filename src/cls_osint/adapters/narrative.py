"""Narrative / influence-operation adapter.

Analyses a corpus of OSINTRecords to detect recurring narrative themes,
amplification patterns, and potential influence operations.
"""

from __future__ import annotations

import hashlib
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Sequence

from cls_osint.schemas import NarrativeRecord, OSINTRecord


# Known narrative themes with seed keywords
NARRATIVE_THEMES: dict[str, list[str]] = {
    "China-Taiwan escalation": [
        "taiwan", "strait", "pla", "invasion", "blockade", "reunification",
        "one china", "taipei", "tsai",
    ],
    "Russia-Ukraine conflict": [
        "ukraine", "russia", "zelensky", "putin", "kremlin", "kyiv", "donbas",
        "nato", "war crimes", "mobilization",
    ],
    "Iran nuclear threat": [
        "iran", "iaea", "enrichment", "nuclear deal", "jcpoa", "sanctions",
        "centrifuge", "uranium", "tehran",
    ],
    "North Korea missile program": [
        "north korea", "dprk", "kim jong", "icbm", "missile test", "pyongyang",
        "nuclear warhead", "ballistic",
    ],
    "US election interference": [
        "election interference", "disinformation", "foreign influence",
        "voter fraud", "campaign hack", "social media manipulation",
    ],
    "China cyber operations": [
        "apt41", "apt10", "volt typhoon", "chinese hackers", "espionage",
        "intellectual property theft", "prc cyber",
    ],
    "ISIS/terrorism resurgence": [
        "isis", "isil", "daesh", "al-qaeda", "jihad", "caliphate",
        "terrorism", "extremism", "insurgency",
    ],
    "US-China trade war": [
        "tariffs", "trade war", "decoupling", "supply chain", "semiconductors",
        "export controls", "huawei", "tiktok",
    ],
    "Middle East destabilization": [
        "hamas", "hezbollah", "gaza", "west bank", "israel", "iran proxy",
        "houthi", "red sea", "strait of hormuz",
    ],
    "COVID-19 origins narrative": [
        "lab leak", "wuhan", "covid origin", "gain of function",
        "who investigation", "natural origin",
    ],
}

_AMPLIFIER_DOMAINS = [
    "rt.com", "sputniknews.com", "xinhua.net", "cgtn.com",
    "presstv.com", "globalresearch.ca", "zerohedge.com",
]


def _normalize(text: str) -> str:
    return text.lower()


def _count_theme_hits(text: str, keywords: list[str]) -> int:
    normed = _normalize(text)
    return sum(1 for kw in keywords if kw in normed)


def _detect_sentiment(text: str) -> str:
    text_lower = text.lower()
    negative_words = [
        "threat", "danger", "attack", "crisis", "war", "kill", "destroy",
        "failed", "collapse", "invasion", "conflict", "violence",
    ]
    positive_words = [
        "peace", "agreement", "cooperation", "ally", "success", "resolve",
        "diplomatic", "ceasefire", "progress", "deal",
    ]
    neg_count = sum(1 for w in negative_words if w in text_lower)
    pos_count = sum(1 for w in positive_words if w in text_lower)
    if neg_count > pos_count + 2:
        return "negative"
    if pos_count > neg_count + 2:
        return "positive"
    if neg_count > 0 and pos_count > 0:
        return "mixed"
    return "neutral"


def _detect_amplifiers(records: list[OSINTRecord], theme_keywords: list[str]) -> list[str]:
    """Identify source names that repeatedly amplify a given theme."""
    source_hits: Counter = Counter()
    for rec in records:
        hits = _count_theme_hits(rec.content, theme_keywords)
        if hits >= 2:
            source_hits[rec.source_name] += hits
    # Return top amplifiers
    return [name for name, _ in source_hits.most_common(10)]


def _compute_reach_score(records: list[OSINTRecord], theme: str, hits: int) -> float:
    """Estimate reach as fraction of corpus that mentions the theme."""
    total = len(records)
    if total == 0:
        return 0.0
    score = min(1.0, hits / max(total, 1) * 3.0)  # scale up
    return round(score, 3)


def _make_record_id(theme: str, detected_at_iso: str) -> str:
    raw = f"{theme}::{detected_at_iso}"
    return "narrative_" + hashlib.sha256(raw.encode()).hexdigest()[:12]


def detect_narratives(
    records: Sequence[OSINTRecord],
    min_hits: int = 2,
    top_themes: int = 10,
) -> list[NarrativeRecord]:
    """Detect narrative themes across a corpus of OSINTRecords.

    Args:
        records: OSINTRecord instances to analyse.
        min_hits: Minimum keyword hit count to register a theme.
        top_themes: Maximum number of themes to return.

    Returns:
        List of NarrativeRecord instances, sorted by reach_score descending.
    """
    records_list = list(records)
    if not records_list:
        return []

    now = datetime.now(timezone.utc)
    results: list[NarrativeRecord] = []

    # Aggregate all text for quick theme scanning
    theme_total_hits: Counter = Counter()
    theme_records: dict[str, list[OSINTRecord]] = defaultdict(list)

    for rec in records_list:
        for theme, keywords in NARRATIVE_THEMES.items():
            hits = _count_theme_hits(rec.content, keywords)
            if hits >= 1:
                theme_total_hits[theme] += hits
                theme_records[theme].append(rec)

    for theme, total_hits in theme_total_hits.most_common(top_themes):
        if total_hits < min_hits:
            continue

        matching_records = theme_records[theme]
        keywords = NARRATIVE_THEMES[theme]
        amplifiers = _detect_amplifiers(matching_records, keywords)
        source_urls = list({r.url for r in matching_records if r.url})[:10]
        all_text = " ".join(r.content for r in matching_records)
        sentiment = _detect_sentiment(all_text)
        reach = _compute_reach_score(records_list, theme, total_hits)

        detected_at = now
        record_id = _make_record_id(theme, detected_at.isoformat())

        desc = (
            f"Theme '{theme}' detected across {len(matching_records)} source(s) "
            f"with {total_hits} keyword hit(s). Sentiment: {sentiment}."
        )

        results.append(
            NarrativeRecord(
                record_id=record_id,
                theme=theme,
                description=desc,
                amplifiers=amplifiers,
                reach_score=reach,
                sentiment=sentiment,
                source_urls=source_urls,
                detected_at=detected_at,
                metadata={
                    "total_hits": total_hits,
                    "matching_sources": len(matching_records),
                    "keywords": keywords[:5],
                },
            )
        )

    results.sort(key=lambda r: r.reach_score, reverse=True)
    return results


def analyse_corpus(
    records: Sequence[OSINTRecord],
    min_hits: int = 2,
) -> list[NarrativeRecord]:
    """Alias for detect_narratives — public API for the narrative adapter."""
    return detect_narratives(records, min_hits=min_hits)
