"""Tests for cls_db — database persistence and dual-write."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cls_db.database import Database
from cls_db.models import ALL_DDL, SIGNALS_DDL, LEADS_DDL
from cls_db.repository import Repository, _serialize, _row_to_dict
from cls_db.migrate import ensure_schema, run_migrations, drop_all, reset_schema
from cls_db.dual_write import DualWriter, make_dual_writer


class TestDatabase:
    def test_creates_db_file(self, tmp_path):
        db = Database(tmp_path / "test.db")
        db.execute("CREATE TABLE IF NOT EXISTS t (id INTEGER PRIMARY KEY)")
        assert (tmp_path / "test.db").exists()

    def test_execute_and_fetchall(self, tmp_path):
        db = Database(tmp_path / "test.db")
        db.execute("CREATE TABLE t (id INTEGER, val TEXT)")
        db.execute("INSERT INTO t VALUES (1, 'hello')")
        rows = db.fetchall("SELECT * FROM t")
        assert len(rows) == 1
        assert rows[0]["val"] == "hello"

    def test_fetchone_returns_dict(self, tmp_path):
        db = Database(tmp_path / "test.db")
        db.execute("CREATE TABLE t (id INTEGER, val TEXT)")
        db.execute("INSERT INTO t VALUES (42, 'world')")
        row = db.fetchone("SELECT * FROM t WHERE id = ?", (42,))
        assert row is not None
        assert row["val"] == "world"

    def test_fetchone_returns_none_for_miss(self, tmp_path):
        db = Database(tmp_path / "test.db")
        db.execute("CREATE TABLE t (id INTEGER, val TEXT)")
        row = db.fetchone("SELECT * FROM t WHERE id = ?", (999,))
        assert row is None

    def test_executemany(self, tmp_path):
        db = Database(tmp_path / "test.db")
        db.execute("CREATE TABLE t (id INTEGER, val TEXT)")
        db.executemany("INSERT INTO t VALUES (?, ?)", [(1, "a"), (2, "b"), (3, "c")])
        rows = db.fetchall("SELECT * FROM t")
        assert len(rows) == 3

    def test_table_exists(self, tmp_path):
        db = Database(tmp_path / "test.db")
        db.execute("CREATE TABLE mytable (id INTEGER)")
        assert db.table_exists("mytable")
        assert not db.table_exists("missing_table")

    def test_close_and_reopen(self, tmp_path):
        db = Database(tmp_path / "test.db")
        db.execute("CREATE TABLE t (id INTEGER)")
        db.execute("INSERT INTO t VALUES (1)")
        db.close()
        # Reopen
        db2 = Database(tmp_path / "test.db")
        rows = db2.fetchall("SELECT * FROM t")
        assert len(rows) == 1


class TestSerialize:
    def test_dict_serialized_to_json(self):
        assert _serialize({"a": 1}) == '{"a": 1}'

    def test_list_serialized_to_json(self):
        assert _serialize([1, 2, 3]) == "[1, 2, 3]"

    def test_string_unchanged(self):
        assert _serialize("hello") == "hello"

    def test_int_unchanged(self):
        assert _serialize(42) == 42


class TestRowToDict:
    def test_deserializes_json_string_dict(self):
        row = {"data": '{"key": "value"}'}
        result = _row_to_dict(row)
        assert result["data"] == {"key": "value"}

    def test_deserializes_json_string_list(self):
        row = {"items": '["a", "b"]'}
        result = _row_to_dict(row)
        assert result["items"] == ["a", "b"]

    def test_leaves_non_json_strings_alone(self):
        row = {"text": "plain string"}
        result = _row_to_dict(row)
        assert result["text"] == "plain string"


class TestMigrations:
    def test_ensure_schema_creates_tables(self, tmp_path):
        db = Database(tmp_path / "test.db")
        created = ensure_schema(db)
        assert "signals" in created
        assert "leads" in created

    def test_ensure_schema_idempotent(self, tmp_path):
        db = Database(tmp_path / "test.db")
        ensure_schema(db)
        # Second call should not raise
        created2 = ensure_schema(db)
        assert created2 == []

    def test_run_migrations_report(self, tmp_path):
        db = Database(tmp_path / "test.db")
        report = run_migrations(db)
        assert "tables_created" in report
        assert "total_tables" in report
        assert report["total_tables"] == len(ALL_DDL)

    def test_drop_all_removes_tables(self, tmp_path):
        db = Database(tmp_path / "test.db")
        ensure_schema(db)
        drop_all(db)
        assert not db.table_exists("signals")
        assert not db.table_exists("leads")

    def test_reset_schema(self, tmp_path):
        db = Database(tmp_path / "test.db")
        ensure_schema(db)
        db.execute("INSERT INTO signals (signal_id, source) VALUES ('s1', 'test')")
        report = reset_schema(db)
        # After reset, table exists but old data is gone
        assert db.table_exists("signals")
        rows = db.fetchall("SELECT * FROM signals")
        assert len(rows) == 0


class TestRepository:
    def setup_method(self):
        """Create a fresh in-memory-like DB for each test."""
        pass

    def test_insert_and_get(self, tmp_path):
        db = Database(tmp_path / "test.db")
        ensure_schema(db)
        repo = Repository(db, "leads", pk_field="lead_id")

        record = {
            "lead_id": "l001",
            "title": "Test Lead",
            "priority": "HIGH",
            "category": "military",
            "confidence": 0.8,
        }
        repo.insert(record)
        result = repo.get("l001")
        assert result is not None
        assert result["lead_id"] == "l001"
        assert result["priority"] == "HIGH"

    def test_insert_batch(self, tmp_path):
        db = Database(tmp_path / "test.db")
        ensure_schema(db)
        repo = Repository(db, "leads", pk_field="lead_id")

        records = [
            {"lead_id": f"l{i:03d}", "title": f"Lead {i}", "priority": "LOW", "category": "cyber"}
            for i in range(5)
        ]
        count = repo.insert_batch(records)
        assert count == 5
        assert repo.count() == 5

    def test_filter_by_field(self, tmp_path):
        db = Database(tmp_path / "test.db")
        ensure_schema(db)
        repo = Repository(db, "leads", pk_field="lead_id")

        repo.insert({"lead_id": "l1", "title": "Lead one", "priority": "HIGH", "category": "cyber"})
        repo.insert({"lead_id": "l2", "title": "Lead two", "priority": "LOW", "category": "military"})

        high = repo.filter("priority", "HIGH")
        assert len(high) == 1
        assert high[0]["lead_id"] == "l1"

    def test_count(self, tmp_path):
        db = Database(tmp_path / "test.db")
        ensure_schema(db)
        repo = Repository(db, "leads", pk_field="lead_id")

        for i in range(3):
            repo.insert({"lead_id": f"l{i}", "title": f"Lead {i}", "priority": "LOW"})

        assert repo.count() == 3

    def test_delete(self, tmp_path):
        db = Database(tmp_path / "test.db")
        ensure_schema(db)
        repo = Repository(db, "leads", pk_field="lead_id")

        repo.insert({"lead_id": "l1", "title": "Lead to delete", "priority": "LOW"})
        repo.delete("l1")
        assert repo.get("l1") is None

    def test_latest(self, tmp_path):
        db = Database(tmp_path / "test.db")
        ensure_schema(db)
        repo = Repository(db, "leads", pk_field="lead_id")

        for i in range(10):
            repo.insert({"lead_id": f"l{i:03d}", "title": f"Lead {i}", "priority": "LOW"})

        latest = repo.latest(3)
        assert len(latest) == 3

    def test_insert_replace_on_pk_conflict(self, tmp_path):
        db = Database(tmp_path / "test.db")
        ensure_schema(db)
        repo = Repository(db, "leads", pk_field="lead_id")

        repo.insert({"lead_id": "l1", "title": "Original"})
        repo.insert({"lead_id": "l1", "title": "Updated"})

        result = repo.get("l1")
        assert result["title"] == "Updated"


class TestDualWriter:
    def test_write_goes_to_both_stores(self, tmp_path):
        jsonl_path = tmp_path / "data.jsonl"
        db_path = tmp_path / "data.db"
        writer = make_dual_writer(
            jsonl_path=jsonl_path,
            db_path=db_path,
            table="leads",
            pk_field="lead_id",
        )
        record = {"lead_id": "l001", "title": "Test Lead", "priority": "HIGH"}
        writer.write(record)

        assert writer.count_jsonl() == 1
        db_records = writer.read_db(limit=10)
        assert len(db_records) == 1

    def test_write_batch(self, tmp_path):
        jsonl_path = tmp_path / "data.jsonl"
        db_path = tmp_path / "data.db"
        writer = make_dual_writer(
            jsonl_path=jsonl_path, db_path=db_path, table="leads", pk_field="lead_id"
        )
        records = [{"lead_id": f"l{i}", "title": f"Lead {i}"} for i in range(5)]
        written = writer.write_batch(records)
        assert len(written) == 5
        assert writer.count_jsonl() == 5

    def test_read_jsonl_returns_records(self, tmp_path):
        jsonl_path = tmp_path / "data.jsonl"
        writer = make_dual_writer(tmp_path / "data.jsonl", tmp_path / "db.db", "leads")
        writer.write({"lead_id": "l1", "title": "Lead 1"})
        jsonl_data = writer.read_jsonl()
        assert len(jsonl_data) == 1
        assert jsonl_data[0]["lead_id"] == "l1"

    def test_sqlite_failure_does_not_break_jsonl(self, tmp_path):
        """JSONL write should succeed even if SQLite insert fails."""
        jsonl_path = tmp_path / "data.jsonl"
        db_path = tmp_path / "data.db"
        writer = make_dual_writer(jsonl_path=jsonl_path, db_path=db_path, table="leads")

        # Write a valid record
        writer.write({"lead_id": "l1", "title": "Test"})

        # Force a bad record with malformed data
        import unittest.mock
        with unittest.mock.patch.object(writer.repo, "insert", side_effect=Exception("DB error")):
            writer.write({"lead_id": "l2", "title": "Test 2"})

        # JSONL should have both records
        assert writer.count_jsonl() == 2
