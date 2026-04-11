"""Tests for intelligence/store.py — JSONL persistence."""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path

import pytest

from spec1_engine.intelligence.store import JsonlStore


# ─── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def tmp_store(tmp_path: Path) -> JsonlStore:
    return JsonlStore(tmp_path / "test.jsonl")


@pytest.fixture
def sample_record() -> dict:
    return {
        "record_id": "rec-abc123",
        "pattern": "test pattern",
        "classification": "Monitor",
        "confidence": 0.72,
        "source_weight": 0.85,
        "analyst_weight": 0.80,
    }


# ─── Basic write / read ───────────────────────────────────────────────────────

def test_append_returns_dict_with_written_at(tmp_store, sample_record):
    result = tmp_store.append(sample_record)
    assert isinstance(result, dict)
    assert "written_at" in result


def test_append_preserves_all_fields(tmp_store, sample_record):
    result = tmp_store.append(sample_record)
    for key, val in sample_record.items():
        assert result[key] == val


def test_file_created_after_append(tmp_store, sample_record):
    assert not tmp_store.path.exists()
    tmp_store.append(sample_record)
    assert tmp_store.path.exists()


def test_read_all_returns_written_record(tmp_store, sample_record):
    tmp_store.append(sample_record)
    records = list(tmp_store.read_all())
    assert len(records) == 1
    assert records[0]["record_id"] == "rec-abc123"


def test_append_multiple_records(tmp_store, sample_record):
    for i in range(5):
        r = {**sample_record, "record_id": f"rec-{i:04d}"}
        tmp_store.append(r)
    records = list(tmp_store.read_all())
    assert len(records) == 5


def test_append_is_truly_append_not_overwrite(tmp_store, sample_record):
    tmp_store.append({**sample_record, "record_id": "first"})
    tmp_store.append({**sample_record, "record_id": "second"})
    records = list(tmp_store.read_all())
    ids = [r["record_id"] for r in records]
    assert "first" in ids
    assert "second" in ids


def test_count_returns_correct_number(tmp_store, sample_record):
    for i in range(7):
        tmp_store.append({**sample_record, "record_id": f"r{i}"})
    assert tmp_store.count() == 7


def test_count_empty_store(tmp_store):
    assert tmp_store.count() == 0


def test_exists_false_before_write(tmp_store):
    assert tmp_store.exists() is False


def test_exists_true_after_write(tmp_store, sample_record):
    tmp_store.append(sample_record)
    assert tmp_store.exists() is True


# ─── Batch operations ────────────────────────────────────────────────────────

def test_append_batch_returns_all_records(tmp_store, sample_record):
    batch = [{**sample_record, "record_id": f"b{i}"} for i in range(3)]
    results = tmp_store.append_batch(batch)
    assert len(results) == 3


def test_append_batch_empty_returns_empty(tmp_store):
    assert tmp_store.append_batch([]) == []


def test_append_batch_all_have_written_at(tmp_store, sample_record):
    batch = [{**sample_record, "record_id": f"b{i}"} for i in range(4)]
    results = tmp_store.append_batch(batch)
    for r in results:
        assert "written_at" in r


def test_append_batch_persisted_correctly(tmp_store, sample_record):
    batch = [{**sample_record, "record_id": f"batch-{i}"} for i in range(5)]
    tmp_store.append_batch(batch)
    records = list(tmp_store.read_all())
    assert len(records) == 5
    ids = {r["record_id"] for r in records}
    assert ids == {f"batch-{i}" for i in range(5)}


# ─── Type validation ─────────────────────────────────────────────────────────

def test_append_raises_on_non_dict(tmp_store):
    with pytest.raises(TypeError):
        tmp_store.append("not a dict")


def test_append_raises_on_list(tmp_store):
    with pytest.raises(TypeError):
        tmp_store.append(["a", "b"])


def test_append_batch_raises_on_non_dict_in_list(tmp_store):
    with pytest.raises(TypeError):
        tmp_store.append_batch([{"ok": True}, "bad"])


# ─── Filter ──────────────────────────────────────────────────────────────────

def test_filter_by_returns_matching(tmp_store, sample_record):
    tmp_store.append({**sample_record, "classification": "Escalate", "record_id": "r1"})
    tmp_store.append({**sample_record, "classification": "Monitor", "record_id": "r2"})
    tmp_store.append({**sample_record, "classification": "Escalate", "record_id": "r3"})
    matches = list(tmp_store.filter_by("classification", "Escalate"))
    assert len(matches) == 2
    assert all(r["classification"] == "Escalate" for r in matches)


def test_filter_by_no_match_returns_empty(tmp_store, sample_record):
    tmp_store.append(sample_record)
    matches = list(tmp_store.filter_by("classification", "NonExistent"))
    assert matches == []


# ─── Clear ───────────────────────────────────────────────────────────────────

def test_clear_removes_file(tmp_store, sample_record):
    tmp_store.append(sample_record)
    assert tmp_store.exists()
    tmp_store.clear()
    assert not tmp_store.path.exists()


def test_clear_nonexistent_is_safe(tmp_store):
    tmp_store.clear()  # Should not raise


# ─── Threading safety ────────────────────────────────────────────────────────

def test_threading_no_data_loss(tmp_path):
    store = JsonlStore(tmp_path / "threaded.jsonl")
    errors = []
    total = 50

    def writer(thread_id: int):
        for i in range(10):
            try:
                store.append({"thread": thread_id, "i": i, "val": f"t{thread_id}-i{i}"})
            except Exception as exc:
                errors.append(str(exc))

    threads = [threading.Thread(target=writer, args=(t,)) for t in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == [], f"Threading errors: {errors}"
    count = store.count()
    assert count == total, f"Expected {total} records, got {count}"


def test_threading_each_line_valid_json(tmp_path):
    store = JsonlStore(tmp_path / "json_check.jsonl")

    def writer():
        for i in range(20):
            store.append({"x": i, "data": "a" * 100})

    threads = [threading.Thread(target=writer) for _ in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    with store.path.open("r") as fh:
        for line in fh:
            line = line.strip()
            if line:
                parsed = json.loads(line)  # Should not raise
                assert "written_at" in parsed


# ─── JSONL format ────────────────────────────────────────────────────────────

def test_each_line_is_valid_json(tmp_store, sample_record):
    for i in range(5):
        tmp_store.append({**sample_record, "i": i})
    with tmp_store.path.open("r") as fh:
        for line in fh:
            line = line.strip()
            if line:
                obj = json.loads(line)
                assert isinstance(obj, dict)


def test_read_all_on_nonexistent_file_returns_empty(tmp_path):
    store = JsonlStore(tmp_path / "ghost.jsonl")
    records = list(store.read_all())
    assert records == []


def test_parent_dir_created_if_missing(tmp_path):
    deep = tmp_path / "deep" / "nested" / "store.jsonl"
    store = JsonlStore(deep)
    store.append({"hello": "world"})
    assert deep.exists()


def test_multiple_stores_independent(tmp_path):
    s1 = JsonlStore(tmp_path / "s1.jsonl")
    s2 = JsonlStore(tmp_path / "s2.jsonl")
    s1.append({"store": "one"})
    s2.append({"store": "two"})
    s2.append({"store": "two-b"})
    assert s1.count() == 1
    assert s2.count() == 2


def test_written_at_is_iso_format(tmp_store, sample_record):
    from datetime import datetime
    result = tmp_store.append(sample_record)
    # Should parse without error
    dt = datetime.fromisoformat(result["written_at"].replace("Z", "+00:00"))
    assert dt is not None
