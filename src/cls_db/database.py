"""SQLite database connection management for cls_db."""

from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Generator, Optional


class Database:
    """Thread-safe SQLite database wrapper with connection pooling.

    Uses check_same_thread=False with an explicit lock for safety.
    """

    def __init__(self, path: Path = Path("spec1.db")) -> None:
        self.path = Path(path)
        self._lock = threading.Lock()
        self._conn: Optional[sqlite3.Connection] = None

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(
                str(self.path),
                check_same_thread=False,
                isolation_level=None,  # autocommit
            )
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
        return self._conn

    @contextmanager
    def cursor(self) -> Generator[sqlite3.Cursor, None, None]:
        """Yield a cursor within an exclusive lock."""
        with self._lock:
            conn = self._get_conn()
            cur = conn.cursor()
            try:
                yield cur
            finally:
                cur.close()

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        """Execute a single statement and return the cursor."""
        with self._lock:
            conn = self._get_conn()
            return conn.execute(sql, params)

    def executemany(self, sql: str, params_seq: list[tuple]) -> None:
        """Execute a statement with multiple parameter sets."""
        with self._lock:
            conn = self._get_conn()
            conn.executemany(sql, params_seq)

    def fetchall(self, sql: str, params: tuple = ()) -> list[dict]:
        """Execute a SELECT and return all rows as dicts."""
        with self._lock:
            conn = self._get_conn()
            cur = conn.execute(sql, params)
            rows = cur.fetchall()
            return [dict(r) for r in rows]

    def fetchone(self, sql: str, params: tuple = ()) -> Optional[dict]:
        """Execute a SELECT and return first row as dict, or None."""
        with self._lock:
            conn = self._get_conn()
            cur = conn.execute(sql, params)
            row = cur.fetchone()
            return dict(row) if row else None

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def exists(self) -> bool:
        return self.path.exists()

    def table_exists(self, table_name: str) -> bool:
        result = self.fetchone(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,),
        )
        return result is not None


# Module-level default database instance
_DEFAULT_DB: Optional[Database] = None
_DEFAULT_PATH = Path("spec1.db")


def get_db(path: Optional[Path] = None) -> Database:
    """Return the module-level default Database, creating if needed."""
    global _DEFAULT_DB
    target = path or _DEFAULT_PATH
    if _DEFAULT_DB is None or _DEFAULT_DB.path != target:
        _DEFAULT_DB = Database(target)
    return _DEFAULT_DB
