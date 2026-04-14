"""
SPEC-1 — signal/harvester.py

Collects raw signals from public OSINT sources.
v0.1: mocked collectors with realistic fixture data.
v1.0: replace with real RSS, API, and scraping adapters.

Source categories:
  Publications:  War on the Rocks, The Cipher Brief, Lawfare,
                 Small Wars Journal, Defense One, Breaking Defense, The Drive
  Think tanks:   RAND, CSIS, Atlantic Council, CFR
  Journalists:   Barnes, Dilanian, Bertrand, Harris
  Platforms:     Substack, X/Twitter, RSS, podcast transcripts
"""

from __future__ import annotations

from typing import List

from spec1_engine.core import ids
from spec1_engine.schemas.models import Signal


# ── Source registry ───────────────────────────────────────────────────────────

KNOWN_SOURCES = {
    # Publications
    "war_on_the_rocks":  {"type": "publication",  "domain": ["geopolitics", "defense"]},
    "cipher_brief":      {"type": "publication",  "domain": ["cyber", "intelligence"]},
    "lawfare":           {"type": "publication",  "domain": ["geopolitics", "law"]},
    "small_wars_journal":{"type": "publication",  "domain": ["defense", "irregular_warfare"]},
    "defense_one":       {"type": "publication",  "domain": ["defense", "policy"]},
    "breaking_defense":  {"type": "publication",  "domain": ["defense", "procurement"]},
    "the_drive":         {"type": "publication",  "domain": ["defense", "military_tech"]},
    # Think tanks
    "rand":              {"type": "think_tank",   "domain": ["geopolitics", "defense", "policy"]},
    "csis":              {"type": "think_tank",   "domain": ["geopolitics", "cyber", "defense"]},
    "atlantic_council":  {"type": "think_tank",   "domain": ["geopolitics", "nato", "cyber"]},
    "cfr":               {"type": "think_tank",   "domain": ["geopolitics", "foreign_policy"]},
    # Journalists
    "julian_barnes_nyt": {"type": "journalist",   "domain": ["intelligence", "national_security"]},
    "ken_dilanian_nbc":  {"type": "journalist",   "domain": ["intelligence", "national_security"]},
    "natasha_bertrand":  {"type": "journalist",   "domain": ["defense", "intelligence"]},
    "shane_harris_wapo": {"type": "journalist",   "domain": ["intelligence", "cyber"]},
    # Platforms
    "substack_osint":    {"type": "platform",     "domain": ["geopolitics", "open_source"]},
    "x_twitter":         {"type": "platform",     "domain": ["geopolitics", "cyber", "breaking"]},
    "rss_feed":          {"type": "platform",     "domain": ["multi"]},
}


# ── Mocked fixture signals ────────────────────────────────────────────────────

_MOCK_SIGNALS = [
    {
        "source":      "war_on_the_rocks",
        "author":      "Phillips O'Brien",
        "text":        "Western artillery production remains the central constraint on Ukrainian sustainment. "
                       "The industrial gap between NATO output and Russian consumption rates is not closing at the pace "
                       "required to shift the battlefield equation before the next rotation cycle.",
        "url":         "https://warontherocks.com/mock-article-1",
        "velocity":    0.82,
        "engagement":  0.74,
        "published_at":"2026-03-27T08:00:00Z",
    },
    {
        "source":      "cipher_brief",
        "author":      "Shane Harris",
        "text":        "APT40 infrastructure observed staging against Indo-Pacific logistics nodes. "
                       "Attribution confidence is moderate. The targeting pattern suggests pre-positioning "
                       "rather than active exploitation — consistent with contingency preparation.",
        "url":         "https://thecipherbrief.com/mock-article-2",
        "velocity":    0.91,
        "engagement":  0.68,
        "published_at":"2026-03-27T09:30:00Z",
    },
    {
        "source":      "atlantic_council",
        "author":      "Melinda Haring",
        "text":        "Baltic undersea cable incidents show a clear pattern of hybrid operations "
                       "designed to test NATO response thresholds without triggering Article 5. "
                       "The escalation ladder is being probed systematically.",
        "url":         "https://atlanticcouncil.org/mock-article-3",
        "velocity":    0.77,
        "engagement":  0.81,
        "published_at":"2026-03-27T07:15:00Z",
    },
    {
        "source":      "lawfare",
        "author":      "Ben Wittes",
        "text":        "The legal framework for offensive cyber operations remains dangerously underspecified. "
                       "Three recent incidents have exposed gaps in the existing authorities that no "
                       "current statute adequately addresses.",
        "url":         "https://lawfaremedia.org/mock-article-4",
        "velocity":    0.55,
        "engagement":  0.62,
        "published_at":"2026-03-27T10:00:00Z",
    },
    {
        "source":      "x_twitter",
        "author":      "OSINTdefender",
        "text":        "Satellite imagery shows increased vehicle movement at [REDACTED] logistics depot. "
                       "Pattern consistent with resupply surge. Third observation in 10 days.",
        "url":         None,
        "velocity":    0.94,
        "engagement":  0.88,
        "published_at":"2026-03-27T11:45:00Z",
    },
    {
        "source":      "rand",
        "author":      "RAND Corporation",
        "text":        "New report: Extended deterrence credibility in the Indo-Pacific depends more on "
                       "allied burden-sharing capacity than on forward deployment posture. "
                       "The conventional wisdom is being stress-tested.",
        "url":         "https://rand.org/mock-report-5",
        "velocity":    0.61,
        "engagement":  0.70,
        "published_at":"2026-03-26T14:00:00Z",
    },
]


class OSINTHarvester:
    """
    Collects raw OSINT signals from monitored sources.
    v0.1: returns mocked fixture signals.
    v1.0: connect to RSS feeds, APIs, and scraping adapters.
    """

    def collect(self, run_id: str = "") -> List[Signal]:
        """Return a list of raw signals for this cycle."""
        signals = []
        for raw in _MOCK_SIGNALS:
            source = raw["source"]
            source_meta = KNOWN_SOURCES.get(source, {"type": "unknown", "domain": []})
            sig = Signal(
                signal_id=ids.signal_id(source, raw["text"]),
                source=source,
                source_type=source_meta["type"],
                text=raw["text"],
                url=raw.get("url"),
                author=raw.get("author"),
                published_at=raw.get("published_at"),
                velocity=float(raw.get("velocity", 0.0)),
                engagement=float(raw.get("engagement", 0.0)),
                run_id=run_id,
                environment="osint",
                metadata={"domains": source_meta.get("domain", [])},
            )
            signals.append(sig)
        return signals

    def collect_from_source(self, source: str, run_id: str = "") -> List[Signal]:
        """Collect signals from a specific source only."""
        all_signals = self.collect(run_id=run_id)
        return [s for s in all_signals if s.source == source]
