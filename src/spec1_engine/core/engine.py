"""
SPEC-1 — core/engine.py

The loop orchestrator. Runs one full OSINT cycle:
Signal → Opportunity → Investigation → Outcome → Intelligence

The engine is domain-agnostic. It wires the modules together
and carries the run_id through every step for full traceability.
"""

from __future__ import annotations

import os
import traceback
from dataclasses import dataclass
from typing import List, Optional

from spec1_engine.core import ids, logging_utils
from spec1_engine.schemas.models import (
    IntelligenceRecord,
    Investigation,
    Opportunity,
    Outcome,
    Signal,
)

logger = logging_utils.get_logger(__name__)


@dataclass
class CycleResult:
    """The complete output of one engine cycle."""
    run_id:           str
    signal:           Signal
    opportunity:      Optional[Opportunity]
    investigation:    Optional[Investigation]
    outcome:          Optional[Outcome]
    intelligence:     Optional[IntelligenceRecord]
    status:           str           # ok | filtered | failed | halted
    notes:            str = ""


class OSINTEngine:
    """
    Orchestrates one full OSINT learning cycle.

    Usage:
        from spec1_engine.core.engine import OSINTEngine
        engine = OSINTEngine()
        result = engine.run_cycle(signal)
    """

    def __init__(self, environment: str = "osint") -> None:
        self.environment = environment
        self._run_id = ids.run_id(environment)

        # Import here to keep the engine thin and testable
        from spec1_engine.signal.scorer import SignalScorer
        from spec1_engine.investigation.generator import InvestigationGenerator
        from spec1_engine.investigation.verifier import Verifier
        from spec1_engine.intelligence.analyzer import IntelligenceAnalyzer
        from spec1_engine.intelligence.store import IntelligenceStore

        self._scorer     = SignalScorer()
        self._generator  = InvestigationGenerator()
        self._verifier   = Verifier()
        self._analyzer   = IntelligenceAnalyzer()
        self._store      = IntelligenceStore()

    @property
    def run_id(self) -> str:
        return self._run_id

    def _kill_switch_active(self) -> bool:
        return os.path.exists(".cls_kill")

    def run_cycle(self, signal: Signal) -> CycleResult:
        """Run one complete cycle for a single signal."""
        if self._kill_switch_active():
            logging_utils.log_event(
                logger, "kill_switch_halt",
                run_id=self._run_id,
                signal_id=signal.signal_id,
            )
            return CycleResult(
                run_id=self._run_id,
                signal=signal,
                opportunity=None,
                investigation=None,
                outcome=None,
                intelligence=None,
                status="halted",
                notes="Kill switch active (.cls_kill present). Halting.",
            )

        signal.run_id = self._run_id
        signal.environment = self.environment

        logging_utils.log_event(
            logger, "cycle_start",
            run_id=self._run_id,
            signal_id=signal.signal_id,
            source=signal.source,
        )

        # ── Step 1: Score signal into opportunity ────────────────────────────
        opportunity = self._scorer.score(signal)
        if opportunity is None:
            logging_utils.log_event(
                logger, "signal_filtered",
                run_id=self._run_id,
                signal_id=signal.signal_id,
            )
            return CycleResult(
                run_id=self._run_id,
                signal=signal,
                opportunity=None,
                investigation=None,
                outcome=None,
                intelligence=None,
                status="filtered",
                notes="Signal did not pass gate validation.",
            )

        logging_utils.log_event(
            logger, "opportunity_scored",
            run_id=self._run_id,
            opportunity_id=opportunity.opportunity_id,
            score=opportunity.score,
            priority=opportunity.priority,
        )

        # ── Step 2: Generate investigation ───────────────────────────────────
        investigation = self._generator.generate(opportunity, signal)

        logging_utils.log_event(
            logger, "investigation_generated",
            run_id=self._run_id,
            investigation_id=investigation.investigation_id,
            queries=len(investigation.queries),
        )

        # ── Step 3: Verify ────────────────────────────────────────────────────
        outcome = self._verifier.verify(investigation, signal)

        logging_utils.log_event(
            logger, "outcome_classified",
            run_id=self._run_id,
            outcome_id=outcome.outcome_id,
            classification=outcome.classification,
            confidence=outcome.confidence,
        )

        # ── Step 4: Extract intelligence ─────────────────────────────────────
        record = self._analyzer.analyze(outcome, signal)
        self._store.save(record)

        logging_utils.log_event(
            logger, "intelligence_stored",
            run_id=self._run_id,
            record_id=record.record_id,
            pattern=record.pattern,
            source_weight=record.source_weight,
        )

        logging_utils.log_event(
            logger, "cycle_complete",
            run_id=self._run_id,
            signal_id=signal.signal_id,
            status="ok",
        )

        return CycleResult(
            run_id=self._run_id,
            signal=signal,
            opportunity=opportunity,
            investigation=investigation,
            outcome=outcome,
            intelligence=record,
            status="ok",
        )

    def run_batch(self, signals: List[Signal]) -> List[CycleResult]:
        """Run cycles for a list of signals. Continues on individual failures."""
        results = []
        for signal in signals:
            if self._kill_switch_active():
                logging_utils.log_event(
                    logger, "kill_switch_halt",
                    run_id=self._run_id,
                )
                break
            try:
                results.append(self.run_cycle(signal))
            except Exception as exc:
                logging_utils.log_event(
                    logger, "cycle_error",
                    run_id=self._run_id,
                    signal_id=signal.signal_id,
                    error=str(exc),
                    traceback=traceback.format_exc(),
                    level="ERROR",
                )
                results.append(CycleResult(
                    run_id=self._run_id,
                    signal=signal,
                    opportunity=None,
                    investigation=None,
                    outcome=None,
                    intelligence=None,
                    status="failed",
                    notes=f"Cycle failed: {exc}",
                ))
        return results
