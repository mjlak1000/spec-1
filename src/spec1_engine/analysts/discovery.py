"""Discovery Analyst.

Discovers new potential analysts from signal text by pattern matching.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from spec1_engine.analysts.registry import get_all_names
from spec1_engine.schemas.models import ParsedSignal, Signal


@dataclass
class DiscoveredAnalyst:
    """A potential analyst discovered from signal text."""

    name: str
    affiliation_hint: str
    domain_hints: list[str]
    mention_count: int = 1
    discovery_source: str = ""

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "affiliation_hint": self.affiliation_hint,
            "domain_hints": self.domain_hints,
            "mention_count": self.mention_count,
            "discovery_source": self.discovery_source,
        }


# Patterns for detecting analyst mentions
ANALYST_TITLE_PATTERNS = [
    r"(?:said|says|according to|noted|wrote|argues?|writes?)\s+([A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+)",
    r"([A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+),?\s+(?:a\s+)?(?:senior\s+)?(?:fellow|analyst|researcher|director|professor|expert|scholar)",
    r"([A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+),?\s+(?:of|at|from)\s+([A-Z][A-Za-z\s]+(?:University|Institute|Center|Council|Foundation|Corporation|Corp))",
]

AFFILIATION_PATTERN = re.compile(
    r"([A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+).*?(?:at|from|of)\s+([A-Z][A-Za-z\s&]+(?:University|Institute|Center|Council|Foundation|Corporation|Corp|Department|Office))",
    re.IGNORECASE,
)

DOMAIN_KEYWORDS = {
    "russia": ["russia", "russian", "putin", "kremlin", "moscow"],
    "ukraine": ["ukraine", "ukrainian", "zelensky", "kyiv"],
    "china": ["china", "chinese", "beijing", "prc", "ccp"],
    "military": ["military", "army", "navy", "air force", "marines", "defense"],
    "intelligence": ["intelligence", "cia", "nsa", "fbi", "counterintelligence"],
    "cyber": ["cyber", "hacking", "malware", "ransomware", "digital"],
    "nuclear": ["nuclear", "missile", "warhead", "icbm", "deterrence"],
    "nato": ["nato", "alliance", "article 5", "collective defense"],
}


def _infer_domains(text: str) -> list[str]:
    """Infer domain interests from text context."""
    text_lower = text.lower()
    matched: list[str] = []
    for domain, keywords in DOMAIN_KEYWORDS.items():
        if any(kw in text_lower for kw in keywords):
            matched.append(domain)
    return matched[:4]


class DiscoveryAnalyst:
    """Discovers new potential analysts from signal text."""

    def __init__(self) -> None:
        self._known_names: set[str] = {n.lower() for n in get_all_names()}
        self._compiled_patterns = [re.compile(p, re.IGNORECASE) for p in ANALYST_TITLE_PATTERNS]

    def discover(self, signal: Signal, parsed: ParsedSignal) -> list[DiscoveredAnalyst]:
        """Discover potential new analysts mentioned in a signal."""
        text = parsed.cleaned_text
        discovered: dict[str, DiscoveredAnalyst] = {}

        for pattern in self._compiled_patterns:
            for match in pattern.finditer(text):
                name = match.group(1).strip()
                name_lower = name.lower()

                # Skip if already in registry
                if name_lower in self._known_names:
                    continue

                # Skip short/suspicious names
                parts = name.split()
                if len(parts) < 2 or len(name) > 50:
                    continue

                # Try to extract affiliation
                affiliation = ""
                aff_match = AFFILIATION_PATTERN.search(text)
                if aff_match and aff_match.group(1).lower() == name_lower:
                    affiliation = aff_match.group(2).strip()

                domains = _infer_domains(text)

                if name_lower in discovered:
                    discovered[name_lower].mention_count += 1
                else:
                    discovered[name_lower] = DiscoveredAnalyst(
                        name=name,
                        affiliation_hint=affiliation,
                        domain_hints=domains,
                        mention_count=1,
                        discovery_source=signal.url,
                    )

        return list(discovered.values())

    def discover_batch(
        self, signals: list[Signal], parsed_signals: list[ParsedSignal]
    ) -> list[DiscoveredAnalyst]:
        """Discover analysts from a batch of signals."""
        all_discovered: dict[str, DiscoveredAnalyst] = {}
        for sig, ps in zip(signals, parsed_signals):
            for d in self.discover(sig, ps):
                key = d.name.lower()
                if key in all_discovered:
                    all_discovered[key].mention_count += d.mention_count
                else:
                    all_discovered[key] = d
        return sorted(all_discovered.values(), key=lambda x: x.mention_count, reverse=True)
