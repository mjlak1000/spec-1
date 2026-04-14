"""
SPEC-1 — analysts/discovery.py

Discovers new analyst candidates from signal text and metadata.
The system surfaces new voices worth tracking.

v0.1: keyword-based stub.
v1.0: NER extraction, citation graph analysis, Claude API.
"""

from __future__ import annotations

import re
from typing import List

from spec1_engine.schemas.models import Signal


# Known analyst name fragments for basic detection
_KNOWN_NAME_FRAGMENTS = [
    "barnes", "dilanian", "bertrand", "harris",
    "kofman", "massicot", "rid", "haring", "o'brien",
]

# Affiliation keywords that suggest an analyst worth tracking
_AFFILIATION_SIGNALS = [
    "former", "retired", "colonel", "general", "admiral",
    "director", "deputy", "analyst", "fellow", "researcher",
    "csis", "rand", "atlantic council", "cfr", "brookings",
    "pentagon", "cia", "nsa", "dia", "state department",
]


class AnalystDiscovery:
    """
    Extracts potential new analyst candidates from signal text.
    Returns candidate names/affiliations for human review.
    """

    def discover(self, signal: Signal) -> List[dict]:
        """
        Scan signal text for new analyst candidates.
        Returns a list of candidate dicts for review.
        """
        candidates = []
        text_lower = signal.text.lower()

        # Check for known name fragments (basic detection)
        for fragment in _KNOWN_NAME_FRAGMENTS:
            if fragment in text_lower:
                candidates.append({
                    "name_fragment":  fragment,
                    "source":         signal.source,
                    "signal_id":      signal.signal_id,
                    "discovery_type": "known_fragment",
                    "needs_review":   False,
                })

        # Check for affiliation signals (suggests new analyst)
        for affil in _AFFILIATION_SIGNALS:
            if affil in text_lower:
                # Extract a short window around the affiliation signal
                idx = text_lower.find(affil)
                window = signal.text[max(0, idx-60):idx+80]
                candidates.append({
                    "name_fragment":  affil,
                    "context":        window.strip(),
                    "source":         signal.source,
                    "signal_id":      signal.signal_id,
                    "discovery_type": "affiliation_signal",
                    "needs_review":   True,
                })

        return candidates
