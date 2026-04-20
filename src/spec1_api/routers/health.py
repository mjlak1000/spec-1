"""Health check router."""

from __future__ import annotations

import os

from fastapi import APIRouter

from spec1_api import __version__
from spec1_api.schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    """Return service health status."""
    return HealthResponse(
        status="ok",
        version=__version__,
        environment=os.environ.get("SPEC1_ENVIRONMENT", "production"),
    )
