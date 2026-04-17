"""Schema migration runner for cls_db.

Applies DDL statements to create tables if they don't already exist.
"""

from __future__ import annotations

from cls_db.database import Database
from cls_db.models import ALL_DDL


def ensure_schema(db: Database) -> list[str]:
    """Create all tables that don't yet exist.

    Returns list of table names that were created.
    """
    created: list[str] = []
    for table_name, ddl in ALL_DDL:
        if not db.table_exists(table_name):
            db.execute(ddl)
            created.append(table_name)
    return created


def run_migrations(db: Database) -> dict:
    """Run all pending migrations and return a report dict."""
    created = ensure_schema(db)
    existing = [name for name, _ in ALL_DDL if name not in created]
    return {
        "tables_created": created,
        "tables_existing": existing,
        "total_tables": len(ALL_DDL),
    }


def drop_all(db: Database) -> None:
    """Drop all managed tables. USE WITH CAUTION — for testing only."""
    for table_name, _ in ALL_DDL:
        db.execute(f"DROP TABLE IF EXISTS {table_name}")


def reset_schema(db: Database) -> dict:
    """Drop and recreate all tables."""
    drop_all(db)
    return run_migrations(db)
