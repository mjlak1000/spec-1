"""Signal-to-case matching for investigation workspace."""

from __future__ import annotations

from spec1_engine.schemas.models import Signal
from spec1_engine.core import logging_utils
from spec1_engine.workspace.case import list_cases

logger = logging_utils.get_logger(__name__)


def match_signals_to_cases(signals: list[Signal]) -> dict[str, list[Signal]]:
    """
    Match signals to open cases based on case tags.
    A signal matches if any tag appears in signal text, source, or metadata.

    Args:
        signals: List of Signal objects from this cycle

    Returns:
        Dict mapping case_id -> list of matched signals
    """
    matches: dict[str, list[Signal]] = {}

    # Load all open and watching cases
    open_cases = list_cases(status="OPEN")
    watching_cases = list_cases(status="WATCHING")
    cases = open_cases + watching_cases

    if not cases:
        return matches

    # For each case, find matching signals
    for case in cases:
        matches[case.case_id] = []

        for signal in signals:
            # Check if any case tag appears in signal content
            if _signal_matches_case(signal, case.tags):
                matches[case.case_id].append(signal)
                logger.info(f"signal_matched_case: signal_id={signal.signal_id}, case_id={case.case_id}, source={signal.source}")

    return matches


def _signal_matches_case(signal: Signal, tags: list[str]) -> bool:
    """
    Check if signal matches any case tags (case-insensitive).

    Args:
        signal: Signal object
        tags: List of case tags

    Returns:
        True if any tag matches
    """
    # Combine searchable fields
    searchable = [
        signal.text.lower() if signal.text else "",
        signal.source.lower() if signal.source else "",
        signal.author.lower() if signal.author else "",
    ]

    # Add metadata values
    if signal.metadata:
        for v in signal.metadata.values():
            if isinstance(v, str):
                searchable.append(v.lower())

    # Search for tags
    for tag in tags:
        tag_lower = tag.lower()
        for field in searchable:
            if tag_lower in field:
                return True

    return False
