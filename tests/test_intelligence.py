"""
Tests for IntelligenceStore, IntelligenceAnalyzer, and InvestigationGenerator.
"""

import pytest
from spec1_engine.core import ids
from spec1_engine.schemas.models import (
    IntelligenceRecord,
    Investigation,
    Opportunity,
    Outcome,
    Signal,
    OUTCOME_CLASSES,
)
from spec1_engine.intelligence.store import IntelligenceStore
from spec1_engine.intelligence.analyzer import IntelligenceAnalyzer
from spec1_engine.investigation.generator import InvestigationGenerator


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _make_signal(
    source="war_on_the_rocks",
    source_type="publication",
    velocity=0.80,
    engagement=0.70,
    domains=None,
) -> Signal:
    return Signal(
        signal_id=ids.signal_id(source, "test signal text for unit testing"),
        source=source,
        source_type=source_type,
        text="Test signal text for unit testing purposes.",
        velocity=velocity,
        engagement=engagement,
        run_id="osint:test-run",
        environment="osint",
        metadata={"domains": domains if domains is not None else ["geopolitics", "defense"]},
    )


def _make_opportunity(signal: Signal) -> Opportunity:
    return Opportunity(
        opportunity_id=ids.opportunity_id(signal.signal_id),
        signal_id=signal.signal_id,
        score=0.80,
        priority="ELEVATED",
        rationale="Test opportunity",
        run_id=signal.run_id,
        environment=signal.environment,
    )


def _make_outcome(signal: Signal, opportunity: Opportunity, classification="Investigate") -> Outcome:
    inv_id = ids.investigation_id(opportunity.opportunity_id)
    return Outcome(
        outcome_id=ids.outcome_id(inv_id),
        investigation_id=inv_id,
        opportunity_id=opportunity.opportunity_id,
        signal_id=signal.signal_id,
        classification=classification,
        confidence=0.75,
        run_id=signal.run_id,
        environment=signal.environment,
    )


def _make_record(signal: Signal, outcome: Outcome, classification="Investigate") -> IntelligenceRecord:
    return IntelligenceRecord(
        record_id=ids.intelligence_id(signal.signal_id, classification),
        outcome_id=outcome.outcome_id,
        signal_id=signal.signal_id,
        signal_text=signal.text,
        pattern="Test pattern",
        classification=classification,
        confidence=0.75,
        source_weight=0.60,
        analyst_weight=0.50,
        run_id=signal.run_id,
        environment=signal.environment,
        metadata={"source": signal.source, "domains": ["geopolitics"]},
    )


# ── IntelligenceStore ─────────────────────────────────────────────────────────

class TestIntelligenceStore:
    def test_save_and_get(self):
        store = IntelligenceStore()
        sig = _make_signal()
        opp = _make_opportunity(sig)
        out = _make_outcome(sig, opp)
        rec = _make_record(sig, out)
        store.save(rec)
        assert store.get(rec.record_id) is rec

    def test_append_only_no_overwrite(self):
        store = IntelligenceStore()
        sig = _make_signal()
        opp = _make_opportunity(sig)
        out = _make_outcome(sig, opp)
        rec = _make_record(sig, out)
        store.save(rec)
        original = store.get(rec.record_id)

        # Save again with same ID — should not overwrite
        store.save(rec)
        assert store.get(rec.record_id) is original

    def test_all_returns_all_records(self):
        store = IntelligenceStore()
        sig1 = _make_signal(source="war_on_the_rocks")
        sig2 = _make_signal(source="cipher_brief")
        for sig in (sig1, sig2):
            opp = _make_opportunity(sig)
            out = _make_outcome(sig, opp)
            rec = _make_record(sig, out)
            store.save(rec)
        assert len(store.all()) == 2

    def test_len(self):
        store = IntelligenceStore()
        sig = _make_signal()
        opp = _make_opportunity(sig)
        out = _make_outcome(sig, opp)
        rec = _make_record(sig, out)
        assert len(store) == 0
        store.save(rec)
        assert len(store) == 1

    def test_by_classification(self):
        store = IntelligenceStore()
        for i, cls in enumerate(("Investigate", "Monitor", "Investigate")):
            sig = _make_signal(source=f"src_cls_test_{i}")
            opp = _make_opportunity(sig)
            out = _make_outcome(sig, opp, classification=cls)
            rec = _make_record(sig, out, classification=cls)
            store.save(rec)
        investigate = store.by_classification("Investigate")
        assert len(investigate) == 2
        for r in investigate:
            assert r.classification == "Investigate"

    def test_by_source(self):
        store = IntelligenceStore()
        sig = _make_signal(source="rand")
        opp = _make_opportunity(sig)
        out = _make_outcome(sig, opp)
        rec = _make_record(sig, out)
        rec.metadata["source"] = "rand"
        store.save(rec)
        results = store.by_source("rand")
        assert len(results) == 1
        assert results[0].metadata["source"] == "rand"

    def test_by_domain(self):
        store = IntelligenceStore()
        sig = _make_signal(domains=["cyber", "defense"])
        opp = _make_opportunity(sig)
        out = _make_outcome(sig, opp)
        rec = _make_record(sig, out)
        rec.metadata["domains"] = ["cyber", "defense"]
        store.save(rec)
        assert len(store.by_domain("cyber")) == 1
        assert len(store.by_domain("geopolitics")) == 0

    def test_high_confidence(self):
        store = IntelligenceStore()
        for conf, cls in ((0.90, "Corroborated"), (0.50, "Monitor")):
            sig = _make_signal(source=f"src_{conf}")
            opp = _make_opportunity(sig)
            out = _make_outcome(sig, opp, classification=cls)
            rec = IntelligenceRecord(
                record_id=ids.intelligence_id(sig.signal_id, cls),
                outcome_id=out.outcome_id,
                signal_id=sig.signal_id,
                signal_text=sig.text,
                pattern="pattern",
                classification=cls,
                confidence=conf,
                source_weight=0.5,
                analyst_weight=0.5,
                run_id=sig.run_id,
                environment=sig.environment,
            )
            store.save(rec)
        high = store.high_confidence(threshold=0.70)
        assert len(high) == 1
        assert high[0].confidence >= 0.70

    def test_summary(self):
        store = IntelligenceStore()
        for i, cls in enumerate(("Investigate", "Investigate", "Monitor")):
            sig = _make_signal(source=f"s_summary_test_{i}")
            opp = _make_opportunity(sig)
            out = _make_outcome(sig, opp, classification=cls)
            rec = _make_record(sig, out, classification=cls)
            store.save(rec)
        summary = store.summary()
        assert summary["Investigate"] == 2
        assert summary["Monitor"] == 1

    def test_get_missing_returns_none(self):
        store = IntelligenceStore()
        assert store.get("nonexistent_id") is None


# ── IntelligenceAnalyzer ──────────────────────────────────────────────────────

class TestIntelligenceAnalyzer:
    def test_analyze_returns_record(self):
        analyzer = IntelligenceAnalyzer()
        sig = _make_signal()
        opp = _make_opportunity(sig)
        out = _make_outcome(sig, opp, classification="Corroborated")
        rec = analyzer.analyze(out, sig)
        assert isinstance(rec, IntelligenceRecord)
        assert rec.record_id.startswith("intel_")

    def test_analyze_carries_run_id(self):
        analyzer = IntelligenceAnalyzer()
        sig = _make_signal()
        opp = _make_opportunity(sig)
        out = _make_outcome(sig, opp)
        rec = analyzer.analyze(out, sig)
        assert rec.run_id == sig.run_id

    def test_source_weight_increases_on_corroborated(self):
        analyzer = IntelligenceAnalyzer()
        sig = _make_signal()
        opp = _make_opportunity(sig)
        out = _make_outcome(sig, opp, classification="Corroborated")
        rec = analyzer.analyze(out, sig)
        assert rec.source_weight > 0.5

    def test_source_weight_decreases_on_conflicted(self):
        analyzer = IntelligenceAnalyzer()
        sig = _make_signal()
        opp = _make_opportunity(sig)
        out = _make_outcome(sig, opp, classification="Conflicted")
        rec = analyzer.analyze(out, sig)
        assert rec.source_weight < 0.5

    def test_source_weight_bounded(self):
        analyzer = IntelligenceAnalyzer()
        sig = _make_signal()
        opp = _make_opportunity(sig)
        for cls in OUTCOME_CLASSES:
            out = _make_outcome(sig, opp, classification=cls)
            rec = analyzer.analyze(out, sig)
            assert 0.0 <= rec.source_weight <= 1.0

    def test_analyst_weight_increases_on_escalate(self):
        analyzer = IntelligenceAnalyzer()
        sig = _make_signal()
        opp = _make_opportunity(sig)
        out = _make_outcome(sig, opp, classification="Escalate")
        out.analyst_citations = ["julian_barnes"]
        rec = analyzer.analyze(out, sig)
        assert rec.analyst_weight > 0.5

    def test_analyst_weight_default_when_no_citations(self):
        analyzer = IntelligenceAnalyzer()
        sig = _make_signal()
        opp = _make_opportunity(sig)
        out = _make_outcome(sig, opp)
        out.analyst_citations = []
        rec = analyzer.analyze(out, sig)
        assert rec.analyst_weight == 0.5

    def test_pattern_contains_source_and_classification(self):
        analyzer = IntelligenceAnalyzer()
        sig = _make_signal(source="rand", source_type="think_tank")
        opp = _make_opportunity(sig)
        out = _make_outcome(sig, opp, classification="Monitor")
        rec = analyzer.analyze(out, sig)
        assert "rand" in rec.pattern
        assert "Monitor" in rec.pattern

    def test_metadata_records_source(self):
        analyzer = IntelligenceAnalyzer()
        sig = _make_signal(source="lawfare")
        opp = _make_opportunity(sig)
        out = _make_outcome(sig, opp)
        rec = analyzer.analyze(out, sig)
        assert rec.metadata["source"] == "lawfare"


# ── InvestigationGenerator ────────────────────────────────────────────────────

class TestInvestigationGenerator:
    def test_generate_returns_investigation(self):
        gen = InvestigationGenerator()
        sig = _make_signal()
        opp = _make_opportunity(sig)
        inv = gen.generate(opp, sig)
        assert isinstance(inv, Investigation)
        assert inv.investigation_id.startswith("inv_")

    def test_generate_links_ids(self):
        gen = InvestigationGenerator()
        sig = _make_signal()
        opp = _make_opportunity(sig)
        inv = gen.generate(opp, sig)
        assert inv.opportunity_id == opp.opportunity_id
        assert inv.signal_id == sig.signal_id

    def test_generate_carries_run_id(self):
        gen = InvestigationGenerator()
        sig = _make_signal()
        opp = _make_opportunity(sig)
        inv = gen.generate(opp, sig)
        assert inv.run_id == sig.run_id

    def test_queries_are_non_empty(self):
        gen = InvestigationGenerator()
        sig = _make_signal()
        opp = _make_opportunity(sig)
        inv = gen.generate(opp, sig)
        assert len(inv.queries) == 4
        for q in inv.queries:
            assert isinstance(q, str) and len(q) > 0

    def test_hypothesis_mentions_source(self):
        gen = InvestigationGenerator()
        sig = _make_signal(source="cipher_brief")
        opp = _make_opportunity(sig)
        inv = gen.generate(opp, sig)
        assert "cipher_brief" in inv.hypothesis

    def test_select_sources_returns_known_sources(self):
        gen = InvestigationGenerator()
        sig = _make_signal(domains=["geopolitics", "defense"])
        opp = _make_opportunity(sig)
        inv = gen.generate(opp, sig)
        assert len(inv.sources_to_check) > 0
        # All returned sources should be strings
        for s in inv.sources_to_check:
            assert isinstance(s, str)

    def test_select_sources_fallback_when_no_domain_match(self):
        gen = InvestigationGenerator()
        sig = _make_signal(domains=[])
        opp = _make_opportunity(sig)
        inv = gen.generate(opp, sig)
        # Default fallback sources when no domain match
        assert inv.sources_to_check == ["rand", "csis", "atlantic_council"]

    def test_analyst_leads_match_domain(self):
        gen = InvestigationGenerator()
        sig = _make_signal(domains=["cyber"])
        opp = _make_opportunity(sig)
        inv = gen.generate(opp, sig)
        # Should find analysts who cover cyber
        assert len(inv.analyst_leads) > 0

    def test_analyst_leads_capped_at_three(self):
        gen = InvestigationGenerator()
        sig = _make_signal(domains=["geopolitics", "defense", "intelligence", "cyber"])
        opp = _make_opportunity(sig)
        inv = gen.generate(opp, sig)
        assert len(inv.analyst_leads) <= 3
