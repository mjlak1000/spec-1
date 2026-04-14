"""
SPEC-1 — core/ids.py

Traceable ID generation for every object in the loop.
Every ID carries the run context so records can be linked across the cycle.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import date, datetime


def run_id(environment: str = "osint") -> str:
    """Generate a daily run ID. Same format every day for idempotency checks."""
    return f"{environment}:{date.today().isoformat()}"


def cycle_id() -> str:
    """Generate a unique cycle ID for one full loop execution."""
    return f"cycle:{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}:{_short_uuid()}"


def signal_id(source: str, text: str) -> str:
    """Deterministic signal ID — same source + text always produces same ID."""
    content = f"{source}:{text[:120]}"
    return f"sig_{hashlib.sha256(content.encode()).hexdigest()[:16]}"


def opportunity_id(signal_id: str) -> str:
    return f"opp_{signal_id[4:]}_{_short_uuid()}"


def investigation_id(opportunity_id: str) -> str:
    return f"inv_{opportunity_id[4:20]}_{_short_uuid()}"


def outcome_id(investigation_id: str) -> str:
    return f"out_{investigation_id[4:20]}_{_short_uuid()}"


def intelligence_id(outcome_id: str) -> str:
    return f"intel_{outcome_id[4:20]}_{_short_uuid()}"


def analyst_id(name: str, affiliation: str) -> str:
    content = f"{name.lower().strip()}:{affiliation.lower().strip()}"
    return f"analyst_{hashlib.sha256(content.encode()).hexdigest()[:12]}"


def _short_uuid() -> str:
    return str(uuid.uuid4()).replace("-", "")[:8]
