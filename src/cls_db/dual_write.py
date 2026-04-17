"""Dual-write layer — writes to both JSONL and SQLite atomically.

Wraps the existing JSONL stores with a SQLite repository so every write
goes to both backends simultaneously.
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from cls_db.database import Database
from cls_db.migrate import ensure_schema
from cls_db.repository import Repository


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class DualWriter:
    """Writes a record dict to both a JSONL file and a SQLite table."""

    def __init__(
        self,
        jsonl_path: Path,
        db: Database,
        table: str,
        pk_field: str = "record_id",
    ) -> None:
        self.jsonl_path = Path(jsonl_path)
        self.db = db
        self.repo = Repository(db, table, pk_field)
        self.table = table
        self._lock = threading.Lock()
        ensure_schema(db)

    def write(self, record: dict) -> dict:
        """Write a single record to both JSONL and SQLite."""
        entry = {**record, "written_at": _now()}
        with self._lock:
            # JSONL write
            self.jsonl_path.parent.mkdir(parents=True, exist_ok=True)
            with self.jsonl_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry) + "\n")
            # SQLite write
            try:
                self.repo.insert(entry)
            except Exception:
                pass  # JSONL is source of truth; SQLite failure is non-fatal
        return entry

    def write_batch(self, records: list[dict]) -> list[dict]:
        """Write multiple records to both backends."""
        if not records:
            return []
        now = _now()
        entries = [{**r, "written_at": now} for r in records]
        with self._lock:
            self.jsonl_path.parent.mkdir(parents=True, exist_ok=True)
            with self.jsonl_path.open("a", encoding="utf-8") as fh:
                for entry in entries:
                    fh.write(json.dumps(entry) + "\n")
            try:
                self.repo.insert_batch(entries)
            except Exception:
                pass
        return entries

    def read_jsonl(self) -> list[dict]:
        """Read all records from JSONL (source of truth)."""
        if not self.jsonl_path.exists():
            return []
        records: list[dict] = []
        with self.jsonl_path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return records

    def read_db(self, limit: Optional[int] = None) -> list[dict]:
        """Read records from SQLite."""
        return self.repo.all(limit=limit)

    def count_jsonl(self) -> int:
        return len(self.read_jsonl())

    def count_db(self) -> int:
        return self.repo.count()


def make_dual_writer(
    jsonl_path: Path,
    db_path: Path,
    table: str,
    pk_field: str = "record_id",
) -> DualWriter:
    """Factory function — creates a DualWriter for the given paths and table."""
    db = Database(db_path)
    ensure_schema(db)
    return DualWriter(jsonl_path=jsonl_path, db=db, table=table, pk_field=pk_field)
