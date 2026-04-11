"""Signal Parser — ported from cls_osint/parsers/news.py.

Cleans HTML and extracts keywords/entities from Signal text.
Produces ParsedSignal dataclass instances.
"""

from __future__ import annotations

import re
from typing import Optional

from bs4 import BeautifulSoup

from spec1_engine.schemas.models import ParsedSignal, Signal

STOPWORDS: set[str] = {
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "was", "are", "were", "be", "been",
    "has", "have", "had", "will", "would", "could", "should", "may", "might",
    "that", "this", "it", "its", "as", "into", "than", "then", "so", "if",
    "not", "also", "about", "their", "they", "them", "what", "when", "who",
    "which", "more", "said", "over", "after", "before", "been", "between",
    "his", "her", "him", "she", "he", "we", "our", "your", "you", "can",
    "all", "one", "two", "three", "four", "five", "just", "new", "year",
    "says", "like", "some", "there", "where", "most",
}

# Named-entity patterns: capitalized words of 3+ chars that aren't stopwords
ENTITY_PATTERN = re.compile(r"\b([A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,})*)\b")

MAX_KEYWORDS = 15
MAX_ENTITIES = 10
MAX_TEXT_LENGTH = 8000


def _clean_html(text: str) -> str:
    """Remove HTML tags and decode entities using BeautifulSoup."""
    if not text:
        return ""
    try:
        soup = BeautifulSoup(text, "lxml")
        return soup.get_text(separator=" ")
    except Exception:
        # Fallback to regex stripping
        return re.sub(r"<[^>]+>", "", text)


def _normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _truncate(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    return text[:max_len].rsplit(" ", 1)[0] + "..."


def _extract_keywords(text: str, max_kw: int = MAX_KEYWORDS) -> list[str]:
    """Extract unique non-stopword words of 4+ chars."""
    words = re.findall(r"\b[a-zA-Z]{4,}\b", text.lower())
    seen: set[str] = set()
    keywords: list[str] = []
    for word in words:
        if word not in STOPWORDS and word not in seen:
            seen.add(word)
            keywords.append(word)
        if len(keywords) >= max_kw:
            break
    return keywords


def _extract_entities(text: str, max_ent: int = MAX_ENTITIES) -> list[str]:
    """Extract capitalized proper-noun phrases as named entities."""
    matches = ENTITY_PATTERN.findall(text)
    seen: set[str] = set()
    entities: list[str] = []
    for m in matches:
        if m.lower() not in STOPWORDS and m not in seen:
            seen.add(m)
            entities.append(m)
        if len(entities) >= max_ent:
            break
    return entities


def _detect_language(text: str) -> str:
    """Naively detect language (always 'en' for this implementation)."""
    return "en"


def parse_signal(signal: Signal) -> ParsedSignal:
    """Clean and extract structured data from a Signal."""
    raw_text = signal.text or ""
    cleaned = _normalize_whitespace(_clean_html(raw_text))
    cleaned = _truncate(cleaned, MAX_TEXT_LENGTH)

    keywords = _extract_keywords(cleaned)
    entities = _extract_entities(cleaned)
    language = _detect_language(cleaned)
    word_count = len(cleaned.split()) if cleaned else 0

    return ParsedSignal(
        signal_id=signal.signal_id,
        cleaned_text=cleaned,
        keywords=keywords,
        entities=entities,
        language=language,
        word_count=word_count,
    )


def parse_batch(signals: list[Signal]) -> dict:
    """Parse a list of signals, returning parsed and failed."""
    parsed: list[ParsedSignal] = []
    failed: list[dict] = []
    for sig in signals:
        try:
            ps = parse_signal(sig)
            parsed.append(ps)
        except Exception as exc:
            failed.append({"signal_id": sig.signal_id, "error": str(exc)})
    return {"parsed": parsed, "failed": failed}
