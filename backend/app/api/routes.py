from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict

from backend.app.config import get_settings
from backend.app.errors import AppError
from backend.app.models import AnalysisInput
from backend.app.services.ingestion import run_ingestion
from backend.app.services.storage import StorageService


router = APIRouter()


class HealthResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    status: str
    environment: str
    supabase_configured: bool
    supabase_connected: bool
    timestamp: datetime


class AnalyzeResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    ticker: str
    status: str
    generated_at: datetime
    analysis_input: AnalysisInput


def _to_http_exception(error: AppError) -> HTTPException:
    return HTTPException(status_code=error.status_code, detail=error.message)

@router.get("/")
async def root() -> dict[str, str]:
    return {"status": "ok", "docs": "/docs", "health": "/health"}


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    settings = get_settings()
    storage = StorageService(settings)
    supabase_connected = await storage.check_health()
    return HealthResponse(
        status="ok" if supabase_connected or not settings.has_supabase else "degraded",
        environment=settings.app_env,
        supabase_configured=settings.has_supabase,
        supabase_connected=supabase_connected,
        timestamp=datetime.now(timezone.utc),
    )


@router.post("/analyze/{ticker}", response_model=AnalyzeResponse)
async def analyze_ticker(ticker: str) -> AnalyzeResponse:
    normalized_ticker = ticker.strip().upper()
    try:
        result = await run_ingestion(normalized_ticker)
    except AppError as error:
        raise _to_http_exception(error) from error

    return AnalyzeResponse(
        ticker=normalized_ticker,
        status="completed",
        generated_at=result.generated_at,
        analysis_input=result.analysis_input,
    )


@router.get("/analysis-input/{ticker}", response_model=AnalysisInput)
async def get_analysis_input(ticker: str) -> AnalysisInput:
    normalized_ticker = ticker.strip().upper()
    settings = get_settings()
    storage = StorageService(settings)

    try:
        payload: dict[str, Any] = await storage.get_latest_analysis_input(normalized_ticker)
        return AnalysisInput.model_validate(payload)
    except AppError as error:
        raise _to_http_exception(error) from error
