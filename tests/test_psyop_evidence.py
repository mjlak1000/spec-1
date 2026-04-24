"""Tests for cls_psyop evidence chain system."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cls_psyop.evidence import EvidenceChain, EvidenceStore
from spec1_engine.cls_psyop.scorer import (
    NARRATIVE_CLUSTER,
    CONSENSUS_SPIKE,
    score_psyop,
    _detect_narrative_cluster,
    _detect_consensus_spike,
)


# ─── Fixtures ────────────────────────────────────────────────────────────────

def _make_signals_data(n: int, single_source: bool = False) -> list[dict]:
    return [
        {
            "signal_id": f"sig-{i:03d}",
            "source": "source_a" if single_source else f"source_{chr(ord('a') + i % 5)}",
            "text": f"Iran nuclear risk assessment article number {i} — analysis of proliferation threat",
            "url": f"https://example.com/article-{i}",
            "published_at": "2026-04-18T06:00:00+00:00",
        }
        for i in range(n)
    ]


def _make_psyop_signal(
    n_sources: int = 4,
    velocity: float = 0.3,
    single_source: bool = False,
) -> dict:
    signals_data = _make_signals_data(n_sources, single_source=single_source)
    sources = list({s["source"] for s in signals_data})
    return {
        "topic": "iran_nuclear",
        "entities": ["Iran", "IAEA"],
        "sources": sources,
        "fara_matches": [],
        "legislation_matches": [],
        "narrative_markets": sources,
        "consensus_velocity": velocity,
        "origin_traceable": True,
        "signals_data": signals_data,
    }


# ─── EvidenceChain dataclass ─────────────────────────────────────────────────

class TestEvidenceChain:
    def test_to_dict_has_all_fields(self):
        ec = EvidenceChain(
            pattern_name=NARRATIVE_CLUSTER,
            confidence=0.72,
            supporting_signals=["sig-001", "sig-002"],
            raw_excerpts=[{"signal_id": "sig-001", "source": "reuters", "text_snippet": "Iran nuclear", "url": "https://x.com"}],
            source_metadata=[{"source": "reuters", "credibility_score": 0.7, "signal_count": 1, "first_seen": "", "last_seen": ""}],
            cross_references=[],
            summary="3 sources published Iran nuclear risk assessments — pattern: NARRATIVE_CLUSTER, confidence: 0.72",
        )
        d = ec.to_dict()
        assert d["pattern_name"] == NARRATIVE_CLUSTER
        assert d["confidence"] == 0.72
        assert "supporting_signals" in d
        assert "raw_excerpts" in d
        assert "source_metadata" in d
        assert "cross_references" in d
        assert "summary" in d
        assert "created_at" in d

    def test_summary_sentence_format(self):
        ec = EvidenceChain(
            pattern_name=CONSENSUS_SPIKE,
            confidence=0.8,
            supporting_signals=[],
            raw_excerpts=[],
            source_metadata=[],
            cross_references=[],
            summary="5 outlets published on 'iran_nuclear' with velocity 0.80 — pattern: CONSENSUS_SPIKE, confidence: 0.80",
        )
        assert "CONSENSUS_SPIKE" in ec.summary
        assert "confidence" in ec.summary


# ─── NARRATIVE_CLUSTER detection ─────────────────────────────────────────────

class TestNarrativeCluster:
    def test_fires_when_3_plus_sources(self):
        sig = _make_psyop_signal(n_sources=6)
        chain = _detect_narrative_cluster(sig)
        assert chain is not None
        assert chain.pattern_name == NARRATIVE_CLUSTER

    def test_does_not_fire_below_threshold(self):
        sig = _make_psyop_signal(n_sources=1, single_source=True)
        # Only 1 source
        sig["sources"] = ["source_a"]
        chain = _detect_narrative_cluster(sig)
        assert chain is None

    def test_raw_excerpts_truncated_to_280_chars(self):
        long_text = "X" * 500
        sig = _make_psyop_signal(n_sources=4)
        # Override text with long content
        for s in sig["signals_data"]:
            s["text"] = long_text
        chain = _detect_narrative_cluster(sig)
        assert chain is not None
        for excerpt in chain.raw_excerpts:
            assert len(excerpt["text_snippet"]) <= 280

    def test_raw_excerpts_include_required_keys(self):
        sig = _make_psyop_signal(n_sources=4)
        chain = _detect_narrative_cluster(sig)
        assert chain is not None
        for excerpt in chain.raw_excerpts:
            assert "signal_id" in excerpt
            assert "source" in excerpt
            assert "text_snippet" in excerpt
            assert "url" in excerpt

    def test_cross_references_populated_for_multi_signal_source(self):
        """When a source has 2+ signals, those signal_ids appear in cross_references."""
        # 4 signals but only 2 unique sources → each source has 2 signals
        sig = _make_psyop_signal(n_sources=4, single_source=False)
        # Force two sources each with 2 signals
        sig["signals_data"][0]["source"] = "reuters"
        sig["signals_data"][1]["source"] = "reuters"
        sig["signals_data"][2]["source"] = "ap"
        sig["signals_data"][3]["source"] = "ap"
        sig["sources"] = ["reuters", "ap", "bbc"]  # 3 sources → threshold met
        chain = _detect_narrative_cluster(sig)
        assert chain is not None
        assert len(chain.cross_references) >= 2

    def test_summary_contains_pattern_name_and_confidence(self):
        sig = _make_psyop_signal(n_sources=5)
        chain = _detect_narrative_cluster(sig)
        assert chain is not None
        assert NARRATIVE_CLUSTER in chain.summary
        assert "confidence" in chain.summary


# ─── CONSENSUS_SPIKE detection ───────────────────────────────────────────────

class TestConsensusSpike:
    def test_fires_on_high_velocity(self):
        sig = _make_psyop_signal(velocity=0.8)
        chain = _detect_consensus_spike(sig)
        assert chain is not None
        assert chain.pattern_name == CONSENSUS_SPIKE

    def test_does_not_fire_on_low_velocity(self):
        sig = _make_psyop_signal(velocity=0.2)
        chain = _detect_consensus_spike(sig)
        assert chain is None

    def test_confidence_equals_velocity(self):
        sig = _make_psyop_signal(velocity=0.75)
        chain = _detect_consensus_spike(sig)
        assert chain is not None
        assert chain.confidence == 0.75

    def test_summary_contains_spike_and_velocity(self):
        sig = _make_psyop_signal(velocity=0.9)
        chain = _detect_consensus_spike(sig)
        assert chain is not None
        assert CONSENSUS_SPIKE in chain.summary


# ─── score_psyop integration ─────────────────────────────────────────────────

class TestScorePsyop:
    def test_both_patterns_fire(self, tmp_path):
        sig = _make_psyop_signal(n_sources=5, velocity=0.8)
        result = score_psyop(sig, run_id="run-test", evidence_store_path=tmp_path / "ev.jsonl")
        assert NARRATIVE_CLUSTER in result["patterns_fired"]
        assert CONSENSUS_SPIKE in result["patterns_fired"]

    def test_no_patterns_clean(self, tmp_path):
        sig = _make_psyop_signal(n_sources=1, velocity=0.1, single_source=True)
        sig["sources"] = ["one_source"]
        result = score_psyop(sig, run_id="r", evidence_store_path=tmp_path / "ev.jsonl")
        assert result["patterns_fired"] == []
        assert result["classification"] == "CLEAN"

    def test_evidence_chains_in_result(self, tmp_path):
        sig = _make_psyop_signal(n_sources=5, velocity=0.8)
        result = score_psyop(sig, run_id="r", evidence_store_path=tmp_path / "ev.jsonl")
        assert "evidence_chains" in result
        assert len(result["evidence_chains"]) >= 1

    def test_evidence_written_to_jsonl(self, tmp_path):
        store_path = tmp_path / "spec1_psyop_evidence.jsonl"
        sig = _make_psyop_signal(n_sources=5, velocity=0.8)
        score_psyop(sig, run_id="run-ev-001", evidence_store_path=store_path)

        assert store_path.exists()
        lines = [l for l in store_path.read_text().splitlines() if l.strip()]
        assert len(lines) >= 1
        entry = json.loads(lines[0])
        assert "pattern_name" in entry
        assert entry["run_id"] == "run-ev-001"

    def test_evidence_jsonl_is_valid_json_append_only(self, tmp_path):
        store_path = tmp_path / "spec1_psyop_evidence.jsonl"
        sig = _make_psyop_signal(n_sources=5, velocity=0.8)

        # Run twice — should append, not overwrite
        score_psyop(sig, run_id="run-1", evidence_store_path=store_path)
        score_psyop(sig, run_id="run-2", evidence_store_path=store_path)

        lines = [l for l in store_path.read_text().splitlines() if l.strip()]
        assert len(lines) >= 2
        for line in lines:
            obj = json.loads(line)
            assert isinstance(obj, dict)

    def test_cross_references_across_chains(self, tmp_path):
        """signal_ids appearing in multiple chains are cross-referenced."""
        sig = _make_psyop_signal(n_sources=5, velocity=0.8)
        result = score_psyop(sig, run_id="r", evidence_store_path=tmp_path / "ev.jsonl")
        chains = result["evidence_chains"]
        if len(chains) >= 2:
            # At least one chain should have cross_references populated
            all_xrefs = [c["cross_references"] for c in chains]
            assert any(len(x) > 0 for x in all_xrefs)

    def test_summary_sentence_format(self, tmp_path):
        sig = _make_psyop_signal(n_sources=5, velocity=0.8)
        result = score_psyop(sig, run_id="r", evidence_store_path=tmp_path / "ev.jsonl")
        for chain in result["evidence_chains"]:
            assert "pattern:" in chain["summary"]
            assert "confidence:" in chain["summary"]


# ─── EvidenceStore ───────────────────────────────────────────────────────────

class TestEvidenceStore:
    def _make_chain(self, pattern: str = NARRATIVE_CLUSTER) -> EvidenceChain:
        return EvidenceChain(
            pattern_name=pattern,
            confidence=0.5,
            supporting_signals=["sig-001"],
            raw_excerpts=[],
            source_metadata=[],
            cross_references=[],
            summary="Test summary — pattern: {}, confidence: 0.50".format(pattern),
        )

    def test_append_creates_file(self, tmp_path):
        store = EvidenceStore(tmp_path / "ev.jsonl")
        store.append(self._make_chain(), run_id="r1")
        assert (tmp_path / "ev.jsonl").exists()

    def test_append_batch_writes_all(self, tmp_path):
        store = EvidenceStore(tmp_path / "ev.jsonl")
        chains = [self._make_chain(NARRATIVE_CLUSTER), self._make_chain(CONSENSUS_SPIKE)]
        store.append_batch(chains, run_id="r1")
        assert store.count() == 2

    def test_read_all_returns_dicts(self, tmp_path):
        store = EvidenceStore(tmp_path / "ev.jsonl")
        store.append(self._make_chain(), run_id="r1")
        records = list(store.read_all())
        assert len(records) == 1
        assert isinstance(records[0], dict)
        assert records[0]["run_id"] == "r1"

    def test_append_is_cumulative(self, tmp_path):
        store = EvidenceStore(tmp_path / "ev.jsonl")
        store.append(self._make_chain(), run_id="r1")
        store.append(self._make_chain(), run_id="r2")
        assert store.count() == 2
