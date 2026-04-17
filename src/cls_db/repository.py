"""Generic CRUD repository for cls_db.

Provides typed insert/select/delete over SQLite tables.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Optional

from cls_db.database import Database


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _serialize(value: Any) -> Any:
    """Serialize lists/dicts to JSON strings for SQLite storage."""
    if isinstance(value, (list, dict)):
        return json.dumps(value)
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _row_to_dict(row: dict) -> dict:
    """Deserialize JSON string fields back to Python objects."""
    result: dict = {}
    for k, v in row.items():
        if isinstance(v, str) and v and v[0] in ("{", "["):
            try:
                result[k] = json.loads(v)
            except json.JSONDecodeError:
                result[k] = v
        else:
            result[k] = v
    return result


class Repository:
    """Generic repository for a single SQLite table."""

    def __init__(self, db: Database, table: str, pk_field: str = "record_id") -> None:
        self.db = db
        self.table = table
        self.pk_field = pk_field

    def insert(self, record: dict) -> dict:
        """Insert a record; skip if PK already exists (INSERT OR IGNORE)."""
        entry = {k: _serialize(v) for k, v in record.items()}
        if "written_at" not in entry:
            entry["written_at"] = _now()
        columns = ", ".join(entry.keys())
        placeholders = ", ".join("?" for _ in entry)
        sql = f"INSERT OR REPLACE INTO {self.table} ({columns}) VALUES ({placeholders})"
        self.db.execute(sql, tuple(entry.values()))
        return record

    def insert_batch(self, records: list[dict]) -> int:
        """Insert multiple records; return count inserted."""
        if not records:
            return 0
        now = _now()
        rows: list[tuple] = []
        for rec in records:
            entry = {k: _serialize(v) for k, v in rec.items()}
            if "written_at" not in entry:
                entry["written_at"] = now
            rows.append(tuple(entry.values()))

        # Use columns from first record
        first = {k: _serialize(v) for k, v in records[0].items()}
        if "written_at" not in first:
            first["written_at"] = now
        columns = ", ".join(first.keys())
        placeholders = ", ".join("?" for _ in first)
        sql = f"INSERT OR REPLACE INTO {self.table} ({columns}) VALUES ({placeholders})"
        self.db.executemany(sql, rows)
        return len(rows)

    def get(self, pk_value: str) -> Optional[dict]:
        """Fetch a single record by primary key."""
        row = self.db.fetchone(
            f"SELECT * FROM {self.table} WHERE {self.pk_field} = ?",
            (pk_value,),
        )
        return _row_to_dict(row) if row else None

    def all(self, limit: Optional[int] = None, offset: int = 0) -> list[dict]:
        """Return all records, optionally limited."""
        sql = f"SELECT * FROM {self.table} ORDER BY rowid"
        params: tuple = ()
        if limit is not None:
            sql += " LIMIT ? OFFSET ?"
            params = (limit, offset)
        rows = self.db.fetchall(sql, params)
        return [_row_to_dict(r) for r in rows]

    def filter(self, field: str, value: Any, limit: Optional[int] = None) -> list[dict]:
        """Return records matching field = value."""
        sql = f"SELECT * FROM {self.table} WHERE {field} = ?"
        params: tuple = (_serialize(value),)
        if limit is not None:
            sql += f" LIMIT {limit}"
        rows = self.db.fetchall(sql, params)
        return [_row_to_dict(r) for r in rows]

    def count(self) -> int:
        row = self.db.fetchone(f"SELECT COUNT(*) as n FROM {self.table}")
        return row["n"] if row else 0

    def delete(self, pk_value: str) -> None:
        self.db.execute(
            f"DELETE FROM {self.table} WHERE {self.pk_field} = ?",
            (pk_value,),
        )

    def latest(self, n: int = 10) -> list[dict]:
        """Return the last n records by rowid."""
        rows = self.db.fetchall(
            f"SELECT * FROM {self.table} ORDER BY rowid DESC LIMIT ?",
            (n,),
        )
        return [_row_to_dict(r) for r in reversed(rows)]
