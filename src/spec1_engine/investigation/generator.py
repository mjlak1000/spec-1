"""Investigation Generator.

Generates Investigation instances from Opportunity + Signal + ParsedSignal.
"""

from __future__ import annotations

from spec1_engine.core.ids import investigation_id
from spec1_engine.schemas.models import Investigation, Opportunity, ParsedSignal, Signal

# Authoritative sources to check for each investigation
AUTHORITATIVE_SOURCES = [
    "https://warontherocks.com",
    "https://www.thecipherbrief.com",
    "https://www.lawfaremedia.org",
    "https://www.rand.org",
    "https://www.atlanticcouncil.org",
    "https://www.defenseone.com",
    "https://www.bellingcat.com",
    "https://intelligence.house.gov",
    "https://www.dni.gov",
]

ANALYST_POOL = [
    "Julian E. Barnes",
    "Ken Dilanian",
    "Natasha Bertrand",
    "Shane Harris",
    "Phillips O'Brien",
    "Michael Kofman",
    "Dara Massicot",
    "Thomas Rid",
    "Melinda Haring",
]


def _build_hypothesis(signal: Signal, parsed: ParsedSignal) -> str:
    """Build a hypothesis statement from signal data."""
    entities = parsed.entities[:3]
    keywords = parsed.keywords[:5]
    entity_str = ", ".join(entities) if entities else "identified actors"
    kw_str = "; ".join(keywords) if keywords else "the reported events"
    source = signal.source.replace("_", " ").title()
    return (
        f"The reporting from {source} concerning {entity_str} regarding {kw_str} "
        f"may indicate a significant intelligence development warranting further investigation."
    )


def _build_queries(signal: Signal, parsed: ParsedSignal) -> list[str]:
    """Generate investigation queries from keywords and entities."""
    queries: list[str] = []
    for entity in parsed.entities[:4]:
        queries.append(f'"{entity}" site:rand.org OR site:atlanticcouncil.org')
        queries.append(f'"{entity}" intelligence analysis')
    for kw in parsed.keywords[:3]:
        queries.append(f"{kw} national security implications")
    queries.append(f'"{signal.source.replace("_", " ")}" {" ".join(parsed.keywords[:2])}')
    return queries[:8]


def _select_analyst_leads(parsed: ParsedSignal) -> list[str]:
    """Select relevant analyst leads based on keywords."""
    text_lower = parsed.cleaned_text.lower()
    leads: list[str] = []

    analyst_domains = {
        "Michael Kofman": ["russia", "ukraine", "military"],
        "Dara Massicot": ["russia", "military", "forces"],
        "Melinda Haring": ["ukraine", "eastern europe", "kyiv"],
        "Thomas Rid": ["information", "warfare", "cyber", "disinformation"],
        "Phillips O'Brien": ["military", "strategy", "naval", "air power"],
        "Julian E. Barnes": ["intelligence", "cia", "nsa", "pentagon"],
        "Ken Dilanian": ["intelligence", "fbi", "investigation"],
        "Natasha Bertrand": ["pentagon", "defense", "military"],
        "Shane Harris": ["intelligence", "nsa", "cyber", "security"],
    }

    for analyst, domains in analyst_domains.items():
        if any(d in text_lower for d in domains):
            leads.append(analyst)
        if len(leads) >= 3:
            break

    if not leads:
        leads = ANALYST_POOL[:2]

    return leads


def generate_investigation(
    opportunity: Opportunity,
    signal: Signal,
    parsed: ParsedSignal,
) -> Investigation:
    """Generate an Investigation from an Opportunity."""
    return Investigation(
        investigation_id=investigation_id(),
        opportunity_id=opportunity.opportunity_id,
        hypothesis=_build_hypothesis(signal, parsed),
        queries=_build_queries(signal, parsed),
        sources_to_check=AUTHORITATIVE_SOURCES[:5],
        analyst_leads=_select_analyst_leads(parsed),
    )
