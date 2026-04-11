"""JSONL Intelligence Store — ported from cls_osint/persistence/store.py.

Append-only JSONL writer with threading lock and disk persistence.
Single-writer rule enforced via threading.Lock.
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Optional


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class JsonlStore:
    """Thread-safe JSONL append-only store with configurable file path."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._lock = threading.Lock()

    def append(self, record: dict) -> dict:
        """Append a single record to the JSONL file. Returns the written entry."""
        if not isinstance(record, dict):
            raise TypeError(f"record must be dict, got {type(record)}")
        entry = {**record, "written_at": _now()}
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry) + "\n")
        return entry

    def append_batch(self, records: list[dict]) -> list[dict]:
        """Append multiple records atomically under a single lock."""
        if not records:
            return []
        written: list[dict] = []
        now = _now()
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as fh:
                for record in records:
                    if not isinstance(record, dict):
                        raise TypeError(f"record must be dict, got {type(record)}")
                    entry = {**record, "written_at": now}
                    fh.write(json.dumps(entry) + "\n")
                    written.append(entry)
        return written

    def read_all(self) -> Iterator[dict]:
        """Iterate over all records in the store."""
        if not self.path.exists():
            return
        with self.path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue

    def count(self) -> int:
        """Count records in the store."""
        return sum(1 for _ in self.read_all())

    def filter_by(self, field: str, value: object) -> Iterator[dict]:
        """Iterate records matching a field value."""
        for record in self.read_all():
            if record.get(field) == value:
                yield record

    def exists(self) -> bool:
        """Return True if the store file exists and is non-empty."""
        return self.path.exists() and self.path.stat().st_size > 0

    def clear(self) -> None:
        """Delete the store file (for testing)."""
        if self.path.exists():
            self.path.unlink()


# Module-level convenience functions for backwards compatibility
_DEFAULT_STORE: Optional[JsonlStore] = None
_DEFAULT_PATH = Path("spec1_intelligence.jsonl")


def _get_default_store(path: Optional[Path] = None) -> JsonlStore:
    global _DEFAULT_STORE, _DEFAULT_PATH
    target = path or _DEFAULT_PATH
    if _DEFAULT_STORE is None or _DEFAULT_STORE.path != target:
        _DEFAULT_STORE = JsonlStore(target)
    return _DEFAULT_STORE


def append(record: dict, path: Optional[Path] = None) -> dict:
    return _get_default_store(path).append(record)


def append_batch(records: list[dict], path: Optional[Path] = None) -> list[dict]:
    return _get_default_store(path).append_batch(records)


def read_all(path: Optional[Path] = None) -> Iterator[dict]:
    return _get_default_store(path).read_all()


def count(path: Optional[Path] = None) -> int:
    return _get_default_store(path).count()


def filter_by(field: str, value: object, path: Optional[Path] = None) -> Iterator[dict]:
    return _get_default_store(path).filter_by(field, value)


def exists(path: Optional[Path] = None) -> bool:
    return _get_default_store(path).exists()
