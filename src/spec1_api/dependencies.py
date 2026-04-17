"""FastAPI dependency injection for spec1_api."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from fastapi import Depends

from spec1_engine.intelligence.store import JsonlStore
from cls_osint.store import OsintStore
from cls_leads.store import LeadStore
from cls_psyop.store import PsyopStore
from cls_quant.store import QuantStore
from cls_world_brief.store import BriefStore
from cls_db.database import Database
from cls_db.migrate import ensure_schema


def _env_path(env_var: str, default: str) -> Path:
    return Path(os.environ.get(env_var, default))


@lru_cache(maxsize=1)
def get_intel_store() -> JsonlStore:
    path = _env_path("SPEC1_STORE_PATH", "spec1_intelligence.jsonl")
    return JsonlStore(path)


@lru_cache(maxsize=1)
def get_osint_store() -> OsintStore:
    path = _env_path("SPEC1_OSINT_PATH", "osint_records.jsonl")
    return OsintStore(path)


@lru_cache(maxsize=1)
def get_lead_store() -> LeadStore:
    path = _env_path("SPEC1_LEADS_PATH", "leads.jsonl")
    return LeadStore(path)


@lru_cache(maxsize=1)
def get_psyop_store() -> PsyopStore:
    path = _env_path("SPEC1_PSYOP_PATH", "psyop_scores.jsonl")
    return PsyopStore(path)


@lru_cache(maxsize=1)
def get_quant_store() -> QuantStore:
    path = _env_path("SPEC1_QUANT_PATH", "quant_signals.jsonl")
    return QuantStore(path)


@lru_cache(maxsize=1)
def get_brief_store() -> BriefStore:
    jsonl = _env_path("SPEC1_BRIEFS_PATH", "world_briefs.jsonl")
    briefs_dir = _env_path("SPEC1_BRIEFS_DIR", "briefs")
    return BriefStore(jsonl_path=jsonl, briefs_dir=briefs_dir)


@lru_cache(maxsize=1)
def get_database() -> Database:
    path = _env_path("SPEC1_DB_PATH", "spec1.db")
    db = Database(path)
    ensure_schema(db)
    return db


# Type aliases for use in route signatures
IntelStoreDep = Annotated[JsonlStore, Depends(get_intel_store)]
OsintStoreDep = Annotated[OsintStore, Depends(get_osint_store)]
LeadStoreDep = Annotated[LeadStore, Depends(get_lead_store)]
PsyopStoreDep = Annotated[PsyopStore, Depends(get_psyop_store)]
QuantStoreDep = Annotated[QuantStore, Depends(get_quant_store)]
BriefStoreDep = Annotated[BriefStore, Depends(get_brief_store)]
DatabaseDep = Annotated[Database, Depends(get_database)]
