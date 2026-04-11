"""Credibility Analyst.

Scores signals based on known-analyst authorship.
"""

from __future__ import annotations

import re
from typing import Optional

from spec1_engine.analysts.registry import load_all, get_credibility
from spec1_engine.schemas.models import AnalystRecord, Signal, ParsedSignal


class CredibilityAnalyst:
    """Scores signals by checking if author is a known high-credibility analyst."""

    def __init__(self) -> None:
        self._analysts: list[AnalystRecord] = load_all()
        self._name_map: dict[str, AnalystRecord] = {
            a.name.lower(): a for a in self._analysts
        }

    def score(self, signal: Signal) -> float:
        """Return credibility score for signal based on its author field.

        Returns analyst credibility if author is known, else default 0.50.
        """
        if not signal.author:
            return 0.50

        author_lower = signal.author.lower().strip()

        # Exact match
        if author_lower in self._name_map:
            return self._name_map[author_lower].credibility_score

        # Partial match (e.g. "By Julian E. Barnes" or "Julian Barnes")
        for name_lower, record in self._name_map.items():
            parts = name_lower.split()
            if len(parts) >= 2:
                # Check if last name matches and first initial or name matches
                last_name = parts[-1]
                if last_name in author_lower:
                    # Also verify first name / initial
                    first = parts[0]
                    if first in author_lower or (len(first) > 0 and first[0] in author_lower):
                        return record.credibility_score

        return 0.50

    def identify_analyst(self, signal: Signal) -> Optional[AnalystRecord]:
        """Return the AnalystRecord if the author is a known analyst, else None."""
        if not signal.author:
            return None

        author_lower = signal.author.lower().strip()
        if author_lower in self._name_map:
            return self._name_map[author_lower]

        for name_lower, record in self._name_map.items():
            parts = name_lower.split()
            if len(parts) >= 2:
                last_name = parts[-1]
                if last_name in author_lower:
                    first = parts[0]
                    if first in author_lower or (len(first) > 0 and first[0] in author_lower):
                        return record

        return None

    def score_batch(self, signals: list[Signal]) -> list[float]:
        """Score a batch of signals."""
        return [self.score(s) for s in signals]

    def get_known_analysts(self) -> list[AnalystRecord]:
        """Return all known analysts."""
        return list(self._analysts)

    def count_known(self) -> int:
        """Return number of known analysts in registry."""
        return len(self._analysts)
