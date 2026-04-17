"""ID generation utilities."""

from __future__ import annotations

import hashlib
import uuid


def new_uuid() -> str:
    """Generate a new UUID4 string."""
    return str(uuid.uuid4())


def deterministic_id(text: str) -> str:
    """Generate a deterministic 16-char hex ID from text via SHA-256."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def run_id() -> str:
    """Generate a unique run identifier."""
    return f"run-{uuid.uuid4().hex[:12]}"


def signal_id(url: str, title: str) -> str:
    """Generate a deterministic signal ID from URL and title."""
    return deterministic_id(f"{url}::{title}")


def opportunity_id(signal_id: str) -> str:
    """Generate an opportunity ID."""
    return f"opp-{uuid.uuid4().hex[:12]}"


def investigation_id() -> str:
    """Generate an investigation ID."""
    return f"inv-{uuid.uuid4().hex[:12]}"


def outcome_id() -> str:
    """Generate an outcome ID."""
    return f"out-{uuid.uuid4().hex[:12]}"


def record_id() -> str:
    """Generate an intelligence record ID."""
    return f"rec-{uuid.uuid4().hex[:12]}"


def case_id() -> str:
    """Generate a unique case ID for an investigation case file."""
    return f"case-{uuid.uuid4().hex[:12]}"
