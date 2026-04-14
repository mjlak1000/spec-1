"""SPEC-1 Engine — orchestrates the full signal pipeline."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from spec1_engine.core.ids import run_id as new_run_id
from spec1_engine.core.logging_utils import get_logger
from spec1_engine.schemas.models import (
    IntelligenceRecord,
    Investigation,
    Opportunity,
    Outcome,
    ParsedSignal,
    Signal,
)
from spec1_engine.signal.harvester import harvest_all
from spec1_engine.signal.parser import parse_signal
from spec1_engine.signal.scorer import score_signal
from spec1_engine.investigation.generator import generate_investigation
from spec1_engine.investigation.verifier import verify_investigation
from spec1_engine.intelligence.analyzer import analyze
from spec1_engine.intelligence.store import JsonlStore
import spec1_engine.persistence.postgres as pg_store

logger = get_logger(__name__)


@dataclass
class EngineConfig:
    """Configuration for the SPEC-1 engine."""

    run_id: str = field(default_factory=new_run_id)
    environment: str = "production"
    store_path: Path = field(default_factory=lambda: Path("spec1_intelligence.jsonl"))
    feed_timeout: int = 15
    max_signals: Optional[int] = None


@dataclass
class RunStats:
    """Statistics for a single engine run."""

    run_id: str
    started_at: str
    signals_harvested: int = 0
    signals_parsed: int = 0
    opportunities_found: int = 0
    investigations_generated: int = 0
    outcomes_verified: int = 0
    records_stored: int = 0
    errors: list[str] = field(default_factory=list)
    finished_at: Optional[str] = None

    def finish(self) -> None:
        self.finished_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "signals_harvested": self.signals_harvested,
            "signals_parsed": self.signals_parsed,
            "opportunities_found": self.opportunities_found,
            "investigations_generated": self.investigations_generated,
            "outcomes_verified": self.outcomes_verified,
            "records_stored": self.records_stored,
            "errors": self.errors,
        }


class Engine:
    """SPEC-1 Intelligence Engine."""

    def __init__(self, config: Optional[EngineConfig] = None) -> None:
        self.config = config or EngineConfig()
        self.store = JsonlStore(self.config.store_path)
        logger.info("Engine initialised run_id=%s", self.config.run_id)

    def run(self) -> RunStats:
        """Execute the full pipeline and return run statistics."""
        stats = RunStats(
            run_id=self.config.run_id,
            started_at=datetime.now(timezone.utc).isoformat(),
        )

        # 1. Harvest
        logger.info("Harvesting RSS signals...")
        try:
            result = harvest_all(
                run_id=self.config.run_id,
                environment=self.config.environment,
                timeout=self.config.feed_timeout,
            )
            signals: list[Signal] = result["signals"]
            if self.config.max_signals:
                signals = signals[: self.config.max_signals]
            stats.signals_harvested = len(signals)
            for src, err in result.get("errors", {}).items():
                stats.errors.append(f"harvest:{src}:{err}")
            logger.info("Harvested %d signals", stats.signals_harvested)
        except Exception as exc:
            stats.errors.append(f"harvest_all:{exc}")
            stats.finish()
            return stats

        # 2. Parse
        parsed_signals: list[ParsedSignal] = []
        for sig in signals:
            try:
                ps = parse_signal(sig)
                parsed_signals.append(ps)
            except Exception as exc:
                stats.errors.append(f"parse:{sig.signal_id}:{exc}")
        stats.signals_parsed = len(parsed_signals)
        logger.info("Parsed %d signals", stats.signals_parsed)

        # 3. Score — 4 gates
        opportunities: list[tuple[Signal, ParsedSignal, Opportunity]] = []
        for sig, ps in zip(signals, parsed_signals):
            try:
                opp = score_signal(sig, ps, run_id=self.config.run_id)
                if opp is not None:
                    opportunities.append((sig, ps, opp))
            except Exception as exc:
                stats.errors.append(f"score:{sig.signal_id}:{exc}")
        stats.opportunities_found = len(opportunities)
        logger.info("Scored: %d opportunities", stats.opportunities_found)

        # 4. Investigate → Verify → Analyze → Store
        for sig, ps, opp in opportunities:
            try:
                inv = generate_investigation(opp, sig, ps)
                stats.investigations_generated += 1

                outcome = verify_investigation(inv)
                stats.outcomes_verified += 1

                record = analyze(opp, inv, outcome, sig)
                record_dict = record.to_dict()
                self.store.append(record_dict)
                pg_store.append(record_dict)
                stats.records_stored += 1
            except Exception as exc:
                stats.errors.append(f"pipeline:{opp.opportunity_id}:{exc}")

        stats.finish()
        logger.info(
            "Run complete: %d records stored, %d errors",
            stats.records_stored,
            len(stats.errors),
        )
        return stats
