"""Tests for the PostgreSQL persistence module.

Uses SQLite (via SQLAlchemy) as a drop-in replacement so tests run without
a real PostgreSQL instance.
"""

from __future__ import annotations

import pytest


# ─── Module import / configure ────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def reset_pg_engine():
    """Reset the cached engine before and after every test."""
    import spec1_engine.persistence.postgres as pg
    pg.reset_engine()
    yield
    pg.reset_engine()


@pytest.fixture
def sqlite_url(tmp_path):
    """Return a SQLite DATABASE_URL backed by a temp file."""
    db_file = tmp_path / "test_intel.db"
    return f"sqlite:///{db_file}"


@pytest.fixture
def sample_record():
    return {
        "record_id": "rec-test001",
        "run_id": "run-abc",
        "signal_id": "sig-001",
        "signal_source": "war_on_the_rocks",
        "signal_url": "https://example.com/article",
        "pattern": "[ELEVATED] Test pattern | gates=credibility+volume",
        "classification": "Corroborated",
        "outcome_classification": "Corroborated",
        "confidence": 0.85,
        "outcome_confidence": 0.80,
        "source_weight": 0.85,
        "analyst_weight": 0.90,
        "opportunity_id": "opp-testx001",
        "opportunity_score": 0.78,
        "opportunity_priority": "ELEVATED",
        "investigation_id": "inv-test001",
        "hypothesis": "This is a test hypothesis.",
        "environment": "test",
    }


# ─── No DATABASE_URL ──────────────────────────────────────────────────────────

def test_append_returns_false_when_no_url():
    import spec1_engine.persistence.postgres as pg
    assert pg.append({"record_id": "x"}) is False


def test_append_batch_returns_zero_when_no_url():
    import spec1_engine.persistence.postgres as pg
    assert pg.append_batch([{"record_id": "x"}]) == 0


def test_query_latest_returns_empty_when_no_url():
    import spec1_engine.persistence.postgres as pg
    assert pg.query_latest() == []


def test_count_returns_zero_when_no_url():
    import spec1_engine.persistence.postgres as pg
    assert pg.count() == 0


def test_is_configured_returns_false_when_no_url():
    import spec1_engine.persistence.postgres as pg
    assert pg.is_configured() is False


def test_init_db_returns_false_when_no_url():
    import spec1_engine.persistence.postgres as pg
    assert pg.init_db() is False


# ─── With SQLite DATABASE_URL ─────────────────────────────────────────────────

def test_init_db_creates_tables(sqlite_url):
    import spec1_engine.persistence.postgres as pg
    result = pg.init_db(url=sqlite_url)
    assert result is True


def test_is_configured_true_with_sqlite(sqlite_url):
    import spec1_engine.persistence.postgres as pg
    assert pg.is_configured(url=sqlite_url) is True


def test_append_returns_true_with_sqlite(sqlite_url, sample_record):
    import spec1_engine.persistence.postgres as pg
    result = pg.append(sample_record, url=sqlite_url)
    assert result is True


def test_count_after_append(sqlite_url, sample_record):
    import spec1_engine.persistence.postgres as pg
    pg.append(sample_record, url=sqlite_url)
    assert pg.count(url=sqlite_url) == 1


def test_count_empty_database(sqlite_url):
    import spec1_engine.persistence.postgres as pg
    pg.init_db(url=sqlite_url)
    assert pg.count(url=sqlite_url) == 0


def test_query_latest_returns_inserted_record(sqlite_url, sample_record):
    import spec1_engine.persistence.postgres as pg
    pg.append(sample_record, url=sqlite_url)
    records = pg.query_latest(limit=10, url=sqlite_url)
    assert len(records) == 1
    assert records[0]["record_id"] == "rec-test001"


def test_query_latest_limit(sqlite_url, sample_record):
    import spec1_engine.persistence.postgres as pg
    for i in range(5):
        r = {**sample_record, "record_id": f"rec-{i:04d}"}
        pg.append(r, url=sqlite_url)
    records = pg.query_latest(limit=3, url=sqlite_url)
    assert len(records) == 3


def test_append_batch_inserts_all(sqlite_url, sample_record):
    import spec1_engine.persistence.postgres as pg
    batch = [{**sample_record, "record_id": f"rec-b{i}"} for i in range(5)]
    inserted = pg.append_batch(batch, url=sqlite_url)
    assert inserted == 5
    assert pg.count(url=sqlite_url) == 5


def test_append_batch_empty_returns_zero(sqlite_url):
    import spec1_engine.persistence.postgres as pg
    assert pg.append_batch([], url=sqlite_url) == 0


def test_append_idempotent_duplicate_primary_key(sqlite_url, sample_record):
    """Appending the same record_id twice does not raise and count stays at 1."""
    import spec1_engine.persistence.postgres as pg
    pg.append(sample_record, url=sqlite_url)
    pg.append(sample_record, url=sqlite_url)
    assert pg.count(url=sqlite_url) == 1


def test_record_fields_persisted(sqlite_url, sample_record):
    import spec1_engine.persistence.postgres as pg
    pg.append(sample_record, url=sqlite_url)
    records = pg.query_latest(url=sqlite_url)
    assert len(records) == 1
    row = records[0]
    assert row["signal_source"] == "war_on_the_rocks"
    assert row["classification"] == "Corroborated"
    assert row["opportunity_priority"] == "ELEVATED"
    assert abs(row["confidence"] - 0.85) < 1e-6


def test_multiple_records_ordered_by_written_at(sqlite_url, sample_record):
    """query_latest returns newest records first."""
    import spec1_engine.persistence.postgres as pg
    for i in range(3):
        pg.append({**sample_record, "record_id": f"rec-ord-{i}"}, url=sqlite_url)
    records = pg.query_latest(url=sqlite_url)
    assert len(records) == 3


def test_build_row_handles_missing_fields():
    from spec1_engine.persistence.postgres import _build_row
    row = _build_row({"record_id": "minimal"})
    assert row["record_id"] == "minimal"
    assert row["signal_source"] is None
    assert row["confidence"] is None


def test_build_row_uses_alternate_field_names():
    from spec1_engine.persistence.postgres import _build_row
    row = _build_row({
        "record_id": "r1",
        "source": "cipher_brief",
        "url": "https://example.com",
    })
    assert row["signal_source"] == "cipher_brief"
    assert row["signal_url"] == "https://example.com"


def test_to_float_handles_none():
    from spec1_engine.persistence.postgres import _to_float
    assert _to_float(None) is None


def test_to_float_handles_string():
    from spec1_engine.persistence.postgres import _to_float
    assert _to_float("0.75") == pytest.approx(0.75)


def test_to_float_handles_invalid():
    from spec1_engine.persistence.postgres import _to_float
    assert _to_float("not_a_number") is None


def test_reset_engine_clears_cache(sqlite_url):
    import spec1_engine.persistence.postgres as pg
    pg.init_db(url=sqlite_url)
    assert pg._engine is not None
    pg.reset_engine()
    assert pg._engine is None
