"""PostgreSQL persistence store for SPEC-1 intelligence records.

Uses SQLAlchemy Core so it works with both PostgreSQL (production) and
SQLite (testing).  Active only when DATABASE_URL is set in the environment;
all public functions silently no-op when no URL is configured.

Schema
------
Table ``intelligence_records`` — append-only; rows are never updated or deleted.
One row per ``IntelligenceRecord`` written by the engine.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    MetaData,
    String,
    Table,
    Text,
    create_engine,
    text,
)
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

_metadata = MetaData()

intelligence_records = Table(
    "intelligence_records",
    _metadata,
    Column("record_id", String(64), primary_key=True),
    Column("run_id", String(64), index=True, nullable=True),
    Column("signal_id", String(64), index=True, nullable=True),
    Column("signal_source", String(128), nullable=True),
    Column("signal_url", Text, nullable=True),
    Column("pattern", Text, nullable=True),
    Column("classification", String(64), nullable=True),
    Column("outcome_classification", String(64), nullable=True),
    Column("confidence", Float, nullable=True),
    Column("outcome_confidence", Float, nullable=True),
    Column("source_weight", Float, nullable=True),
    Column("analyst_weight", Float, nullable=True),
    Column("opportunity_id", String(64), nullable=True),
    Column("opportunity_score", Float, nullable=True),
    Column("opportunity_priority", String(32), nullable=True),
    Column("investigation_id", String(64), nullable=True),
    Column("hypothesis", Text, nullable=True),
    Column("environment", String(64), nullable=True),
    Column("written_at", DateTime(timezone=True), nullable=True),
)

_engine: Optional[Engine] = None


def _get_engine(url: Optional[str] = None) -> Optional[Engine]:
    """Return (and cache) the SQLAlchemy engine, or None if no URL configured."""
    global _engine
    database_url = url or os.environ.get("DATABASE_URL")
    if not database_url:
        return None
    if _engine is None or (url and str(_engine.url) != url):
        try:
            _engine = create_engine(database_url, pool_pre_ping=True)
        except Exception as exc:
            logger.error("Failed to create database engine: %s", exc)
            return None
    return _engine


def init_db(url: Optional[str] = None) -> bool:
    """Create tables if they do not already exist.

    Returns True on success, False if no DATABASE_URL configured or on error.
    """
    engine = _get_engine(url)
    if engine is None:
        return False
    try:
        _metadata.create_all(engine)
        logger.info("PostgreSQL tables initialised (or already exist)")
        return True
    except Exception as exc:
        logger.error("Failed to initialise database tables: %s", exc)
        return False


def append(record: dict, url: Optional[str] = None) -> bool:
    """Insert a single intelligence record into the database.

    Returns True on success, False if no DATABASE_URL configured or on error.
    Silently skips when the database is not configured so callers never need
    to check whether PostgreSQL is active.
    """
    engine = _get_engine(url)
    if engine is None:
        return False

    # Ensure tables exist (idempotent)
    try:
        _metadata.create_all(engine)
    except Exception as exc:
        logger.error("create_all failed: %s", exc)
        return False

    row = _build_row(record)
    try:
        with engine.begin() as conn:
            conn.execute(intelligence_records.insert().values(**row))
        return True
    except Exception as exc:
        # Silently skip duplicate primary-key violations (idempotent writes)
        exc_str = str(exc).lower()
        if "unique" in exc_str or "duplicate" in exc_str or "primary key" in exc_str:
            return True
        logger.error("PostgreSQL append failed: %s", exc)
        return False


def append_batch(records: list[dict], url: Optional[str] = None) -> int:
    """Insert multiple intelligence records.  Returns count of rows inserted."""
    if not records:
        return 0
    engine = _get_engine(url)
    if engine is None:
        return 0

    try:
        _metadata.create_all(engine)
    except Exception as exc:
        logger.error("create_all failed: %s", exc)
        return 0

    inserted = 0
    for record in records:
        if append(record, url=url):
            inserted += 1
    return inserted


def query_latest(limit: int = 20, url: Optional[str] = None) -> list[dict]:
    """Return the most recent *limit* records ordered by written_at descending."""
    engine = _get_engine(url)
    if engine is None:
        return []
    try:
        with engine.connect() as conn:
            result = conn.execute(
                intelligence_records.select()
                .order_by(intelligence_records.c.written_at.desc())
                .limit(limit)
            )
            return [dict(row._mapping) for row in result]
    except Exception as exc:
        logger.error("query_latest failed: %s", exc)
        return []


def count(url: Optional[str] = None) -> int:
    """Return total row count, or 0 if database not configured."""
    engine = _get_engine(url)
    if engine is None:
        return 0
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM intelligence_records"))
            return result.scalar() or 0
    except Exception as exc:
        logger.error("count failed: %s", exc)
        return 0


def is_configured(url: Optional[str] = None) -> bool:
    """Return True if a DATABASE_URL is set and the engine can connect."""
    engine = _get_engine(url)
    if engine is None:
        return False
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def reset_engine() -> None:
    """Reset the cached engine (for testing)."""
    global _engine
    _engine = None


# ── helpers ───────────────────────────────────────────────────────────────────

def _build_row(record: dict) -> dict:
    """Normalise a record dict into the columns expected by the table."""
    return {
        "record_id": str(record.get("record_id", "")),
        "run_id": record.get("run_id"),
        "signal_id": record.get("signal_id"),
        "signal_source": record.get("signal_source") or record.get("source"),
        "signal_url": record.get("signal_url") or record.get("url"),
        "pattern": record.get("pattern"),
        "classification": record.get("classification"),
        "outcome_classification": record.get("outcome_classification"),
        "confidence": _to_float(record.get("confidence")),
        "outcome_confidence": _to_float(record.get("outcome_confidence")),
        "source_weight": _to_float(record.get("source_weight")),
        "analyst_weight": _to_float(record.get("analyst_weight")),
        "opportunity_id": record.get("opportunity_id"),
        "opportunity_score": _to_float(record.get("opportunity_score")),
        "opportunity_priority": record.get("opportunity_priority"),
        "investigation_id": record.get("investigation_id"),
        "hypothesis": record.get("hypothesis"),
        "environment": record.get("environment"),
        "written_at": datetime.now(timezone.utc),
    }


def _to_float(val: object) -> Optional[float]:
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None
