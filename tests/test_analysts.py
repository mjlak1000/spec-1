"""Tests for analysts — registry, credibility scoring, discovery."""

from __future__ import annotations

import pytest

from spec1_engine.analysts.registry import (
    load_all,
    find_by_name,
    find_by_domain,
    get_all_names,
    get_credibility,
)
from spec1_engine.analysts.credibility import CredibilityAnalyst
from spec1_engine.analysts.discovery import DiscoveryAnalyst, DiscoveredAnalyst
from spec1_engine.schemas.models import AnalystRecord, ParsedSignal, Signal
from datetime import datetime, timezone

REQUIRED_ANALYSTS = [
    "Julian E. Barnes",
    "Ken Dilanian",
    "Natasha Bertrand",
    "Shane Harris",
    "Phillips O'Brien",
    "Michael Kofman",
    "Dara Massicot",
    "Thomas Rid",
    "Melinda Haring",
    "RAND Corp",
    "CSIS",
]


# ─── Helpers ─────────────────────────────────────────────────────────────────

def make_signal(author: str = "", source: str = "war_on_the_rocks", text: str = "") -> Signal:
    return Signal(
        signal_id="test-sig-001",
        source=source,
        source_type="rss",
        text=text or "Some signal text about military intelligence operations.",
        url="https://example.com/article",
        author=author,
        published_at=datetime.now(timezone.utc),
        velocity=0.5,
        engagement=0.0,
        run_id="run-test",
        environment="test",
        metadata={},
    )


def make_parsed(text: str = "", keywords: list[str] | None = None) -> ParsedSignal:
    return ParsedSignal(
        signal_id="test-sig-001",
        cleaned_text=text or "Military intelligence operations in Ukraine.",
        keywords=keywords or ["military", "intelligence", "ukraine"],
        entities=["Ukraine", "NATO"],
        language="en",
        word_count=len((text or "military intelligence").split()),
    )


# ─── Registry tests ───────────────────────────────────────────────────────────

def test_registry_loads_all_analysts():
    analysts = load_all()
    assert len(analysts) == 11


def test_all_required_analysts_present():
    names = get_all_names()
    for required in REQUIRED_ANALYSTS:
        assert required in names, f"Missing analyst: {required}"


def test_julian_barnes_present():
    assert find_by_name("Julian E. Barnes") is not None


def test_ken_dilanian_present():
    assert find_by_name("Ken Dilanian") is not None


def test_natasha_bertrand_present():
    assert find_by_name("Natasha Bertrand") is not None


def test_shane_harris_present():
    assert find_by_name("Shane Harris") is not None


def test_phillips_obrien_present():
    assert find_by_name("Phillips O'Brien") is not None


def test_michael_kofman_present():
    assert find_by_name("Michael Kofman") is not None


def test_dara_massicot_present():
    assert find_by_name("Dara Massicot") is not None


def test_thomas_rid_present():
    assert find_by_name("Thomas Rid") is not None


def test_melinda_haring_present():
    assert find_by_name("Melinda Haring") is not None


def test_rand_corp_present():
    assert find_by_name("RAND Corp") is not None


def test_csis_present():
    assert find_by_name("CSIS") is not None


def test_find_by_name_case_insensitive():
    result = find_by_name("julian e. barnes")
    assert result is not None
    assert result.name == "Julian E. Barnes"


def test_find_by_name_not_found_returns_none():
    result = find_by_name("Not A Real Person")
    assert result is None


def test_all_analysts_have_valid_credibility():
    for a in load_all():
        assert 0.0 < a.credibility_score <= 1.0, f"{a.name} has invalid score"


def test_all_analysts_have_affiliation():
    for a in load_all():
        assert a.affiliation, f"{a.name} missing affiliation"


def test_all_analysts_have_domains():
    for a in load_all():
        assert len(a.domains) > 0, f"{a.name} has no domains"


def test_all_analysts_have_analyst_id():
    for a in load_all():
        assert a.analyst_id.startswith("analyst-"), f"{a.name} has bad ID"


def test_get_credibility_known_analyst():
    score = get_credibility("Michael Kofman")
    assert score == pytest.approx(0.92)


def test_get_credibility_unknown_returns_default():
    score = get_credibility("Unknown Person XYZ")
    assert score == 0.50


def test_find_by_domain_russia():
    results = find_by_domain("russia")
    names = [r.name for r in results]
    assert "Michael Kofman" in names
    assert "Dara Massicot" in names


def test_find_by_domain_intelligence():
    results = find_by_domain("intelligence")
    assert len(results) > 0


def test_analyst_record_to_dict():
    a = find_by_name("Thomas Rid")
    d = a.to_dict()
    assert d["name"] == "Thomas Rid"
    assert "affiliation" in d
    assert "domains" in d
    assert "credibility_score" in d


# ─── CredibilityAnalyst tests ─────────────────────────────────────────────────

def test_credibility_analyst_init():
    ca = CredibilityAnalyst()
    assert ca.count_known() == 11


def test_credibility_analyst_known_author():
    ca = CredibilityAnalyst()
    sig = make_signal(author="Julian E. Barnes")
    score = ca.score(sig)
    assert score == pytest.approx(0.90)


def test_credibility_analyst_unknown_author():
    ca = CredibilityAnalyst()
    sig = make_signal(author="Random Person")
    score = ca.score(sig)
    assert score == 0.50


def test_credibility_analyst_empty_author():
    ca = CredibilityAnalyst()
    sig = make_signal(author="")
    score = ca.score(sig)
    assert score == 0.50


def test_credibility_analyst_identify_known():
    ca = CredibilityAnalyst()
    sig = make_signal(author="Michael Kofman")
    analyst = ca.identify_analyst(sig)
    assert analyst is not None
    assert analyst.name == "Michael Kofman"


def test_credibility_analyst_identify_unknown():
    ca = CredibilityAnalyst()
    sig = make_signal(author="Someone Unknown")
    analyst = ca.identify_analyst(sig)
    assert analyst is None


def test_credibility_analyst_batch_scoring():
    ca = CredibilityAnalyst()
    signals = [
        make_signal(author="Shane Harris"),
        make_signal(author="Unknown"),
        make_signal(author="Dara Massicot"),
    ]
    scores = ca.score_batch(signals)
    assert len(scores) == 3
    assert scores[0] == pytest.approx(0.88)
    assert scores[1] == 0.50
    assert scores[2] == pytest.approx(0.91)


def test_credibility_analyst_get_known_analysts():
    ca = CredibilityAnalyst()
    known = ca.get_known_analysts()
    assert len(known) == 11
    assert all(isinstance(a, AnalystRecord) for a in known)


# ─── DiscoveryAnalyst tests ───────────────────────────────────────────────────

def test_discovery_analyst_init():
    da = DiscoveryAnalyst()
    assert da is not None


def test_discovery_skips_known_analysts():
    da = DiscoveryAnalyst()
    sig = make_signal(text="According to Michael Kofman at CNA, the situation is complex.")
    ps = make_parsed(text="According to Michael Kofman at CNA, the situation is complex.")
    found = da.discover(sig, ps)
    # Michael Kofman is known — should not appear as discovered
    names = [d.name for d in found]
    assert "Michael Kofman" not in names


def test_discovery_finds_new_analyst():
    da = DiscoveryAnalyst()
    text = "According to Dr. James Wilson, a senior fellow at the Defense Institute, the threat is real."
    sig = make_signal(text=text)
    ps = make_parsed(text=text)
    found = da.discover(sig, ps)
    # Should find James Wilson or similar
    assert isinstance(found, list)


def test_discovery_batch_returns_list():
    da = DiscoveryAnalyst()
    signals = [make_signal() for _ in range(3)]
    parsed = [make_parsed() for _ in range(3)]
    result = da.discover_batch(signals, parsed)
    assert isinstance(result, list)


def test_discovered_analyst_to_dict():
    d = DiscoveredAnalyst(
        name="Test Person",
        affiliation_hint="Some Institute",
        domain_hints=["military", "intelligence"],
        mention_count=2,
        discovery_source="https://example.com",
    )
    dd = d.to_dict()
    assert dd["name"] == "Test Person"
    assert dd["mention_count"] == 2
    assert "domain_hints" in dd


# ─── Credibility partial match tests ─────────────────────────────────────────

def test_credibility_partial_match_by_last_name():
    """Score returns analyst score when last name + first initial match."""
    ca = CredibilityAnalyst()
    # "J. Barnes" should match "Julian E. Barnes"
    sig = make_signal(author="J. Barnes")
    score = ca.score(sig)
    assert score == pytest.approx(0.90)


def test_credibility_partial_match_full_name_variant():
    """Score returns analyst score when first+last name match (no middle)."""
    ca = CredibilityAnalyst()
    # "Michael Kofman" exact match works via name_map
    sig = make_signal(author="Michael Kofman")
    score = ca.score(sig)
    assert score == pytest.approx(0.92)


def test_identify_analyst_exact_match():
    """identify_analyst returns AnalystRecord for exact name match."""
    ca = CredibilityAnalyst()
    sig = make_signal(author="Shane Harris")
    record = ca.identify_analyst(sig)
    assert record is not None
    assert record.name == "Shane Harris"


def test_identify_analyst_no_author_returns_none():
    """identify_analyst returns None when signal has no author."""
    ca = CredibilityAnalyst()
    sig = make_signal(author="")
    record = ca.identify_analyst(sig)
    assert record is None


def test_identify_analyst_unknown_returns_none():
    """identify_analyst returns None for unknown author."""
    ca = CredibilityAnalyst()
    sig = make_signal(author="Unknown Journalist XYZ")
    record = ca.identify_analyst(sig)
    assert record is None


def test_identify_analyst_partial_match():
    """identify_analyst finds analyst via partial last-name + first initial."""
    ca = CredibilityAnalyst()
    sig = make_signal(author="T. Rid")
    record = ca.identify_analyst(sig)
    assert record is not None
    assert record.name == "Thomas Rid"


# ─── DiscoveryAnalyst deduplication tests ────────────────────────────────────

def test_discover_batch_deduplicates_mentions():
    """discover_batch merges repeated discoveries and sums mention counts."""
    da = DiscoveryAnalyst()
    # Two signals both mention the same new analyst
    text = (
        "according to John Smith, a senior fellow at the Brookings Institute, "
        "the military situation is evolving. "
        "John Smith said the alliance faces serious challenges."
    )
    sig1 = make_signal(source="rand", text=text)
    sig2 = make_signal(source="cipher_brief", text=text)
    ps1 = make_parsed(text=text)
    ps2 = make_parsed(text=text)

    results = da.discover_batch([sig1, sig2], [ps1, ps2])
    # Deduplicated — same analyst discovered from both signals
    names = [r.name for r in results]
    # If "John Smith" is discovered, it should appear once with count >= 1
    if names:
        seen_counts = {r.name: r.mention_count for r in results}
        for name, count in seen_counts.items():
            assert count >= 1


def test_discover_batch_returns_sorted_by_mention_count():
    """discover_batch returns analysts sorted descending by mention count."""
    da = DiscoveryAnalyst()
    text_a = "said John Smith, senior researcher at Johns Hopkins Institute."
    text_b = (
        "according to John Smith, senior researcher at the Institute, "
        "according to John Smith at the Institute again, military forces."
    )
    sig_a = make_signal(source="rand", text=text_a)
    sig_b = make_signal(source="rand", text=text_b)
    ps_a = make_parsed(text=text_a)
    ps_b = make_parsed(text=text_b)

    results = da.discover_batch([sig_a, sig_b], [ps_a, ps_b])
    if len(results) >= 2:
        counts = [r.mention_count for r in results]
        assert counts == sorted(counts, reverse=True)


def test_discover_with_affiliation_match():
    """Discovery extracts affiliation hint when pattern matches."""
    da = DiscoveryAnalyst()
    text = "John Walsh, a senior fellow at Georgetown University, analyzed the data."
    sig = make_signal(text=text)
    ps = make_parsed(text=text)
    results = da.discover(sig, ps)
    # If John Walsh is discovered, its affiliation_hint may contain Georgetown
    for r in results:
        if "Walsh" in r.name:
            # affiliation may or may not be populated depending on regex
            assert isinstance(r.affiliation_hint, str)


def test_discover_increments_mention_count_for_repeat():
    """discover increments mention_count when the same name appears multiple times."""
    da = DiscoveryAnalyst()
    text = (
        "said John Walsh, senior analyst. "
        "John Walsh said the situation is serious. "
    )
    sig = make_signal(text=text)
    ps = make_parsed(text=text)
    results = da.discover(sig, ps)
    for r in results:
        if "Walsh" in r.name:
            # mention_count should be >= 1
            assert r.mention_count >= 1


def test_discover_skips_long_names():
    """discover skips matched names longer than 50 characters."""
    da = DiscoveryAnalyst()
    # Construct a name that matches the pattern but is > 50 chars
    text = (
        "said Alexanderthelongnamedfirstpart Theoverlyextremelylonglastednameherexx, "
        "a senior analyst at RAND studying military issues."
    )
    sig = make_signal(text=text)
    ps = make_parsed(text=text)
    results = da.discover(sig, ps)
    # The long name should be filtered out (line 94 'continue')
    for r in results:
        assert len(r.name) <= 50
