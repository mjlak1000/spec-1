"""Quant signal persistence — JSONL store."""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from cls_quant.schemas import QuantSignal


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class QuantStore:
    """Thread-safe JSONL store for QuantSignal records."""

    def __init__(self, path: Path = Path("quant_signals.jsonl")) -> None:
        self.path = Path(path)
        self._lock = threading.Lock()

    def save(self, signal: QuantSignal) -> dict:
        entry = {**signal.to_dict(), "written_at": _now()}
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry) + "\n")
        return entry

    def save_batch(self, signals: list[QuantSignal]) -> list[dict]:
        if not signals:
            return []
        now = _now()
        written: list[dict] = []
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as fh:
                for signal in signals:
                    entry = {**signal.to_dict(), "written_at": now}
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

    def by_ticker(self, ticker: str) -> Iterator[dict]:
        for rec in self.read_all():
            if rec.get("ticker") == ticker:
                yield rec

    def by_pattern(self, pattern: str) -> Iterator[dict]:
        for rec in self.read_all():
            if rec.get("pattern") == pattern:
                yield rec

    def latest(self, n: int = 10) -> list[dict]:
        return list(self.read_all())[-n:]

    def count(self) -> int:
        return sum(1 for _ in self.read_all())

    def clear(self) -> None:
        if self.path.exists():
            self.path.unlink()
