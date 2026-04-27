"""Verdict persistence — JSONL (always) and SQLite (when a Database is provided).

VerdictStore can run in two modes:

- **JSONL-only** (`VerdictStore(path)`) — append-only file, source of truth.
  This is the back-compat path; existing tests and tooling use it.
- **Dual-write** (`VerdictStore(path, db=database)`) — writes to JSONL *and*
  the `verdicts` SQLite table via cls_db.dual_write.DualWriter. The JSONL
  remains source of truth; SQLite failures are logged and non-fatal.

The SQLite table is also queryable directly (the index on `record_id`
makes `for_record` lookups fast at scale), but the public methods on
this class always read from JSONL so the two paths can be compared.
"""

from __future__ import annotations

import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Optional

from cls_verdicts.schemas import Verdict

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class VerdictStore:
    """Thread-safe append-only JSONL store for Verdict records, with optional SQLite dual-write."""

    def __init__(
        self,
        path: Path = Path("verdicts.jsonl"),
        db: Optional["Database"] = None,  # noqa: F821  (forward ref to cls_db.database.Database)
    ) -> None:
        self.path = Path(path)
        self._lock = threading.Lock()
        self._dual_writer = None
        if db is not None:
            # Lazy import — keeps the JSONL-only path free of cls_db
            from cls_db.dual_write import DualWriter

            self._dual_writer = DualWriter(
                jsonl_path=self.path,
                db=db,
                table="verdicts",
                pk_field="verdict_id",
            )

    def save(self, verdict: Verdict) -> dict:
        """Append a single verdict. Dual-writes to SQLite when configured."""
        if self._dual_writer is not None:
            return self._dual_writer.write(verdict.to_dict())
        entry = {**verdict.to_dict(), "written_at": _now()}
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry) + "\n")
        return entry

    def read_all(self) -> Iterator[dict]:
        """Yield every persisted verdict in insertion order (from JSONL — source of truth)."""
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

    def for_record(self, record_id: str) -> list[dict]:
        """Return every verdict filed for a single record, oldest first."""
        return [v for v in self.read_all() if v.get("record_id") == record_id]

    def count(self) -> int:
        return sum(1 for _ in self.read_all())
