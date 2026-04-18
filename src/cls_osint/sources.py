"""OSINT source registry.

Defines all known sources used across cls_osint adapters.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class OsintSource:
    """Metadata about an OSINT source."""

    name: str
    source_type: str      # "rss" | "fara" | "congressional" | "narrative"
    url: str
    credibility: float    # 0–1
    refresh_interval_hours: int = 6
    tags: list[str] = field(default_factory=list)
    active: bool = True


# RSS news feeds (used by cls_osint.feed)
RSS_SOURCES: dict[str, OsintSource] = {
    "war_on_the_rocks": OsintSource(
        name="war_on_the_rocks",
        source_type="RSS",
        url="https://warontherocks.com/feed/",
        credibility=0.90,
        tags=["defense", "strategy", "national_security"],
    ),
    "cipher_brief": OsintSource(
        name="cipher_brief",
        source_type="RSS",
        url="https://www.thecipherbrief.com/feed",
        credibility=0.88,
        tags=["intelligence", "cyber", "national_security"],
    ),
    "just_security": OsintSource(
        name="just_security",
        source_type="RSS",
        url="https://www.justsecurity.org/feed/",
        credibility=0.85,
        tags=["law", "national_security", "human_rights"],
    ),
    "rand": OsintSource(
        name="rand",
        source_type="RSS",
        url="https://www.rand.org/blog.xml",
        credibility=0.92,
        tags=["policy", "defense", "research"],
    ),
    "atlantic_council": OsintSource(
        name="atlantic_council",
        source_type="RSS",
        url="https://www.atlanticcouncil.org/feed/",
        credibility=0.87,
        tags=["geopolitics", "defense", "nato"],
    ),
    "defense_one": OsintSource(
        name="defense_one",
        source_type="RSS",
        url="https://www.defenseone.com/rss/all/",
        credibility=0.83,
        tags=["defense", "military", "technology"],
    ),
    "foreign_affairs": OsintSource(
        name="foreign_affairs",
        source_type="RSS",
        url="https://www.foreignaffairs.com/rss.xml",
        credibility=0.92,
        tags=["foreign_policy", "international_relations"],
    ),
}

# FARA sources
FARA_SOURCES: dict[str, OsintSource] = {
    "fara_db": OsintSource(
        name="fara_db",
        source_type="FARA",
        url="https://www.fara.gov/recent-filings.html",
        credibility=0.95,
        refresh_interval_hours=24,
        tags=["fara", "foreign_agents", "lobbying"],
    ),
}

# Congressional sources
CONGRESSIONAL_SOURCES: dict[str, OsintSource] = {
    "congress_gov": OsintSource(
        name="congress_gov",
        source_type="CONGRESSIONAL",
        url="https://www.congress.gov/rss/legislation.xml",
        credibility=0.99,
        refresh_interval_hours=12,
        tags=["legislation", "congress", "senate", "house"],
    ),
    "govtrack": OsintSource(
        name="govtrack",
        source_type="CONGRESSIONAL",
        url="https://www.govtrack.us/congress/bills/feed",
        credibility=0.92,
        refresh_interval_hours=12,
        tags=["legislation", "bills", "votes"],
    ),
}

# Narrative tracking sources
NARRATIVE_SOURCES: dict[str, OsintSource] = {
    "narrative_tracker": OsintSource(
        name="narrative_tracker",
        source_type="NARRATIVE",
        url="internal",
        credibility=0.70,
        refresh_interval_hours=4,
        tags=["narrative", "influence", "psyop"],
    ),
}

# All sources combined
ALL_SOURCES: dict[str, OsintSource] = {
    **RSS_SOURCES,
    **FARA_SOURCES,
    **CONGRESSIONAL_SOURCES,
    **NARRATIVE_SOURCES,
}


def get_source(name: str) -> OsintSource | None:
    """Retrieve a source by name."""
    return ALL_SOURCES.get(name)


def get_sources_by_type(source_type: str) -> list[OsintSource]:
    """Return all active sources of a given type."""
    return [s for s in ALL_SOURCES.values() if s.source_type == source_type and s.active]


def get_credibility(source_name: str) -> float:
    """Return credibility score for a source name (default 0.5)."""
    src = ALL_SOURCES.get(source_name)
    return src.credibility if src else 0.5
