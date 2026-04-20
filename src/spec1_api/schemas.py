"""Pydantic request/response schemas for spec1_api."""

from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "0.0.0"
    environment: str = "production"


class CycleRequest(BaseModel):
    max_signals: Optional[int] = Field(None, description="Limit harvested signals")
    environment: str = Field("production", description="Run environment label")
    collect_fara: bool = Field(False, description="Include FARA collection")
    collect_congress: bool = Field(False, description="Include congressional collection")
    detect_narratives: bool = Field(True, description="Run narrative detection")


class CycleResponse(BaseModel):
    run_id: str
    started_at: str
    finished_at: Optional[str] = None
    signals_harvested: int = 0
    signals_parsed: int = 0
    opportunities_found: int = 0
    investigations_generated: int = 0
    outcomes_verified: int = 0
    records_stored: int = 0
    errors: list[str] = Field(default_factory=list)


class SignalResponse(BaseModel):
    signal_id: str
    source: str
    source_type: str = "RSS"
    text: str
    url: str
    author: str = ""
    published_at: str
    run_id: str = ""
    environment: str = "production"
    metadata: dict = Field(default_factory=dict)


class IntelResponse(BaseModel):
    record_id: str
    pattern: str = ""
    classification: str = ""
    confidence: float = 0.0
    source_weight: float = 0.0
    analyst_weight: float = 0.0
    written_at: Optional[str] = None


class LeadResponse(BaseModel):
    lead_id: str
    title: str
    summary: str
    priority: str
    category: str
    confidence: float = 0.5
    action_items: list[str] = Field(default_factory=list)
    generated_at: str
    written_at: Optional[str] = None


class BriefResponse(BaseModel):
    brief_id: str
    date: str
    headline: str
    summary: str
    sections: list[dict] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    confidence: float = 0.7
    produced_at: str


class PsyopResponse(BaseModel):
    score_id: str
    text_excerpt: str
    patterns_matched: list[str] = Field(default_factory=list)
    pattern_names: list[str] = Field(default_factory=list)
    score: float = 0.0
    classification: str = "CLEAN"
    threat_categories: list[str] = Field(default_factory=list)
    scored_at: str


class FaraResponse(BaseModel):
    record_id: str
    registrant: str
    foreign_principal: str
    country: str
    activities: list[str] = Field(default_factory=list)
    filed_at: str
    doc_url: str
    status: str = "ACTIVE"


class PaginatedResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[Any]
