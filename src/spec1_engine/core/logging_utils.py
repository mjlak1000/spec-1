"""
SPEC-1 — core/logging_utils.py

Structured logging for the OSINT loop.
Every log entry carries run_id and cycle context for full traceability.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime
from typing import Any, Dict, Optional


def get_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(_StructuredFormatter())
        logger.addHandler(handler)
    logger.setLevel(level)
    return logger


def log_event(
    logger: logging.Logger,
    event: str,
    run_id: str = "",
    level: str = "INFO",
    **kwargs: Any,
) -> None:
    """Emit a structured log event with consistent fields."""
    record: Dict[str, Any] = {
        "ts":     datetime.utcnow().isoformat(),
        "event":  event,
        "run_id": run_id,
    }
    record.update(kwargs)
    getattr(logger, level.lower(), logger.info)(json.dumps(record))


class _StructuredFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        try:
            return record.getMessage()
        except Exception:
            return super().format(record)
