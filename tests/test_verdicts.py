"""Tests for cls_verdicts (schema + store) and the /verdicts API surface."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from cls_db.database import Database
from cls_db.migrate import ensure_schema
from cls_db.repository import Repository
from cls_verdicts.schemas import VALID_VERDICTS, Verdict
from cls_verdicts.store import VerdictStore
from spec1_api.dependencies import get_verdict_store
from spec1_api.main import app


# ── schema ─────────────────────────────────────────────────────────────────


def test_valid_verdict_kinds_are_accepted():
    for kind in VALID_VERDICTS:
        v = Verdict(verdict_id="v1", record_id="r1", verdict=kind)  # type: ignore[arg-type]
        assert v.verdict == kind


def test_invalid_verdict_kind_raises():
    with pytest.raises(ValueError, match="verdict must be one of"):
        Verdict(verdict_id="v1", record_id="r1", verdict="maybe")  # type: ignore[arg-type]


def test_make_id_is_stable_for_same_inputs():
    ts = datetime(2026, 4, 25, 12, 0, 0, tzinfo=timezone.utc)
    a = Verdict.make_id("rec1", "alice", ts)
    b = Verdict.make_id("rec1", "alice", ts)
    assert a == b
    assert a.startswith("verdict_")


def test_make_id_differs_when_inputs_differ():
    ts = datetime(2026, 4, 25, 12, 0, 0, tzinfo=timezone.utc)
    assert Verdict.make_id("rec1", "alice", ts) != Verdict.make_id("rec2", "alice", ts)
    assert Verdict.make_id("rec1", "alice", ts) != Verdict.make_id("rec1", "bob", ts)


def test_to_dict_serializes_datetime():
    v = Verdict(
        verdict_id="v1",
        record_id="r1",
        verdict="correct",
        reviewer="alice",
        reviewed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        notes="agrees with prior reporting",
    )
    d = v.to_dict()
    assert d["reviewed_at"] == "2026-01-01T00:00:00+00:00"
    assert d["verdict"] == "correct"
    assert d["notes"] == "agrees with prior reporting"


# ── store ──────────────────────────────────────────────────────────────────


def test_store_saves_and_reads_back(tmp_path: Path):
    store = VerdictStore(tmp_path / "verdicts.jsonl")
    v = Verdict(
        verdict_id=Verdict.make_id("rec1", "alice", datetime.now(timezone.utc)),
        record_id="rec1",
        verdict="correct",
        reviewer="alice",
    )
    entry = store.save(v)
    assert entry["record_id"] == "rec1"
    assert "written_at" in entry

    rows = list(store.read_all())
    assert len(rows) == 1
    assert rows[0]["verdict_id"] == v.verdict_id


def test_store_appends_multiple_verdicts_for_same_record(tmp_path: Path):
    store = VerdictStore(tmp_path / "verdicts.jsonl")
    base = datetime(2026, 4, 25, tzinfo=timezone.utc)
    for i, kind in enumerate(["correct", "partial", "incorrect"]):
        ts = base + timedelta(hours=i)
        store.save(Verdict(
            verdict_id=Verdict.make_id("rec1", f"reviewer{i}", ts),
            record_id="rec1",
            verdict=kind,  # type: ignore[arg-type]
            reviewer=f"reviewer{i}",
            reviewed_at=ts,
        ))
    assert store.count() == 3
    assert len(store.for_record("rec1")) == 3
    assert store.for_record("rec_other") == []


def test_store_skips_malformed_lines(tmp_path: Path):
    p = tmp_path / "verdicts.jsonl"
    p.write_text(
        '{"verdict_id":"v1","record_id":"r1","verdict":"correct"}\n'
        "not valid json\n"
        '{"verdict_id":"v2","record_id":"r2","verdict":"incorrect"}\n',
        encoding="utf-8",
    )
    store = VerdictStore(p)
    rows = list(store.read_all())
    assert [r["verdict_id"] for r in rows] == ["v1", "v2"]


# ── dual-write (cls_db integration) ────────────────────────────────────────


def test_dual_write_creates_verdicts_table_and_index(tmp_path: Path):
    db = Database(tmp_path / "spec1.db")
    ensure_schema(db)
    assert db.table_exists("verdicts")
    # Index is created idempotently in AUX_DDL — rerunning ensure_schema must not error.
    ensure_schema(db)
    assert db.table_exists("verdicts")


def test_dual_write_persists_to_both_jsonl_and_sqlite(tmp_path: Path):
    db = Database(tmp_path / "spec1.db")
    ensure_schema(db)
    store = VerdictStore(tmp_path / "verdicts.jsonl", db=db)
    v = Verdict(
        verdict_id="v_dual",
        record_id="rec1",
        verdict="correct",
        reviewer="alice",
    )
    store.save(v)

    # JSONL has it
    jsonl_rows = list(store.read_all())
    assert len(jsonl_rows) == 1
    assert jsonl_rows[0]["verdict_id"] == "v_dual"

    # SQLite has it too
    repo = Repository(db, "verdicts", pk_field="verdict_id")
    db_rows = repo.all()
    assert len(db_rows) == 1
    assert db_rows[0]["verdict_id"] == "v_dual"
    assert db_rows[0]["record_id"] == "rec1"
    assert db_rows[0]["verdict"] == "correct"


def test_dual_write_jsonl_only_when_no_db(tmp_path: Path):
    """A VerdictStore with no db must not try to import or call cls_db."""
    store = VerdictStore(tmp_path / "verdicts.jsonl")  # no db
    store.save(Verdict(verdict_id="v_solo", record_id="rec1", verdict="correct"))
    rows = list(store.read_all())
    assert len(rows) == 1
    # No SQLite file should have been created
    assert not (tmp_path / "spec1.db").exists()


def test_dual_write_handles_repeat_id_via_replace(tmp_path: Path):
    """Repository inserts use INSERT OR REPLACE; same verdict_id twice must not error."""
    db = Database(tmp_path / "spec1.db")
    ensure_schema(db)
    store = VerdictStore(tmp_path / "verdicts.jsonl", db=db)
    v1 = Verdict(verdict_id="v_same", record_id="rec1", verdict="correct", notes="first")
    v2 = Verdict(verdict_id="v_same", record_id="rec1", verdict="incorrect", notes="changed mind")
    store.save(v1)
    store.save(v2)

    # JSONL keeps both (append-only is the contract)
    rows = list(store.read_all())
    assert len(rows) == 2
    # SQLite keeps the latest (replace semantics)
    repo = Repository(db, "verdicts", pk_field="verdict_id")
    db_rows = repo.all()
    assert len(db_rows) == 1
    assert db_rows[0]["notes"] == "changed mind"


# ── API ────────────────────────────────────────────────────────────────────


@pytest.fixture
def client(tmp_path: Path):
    """TestClient with an isolated VerdictStore pointed at tmp_path."""
    store = VerdictStore(tmp_path / "verdicts.jsonl")
    app.dependency_overrides[get_verdict_store] = lambda: store
    try:
        yield TestClient(app), store
    finally:
        app.dependency_overrides.pop(get_verdict_store, None)


def test_post_verdict_writes_to_store(client):
    c, store = client
    r = c.post("/verdicts", json={
        "record_id": "rec1",
        "verdict": "correct",
        "reviewer": "alice",
        "notes": "matches independent reporting",
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["record_id"] == "rec1"
    assert body["verdict"] == "correct"
    assert body["verdict_id"].startswith("verdict_")
    assert store.count() == 1


def test_post_verdict_rejects_invalid_kind(client):
    c, _ = client
    r = c.post("/verdicts", json={"record_id": "rec1", "verdict": "maybe"})
    assert r.status_code == 422


def test_get_verdicts_filters_by_record_and_reviewer(client):
    c, _ = client
    c.post("/verdicts", json={"record_id": "rec1", "verdict": "correct", "reviewer": "alice"})
    c.post("/verdicts", json={"record_id": "rec1", "verdict": "incorrect", "reviewer": "bob"})
    c.post("/verdicts", json={"record_id": "rec2", "verdict": "partial", "reviewer": "alice"})

    all_resp = c.get("/verdicts").json()
    assert all_resp["total"] == 3

    rec1 = c.get("/verdicts", params={"record_id": "rec1"}).json()
    assert rec1["total"] == 2
    assert all(v["record_id"] == "rec1" for v in rec1["items"])

    alice = c.get("/verdicts", params={"reviewer": "alice"}).json()
    assert alice["total"] == 2
    assert all(v["reviewer"] == "alice" for v in alice["items"])

    correct = c.get("/verdicts", params={"verdict": "correct"}).json()
    assert correct["total"] == 1
    assert correct["items"][0]["reviewer"] == "alice"


def test_get_verdicts_for_record_endpoint(client):
    c, _ = client
    c.post("/verdicts", json={"record_id": "rec1", "verdict": "correct", "reviewer": "alice"})
    c.post("/verdicts", json={"record_id": "rec1", "verdict": "partial", "reviewer": "bob"})

    r = c.get("/verdicts/rec1").json()
    assert r["record_id"] == "rec1"
    assert r["total"] == 2

    empty = c.get("/verdicts/missing").json()
    assert empty["total"] == 0


def test_pagination(client):
    c, _ = client
    for i in range(5):
        c.post("/verdicts", json={"record_id": f"r{i}", "verdict": "correct"})
    page = c.get("/verdicts", params={"limit": 2, "offset": 1}).json()
    assert page["total"] == 5
    assert len(page["items"]) == 2
    assert page["offset"] == 1
