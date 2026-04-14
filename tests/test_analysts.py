"""
Tests for the analyst registry and credibility engine.
"""

import pytest
from spec1_engine.analysts.registry import AnalystRegistryManager, ANALYST_REGISTRY
from spec1_engine.analysts.credibility import CredibilityEngine
from spec1_engine.analysts.discovery import AnalystDiscovery
from spec1_engine.schemas.models import Signal


# ── Registry ──────────────────────────────────────────────────────────────────

def test_registry_loads_seed_data():
    mgr = AnalystRegistryManager()
    assert len(mgr.all()) == len(ANALYST_REGISTRY)


def test_registry_lookup_by_key():
    mgr = AnalystRegistryManager()
    analyst = mgr.get("julian_barnes")
    assert analyst is not None
    assert analyst.name == "Julian E. Barnes"


def test_registry_lookup_by_domain():
    mgr = AnalystRegistryManager()
    cyber_analysts = mgr.by_domain("cyber")
    assert len(cyber_analysts) > 0
    for a in cyber_analysts:
        assert "cyber" in a.domains


def test_registry_top_by_credibility():
    mgr = AnalystRegistryManager()
    top = mgr.top_by_credibility(n=3)
    assert len(top) == 3
    scores = [a.credibility_score for a in top]
    assert scores == sorted(scores, reverse=True)


# ── Credibility ───────────────────────────────────────────────────────────────

def test_credibility_increases_on_corroborated():
    mgr = AnalystRegistryManager()
    engine = CredibilityEngine(mgr)
    analyst = mgr.get("shane_harris")
    before = analyst.credibility_score
    engine.update_from_outcome(["shane_harris"], "Corroborated")
    assert analyst.credibility_score > before


def test_credibility_decreases_on_conflicted():
    mgr = AnalystRegistryManager()
    engine = CredibilityEngine(mgr)
    analyst = mgr.get("shane_harris")
    before = analyst.credibility_score
    engine.update_from_outcome(["shane_harris"], "Conflicted")
    assert analyst.credibility_score < before


def test_credibility_stays_bounded():
    mgr = AnalystRegistryManager()
    engine = CredibilityEngine(mgr)
    for _ in range(100):
        engine.update_from_outcome(["julian_barnes"], "Corroborated")
    analyst = mgr.get("julian_barnes")
    assert analyst.credibility_score <= 1.0


def test_credibility_report_returns_dict():
    mgr = AnalystRegistryManager()
    engine = CredibilityEngine(mgr)
    report = engine.credibility_report()
    assert isinstance(report, dict)
    assert len(report) > 0


# ── Discovery ─────────────────────────────────────────────────────────────────

def test_discovery_finds_known_analyst():
    disc = AnalystDiscovery()
    signal = Signal(
        signal_id="test_disc_001",
        source="cipher_brief",
        source_type="publication",
        text="According to Julian Barnes at the New York Times, intelligence suggests...",
        velocity=0.7,
        engagement=0.6,
    )
    candidates = disc.discover(signal)
    assert len(candidates) > 0
    names = [c["name_fragment"] for c in candidates]
    assert "barnes" in names


def test_discovery_flags_affiliation_signals():
    disc = AnalystDiscovery()
    signal = Signal(
        signal_id="test_disc_002",
        source="war_on_the_rocks",
        source_type="publication",
        text="A former Pentagon official familiar with the matter said the assessment...",
        velocity=0.8,
        engagement=0.7,
    )
    candidates = disc.discover(signal)
    review_needed = [c for c in candidates if c.get("needs_review")]
    assert len(review_needed) > 0
