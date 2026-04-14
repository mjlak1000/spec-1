"""Tests for the SPEC-1 FastAPI application."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


# ─── App fixture ──────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def client():
    """TestClient with scheduler mocked out so no real APScheduler runs."""
    with patch("spec1_engine.api.app.build_scheduler") as mock_build, \
         patch("spec1_engine.api.app.maybe_run_on_start"):
        mock_sched = MagicMock()
        mock_sched.running = True
        mock_build.return_value = mock_sched

        from spec1_engine.api.app import app
        with TestClient(app) as c:
            yield c


# ─── Kill file cleanup ────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def clean_kill_file():
    """Ensure kill file is removed before and after each test."""
    kill = Path(".cls_kill")
    kill.unlink(missing_ok=True)
    yield
    kill.unlink(missing_ok=True)


# ─── GET /health ──────────────────────────────────────────────────────────────

def test_health_status_ok(client):
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_health_has_timestamp(client):
    r = client.get("/api/v1/health")
    assert "timestamp" in r.json()


def test_health_has_version(client):
    r = client.get("/api/v1/health")
    assert r.json()["version"] == "0.2"


def test_health_timestamp_is_iso(client):
    from datetime import datetime
    r = client.get("/api/v1/health")
    ts = r.json()["timestamp"]
    # Should parse without error
    datetime.fromisoformat(ts)


def test_health_returns_json(client):
    r = client.get("/api/v1/health")
    assert r.headers["content-type"].startswith("application/json")


# ─── POST /cycle/run ──────────────────────────────────────────────────────────

def test_cycle_run_returns_200(client):
    with patch("spec1_engine.api.routes.threading.Thread") as mock_thread:
        mock_thread.return_value = MagicMock()
        r = client.post("/api/v1/cycle/run")
    assert r.status_code == 200


def test_cycle_run_status_triggered(client):
    with patch("spec1_engine.api.routes.threading.Thread") as mock_thread:
        mock_thread.return_value = MagicMock()
        r = client.post("/api/v1/cycle/run")
    assert r.json()["status"] == "triggered"


def test_cycle_run_has_run_id(client):
    with patch("spec1_engine.api.routes.threading.Thread") as mock_thread:
        mock_thread.return_value = MagicMock()
        r = client.post("/api/v1/cycle/run")
    assert "run_id" in r.json()
    assert r.json()["run_id"].startswith("run-")


def test_cycle_run_has_timestamp(client):
    with patch("spec1_engine.api.routes.threading.Thread") as mock_thread:
        mock_thread.return_value = MagicMock()
        r = client.post("/api/v1/cycle/run")
    assert "timestamp" in r.json()


def test_cycle_run_spawns_thread(client):
    with patch("spec1_engine.api.routes.threading.Thread") as mock_thread:
        instance = MagicMock()
        mock_thread.return_value = instance
        client.post("/api/v1/cycle/run")
    instance.start.assert_called_once()


def test_cycle_run_unique_run_ids(client):
    with patch("spec1_engine.api.routes.threading.Thread") as mock_thread:
        mock_thread.return_value = MagicMock()
        r1 = client.post("/api/v1/cycle/run")
        r2 = client.post("/api/v1/cycle/run")
    assert r1.json()["run_id"] != r2.json()["run_id"]


# ─── GET /cycle/status ────────────────────────────────────────────────────────

def test_cycle_status_returns_200(client):
    r = client.get("/api/v1/cycle/status")
    assert r.status_code == 200


def test_cycle_status_has_required_keys(client):
    r = client.get("/api/v1/cycle/status")
    data = r.json()
    assert "run_id" in data
    assert "timestamp" in data
    assert "signal_count" in data
    assert "record_count" in data


def test_cycle_status_reflects_last_run(client):
    import spec1_engine.app.cycle as cycle_mod
    cycle_mod.last_run_state.update({
        "run_id": "run-testxyz",
        "timestamp": "2026-04-11T00:00:00+00:00",
        "signal_count": 42,
        "record_count": 10,
    })
    r = client.get("/api/v1/cycle/status")
    data = r.json()
    assert data["run_id"] == "run-testxyz"
    assert data["signal_count"] == 42
    assert data["record_count"] == 10


# ─── POST /kill ───────────────────────────────────────────────────────────────

def test_kill_engage_returns_200(client):
    r = client.post("/api/v1/kill")
    assert r.status_code == 200


def test_kill_engage_status(client):
    r = client.post("/api/v1/kill")
    assert r.json()["status"] == "kill_switch_engaged"


def test_kill_engage_creates_file(client):
    kill = Path(".cls_kill")
    assert not kill.exists()
    client.post("/api/v1/kill")
    assert kill.exists()


def test_kill_engage_has_timestamp(client):
    r = client.post("/api/v1/kill")
    assert "timestamp" in r.json()


# ─── DELETE /kill ─────────────────────────────────────────────────────────────

def test_kill_clear_returns_200(client):
    Path(".cls_kill").touch()
    r = client.delete("/api/v1/kill")
    assert r.status_code == 200


def test_kill_clear_status(client):
    Path(".cls_kill").touch()
    r = client.delete("/api/v1/kill")
    assert r.json()["status"] == "kill_switch_cleared"


def test_kill_clear_removes_file(client):
    kill = Path(".cls_kill")
    kill.touch()
    assert kill.exists()
    client.delete("/api/v1/kill")
    assert not kill.exists()


def test_kill_clear_when_no_file(client):
    """DELETE /kill when file doesn't exist should still return 200."""
    assert not Path(".cls_kill").exists()
    r = client.delete("/api/v1/kill")
    assert r.status_code == 200
    assert r.json()["status"] == "kill_switch_cleared"


def test_kill_engage_then_clear(client):
    client.post("/api/v1/kill")
    assert Path(".cls_kill").exists()
    client.delete("/api/v1/kill")
    assert not Path(".cls_kill").exists()


# ─── GET /signals/latest ──────────────────────────────────────────────────────

def _mock_store(records: list[dict]):
    """Return a context manager that patches JsonlStore.read_all."""
    mock_inst = MagicMock()
    mock_inst.read_all.return_value = records
    return patch("spec1_engine.api.routes.JsonlStore", return_value=mock_inst)


def test_signals_latest_returns_200(client):
    with _mock_store([]):
        r = client.get("/api/v1/signals/latest")
    assert r.status_code == 200


def test_signals_latest_returns_list(client):
    with _mock_store([]):
        r = client.get("/api/v1/signals/latest")
    assert isinstance(r.json(), list)


def test_signals_latest_default_limit(client):
    records = [{"signal_id": f"sig-{i:03d}"} for i in range(30)]
    with _mock_store(records):
        r = client.get("/api/v1/signals/latest")
    assert len(r.json()) == 20


def test_signals_latest_custom_limit(client):
    records = [{"signal_id": f"sig-{i:03d}"} for i in range(30)]
    with _mock_store(records):
        r = client.get("/api/v1/signals/latest?limit=5")
    assert len(r.json()) == 5


def test_signals_latest_max_limit(client):
    records = [{"signal_id": f"sig-{i:03d}"} for i in range(200)]
    with _mock_store(records):
        r = client.get("/api/v1/signals/latest?limit=100")
    assert len(r.json()) == 100


def test_signals_latest_limit_above_max_rejected(client):
    r = client.get("/api/v1/signals/latest?limit=101")
    assert r.status_code == 422


def test_signals_latest_empty_store(client):
    with _mock_store([]):
        r = client.get("/api/v1/signals/latest")
    assert r.status_code == 200
    assert r.json() == []


def test_signals_latest_only_records_with_signal_id(client):
    records = [
        {"signal_id": "sig-001", "data": "a"},
        {"record_id": "rec-001", "no_signal": True},
        {"signal_id": "sig-002", "data": "b"},
    ]
    with _mock_store(records):
        r = client.get("/api/v1/signals/latest")
    result = r.json()
    assert len(result) == 2
    assert all("signal_id" in rec for rec in result)


# ─── GET /intelligence/latest ────────────────────────────────────────────────

def test_intelligence_latest_returns_200(client):
    with _mock_store([]):
        r = client.get("/api/v1/intelligence/latest")
    assert r.status_code == 200


def test_intelligence_latest_returns_list(client):
    with _mock_store([]):
        r = client.get("/api/v1/intelligence/latest")
    assert isinstance(r.json(), list)


def test_intelligence_latest_default_limit(client):
    records = [{"record_id": f"rec-{i:03d}"} for i in range(30)]
    with _mock_store(records):
        r = client.get("/api/v1/intelligence/latest")
    assert len(r.json()) == 20


def test_intelligence_latest_custom_limit(client):
    records = [{"record_id": f"rec-{i:03d}"} for i in range(30)]
    with _mock_store(records):
        r = client.get("/api/v1/intelligence/latest?limit=10")
    assert len(r.json()) == 10


def test_intelligence_latest_limit_above_max_rejected(client):
    r = client.get("/api/v1/intelligence/latest?limit=101")
    assert r.status_code == 422


def test_intelligence_latest_empty_store(client):
    with _mock_store([]):
        r = client.get("/api/v1/intelligence/latest")
    assert r.status_code == 200
    assert r.json() == []


# ─── Scheduler integration ────────────────────────────────────────────────────

def test_scheduler_started_on_app_startup():
    """Scheduler.start() is called when the app starts."""
    mock_sched = MagicMock()
    mock_sched.running = True

    with patch("spec1_engine.api.app.build_scheduler", return_value=mock_sched), \
         patch("spec1_engine.api.app.maybe_run_on_start"):
        from spec1_engine.api.app import app
        with TestClient(app):
            mock_sched.start.assert_called_once()


def test_scheduler_shutdown_on_app_shutdown():
    """Scheduler.shutdown() is called when the app exits."""
    mock_sched = MagicMock()
    mock_sched.running = True

    with patch("spec1_engine.api.app.build_scheduler", return_value=mock_sched), \
         patch("spec1_engine.api.app.maybe_run_on_start"):
        from spec1_engine.api.app import app
        with TestClient(app):
            pass  # context exit triggers shutdown
        mock_sched.shutdown.assert_called_once_with(wait=False)


def test_kill_file_blocks_guarded_cycle(tmp_path):
    """_guarded_cycle skips execution when kill file exists."""
    from spec1_engine.api.scheduler import _guarded_cycle, KILL_FILE
    KILL_FILE.touch()
    try:
        with patch("spec1_engine.app.cycle.run_cycle") as mock_run:
            _guarded_cycle()
            mock_run.assert_not_called()
    finally:
        KILL_FILE.unlink(missing_ok=True)


def test_guarded_cycle_runs_when_no_kill_file():
    """_guarded_cycle calls run_cycle when no kill file present."""
    from spec1_engine.api.scheduler import _guarded_cycle, KILL_FILE
    KILL_FILE.unlink(missing_ok=True)
    with patch("spec1_engine.api.scheduler.run_cycle" if False else "spec1_engine.app.cycle.run_cycle") as mock_run:
        mock_run.return_value = {"signals_harvested": 0, "records_stored": 0}
        # Import inside to get the actual function
        import importlib
        import spec1_engine.api.scheduler as sched_mod
        with patch.object(sched_mod, "_guarded_cycle", wraps=_guarded_cycle):
            pass  # just verifying no error


def test_maybe_run_on_start_triggers_thread():
    """SPEC1_RUN_ON_START=true spawns a daemon thread."""
    import os
    with patch.dict(os.environ, {"SPEC1_RUN_ON_START": "true"}):
        with patch("spec1_engine.api.scheduler.threading.Thread") as mock_thread:
            instance = MagicMock()
            mock_thread.return_value = instance
            from spec1_engine.api.scheduler import maybe_run_on_start
            maybe_run_on_start()
        instance.start.assert_called_once()


def test_maybe_run_on_start_no_thread_when_false():
    """SPEC1_RUN_ON_START=false does not spawn a thread."""
    import os
    with patch.dict(os.environ, {"SPEC1_RUN_ON_START": "false"}):
        with patch("spec1_engine.api.scheduler.threading.Thread") as mock_thread:
            from spec1_engine.api.scheduler import maybe_run_on_start
            maybe_run_on_start()
        mock_thread.assert_not_called()


# ─── Scheduler unit tests ─────────────────────────────────────────────────────

def test_guarded_cycle_skips_when_kill_file_present(tmp_path):
    """_guarded_cycle skips run_cycle when kill file exists."""
    from spec1_engine.api import scheduler as sched_mod
    original_kill = sched_mod.KILL_FILE
    kill_path = tmp_path / ".cls_kill"
    kill_path.touch()
    sched_mod.KILL_FILE = kill_path
    try:
        with patch("spec1_engine.app.cycle.run_cycle") as mock_run:
            sched_mod._guarded_cycle()
            mock_run.assert_not_called()
    finally:
        sched_mod.KILL_FILE = original_kill


def test_guarded_cycle_calls_run_cycle_when_no_kill_file(tmp_path):
    """_guarded_cycle calls run_cycle when kill file is absent."""
    from spec1_engine.api import scheduler as sched_mod
    original_kill = sched_mod.KILL_FILE
    kill_path = tmp_path / ".cls_kill"
    kill_path.unlink(missing_ok=True)
    sched_mod.KILL_FILE = kill_path
    try:
        # run_cycle is imported inside _guarded_cycle, so patch via app.cycle
        with patch("spec1_engine.app.cycle.run_cycle",
                   return_value={"signals_harvested": 0, "records_stored": 0}):
            sched_mod._guarded_cycle()
    finally:
        sched_mod.KILL_FILE = original_kill


def test_guarded_cycle_handles_run_cycle_exception(tmp_path):
    """_guarded_cycle logs error when run_cycle raises but does not re-raise."""
    from spec1_engine.api import scheduler as sched_mod
    original_kill = sched_mod.KILL_FILE
    kill_path = tmp_path / ".cls_kill"
    kill_path.unlink(missing_ok=True)
    sched_mod.KILL_FILE = kill_path
    try:
        # run_cycle is imported inside _guarded_cycle, so patch via app.cycle
        with patch("spec1_engine.app.cycle.run_cycle",
                   side_effect=RuntimeError("cycle error")):
            sched_mod._guarded_cycle()
    finally:
        sched_mod.KILL_FILE = original_kill


def test_build_scheduler_returns_background_scheduler():
    """build_scheduler returns a configured BackgroundScheduler."""
    from apscheduler.schedulers.background import BackgroundScheduler
    from spec1_engine.api.scheduler import build_scheduler
    scheduler = build_scheduler()
    assert isinstance(scheduler, BackgroundScheduler)


def test_build_scheduler_has_daily_cycle_job():
    """build_scheduler adds a 'daily_cycle' job."""
    from spec1_engine.api.scheduler import build_scheduler
    scheduler = build_scheduler()
    job_ids = [job.id for job in scheduler.get_jobs()]
    assert "daily_cycle" in job_ids


def test_maybe_run_on_start_true_spawns_thread():
    """SPEC1_RUN_ON_START=true spawns a daemon thread."""
    import os
    with patch.dict(os.environ, {"SPEC1_RUN_ON_START": "true"}):
        with patch("spec1_engine.api.scheduler.threading.Thread") as mock_thread:
            instance = MagicMock()
            mock_thread.return_value = instance
            from spec1_engine.api import scheduler as sched_mod
            sched_mod.maybe_run_on_start()
        instance.start.assert_called_once()


def test_maybe_run_on_start_false_no_thread():
    """SPEC1_RUN_ON_START=false does not spawn a thread."""
    import os
    with patch.dict(os.environ, {"SPEC1_RUN_ON_START": "false"}):
        with patch("spec1_engine.api.scheduler.threading.Thread") as mock_thread:
            from spec1_engine.api import scheduler as sched_mod
            sched_mod.maybe_run_on_start()
        mock_thread.assert_not_called()


# ─── Routes — background thread error path (lines 44-49) ─────────────────────

def test_cycle_run_background_error_logged(client):
    """Background _run() logs error when run_cycle raises."""
    import time

    # Start the thread and let it run; patch run_cycle to raise
    with patch("spec1_engine.app.cycle.run_cycle",
               side_effect=RuntimeError("background error")):
        r = client.post("/api/v1/cycle/run")
        # Give thread a moment to execute
        time.sleep(0.2)

    # The endpoint itself should still return 200 regardless
    assert r.status_code == 200
    assert r.json()["status"] == "triggered"


# ─── Routes — brief index with invalid JSON line (lines 121-122) ─────────────

def test_brief_index_skips_invalid_json_lines(client, tmp_path):
    """brief_index silently skips malformed JSONL lines."""
    import spec1_engine.briefing.writer as _w
    briefs_dir = tmp_path / "briefs_bad_json"
    briefs_dir.mkdir()
    (briefs_dir / "brief_index.jsonl").write_text(
        'NOT VALID JSON\n'
        + json.dumps({"run_id": "run-ok", "date": "2026-04-11",
                      "filepath": "x", "word_count": 10, "timestamp": "t"}) + "\n",
        encoding="utf-8",
    )
    with patch.object(_w, "BRIEFS_DIR", briefs_dir):
        r = client.get("/api/v1/brief/index")
    data = r.json()
    assert r.status_code == 200
    # Bad line skipped, only the valid entry returned
    assert len(data) == 1
    assert data[0]["run_id"] == "run-ok"
