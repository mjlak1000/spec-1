"""JSONL persistence for cls_osint records."""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterator, Optional


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class OsintStore:
    """Thread-safe append-only JSONL store for OSINT records."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._lock = threading.Lock()

    def append(self, record: dict) -> dict:
        if not isinstance(record, dict):
            raise TypeError(f"record must be dict, got {type(record)}")
        entry = {**record, "written_at": _now()}
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry) + "\n")
        return entry

    def append_batch(self, records: list[dict]) -> list[dict]:
        if not records:
            return []
        now = _now()
        written: list[dict] = []
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

    def filter_by(self, field: str, value: object) -> Iterator[dict]:
        for record in self.read_all():
            if record.get(field) == value:
                yield record

    def filter_fn(self, predicate: Callable[[dict], bool]) -> Iterator[dict]:
        for record in self.read_all():
            if predicate(record):
                yield record

    def count(self) -> int:
        return sum(1 for _ in self.read_all())

    def exists(self) -> bool:
        return self.path.exists() and self.path.stat().st_size > 0

    def clear(self) -> None:
        if self.path.exists():
            self.path.unlink()

    def latest(self, n: int = 10) -> list[dict]:
        """Return the last n records (reads entire file)."""
        all_records = list(self.read_all())
        return all_records[-n:]
