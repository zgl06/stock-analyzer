from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from pydantic import BaseModel, ConfigDict

import logging

from backend.app.analysis import run_analysis_from_fixture, run_analysis_pipeline
from backend.app.config import get_settings
from backend.app.errors import AppError, NotFoundError
from backend.app.models import AnalysisInput, AnalysisResponse
from backend.app.services.ingestion import run_ingestion
from backend.app.services.storage import StorageService

logger = logging.getLogger(__name__)


router = APIRouter()

_templates = Jinja2Templates(
    directory=str(Path(__file__).parent.parent.parent / "templates")
)


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


async def _resolve_analysis(ticker: str, *, refresh: bool = False) -> AnalysisResponse:
    """Resolve an `AnalysisResponse` for the given ticker.

    Lookup order:
      1. Bundled fixture (fast, deterministic; currently AAPL only).
      2. Latest persisted `AnalysisInput` from Supabase (cached live data),
         unless `refresh=True` is passed -- callers can force a fresh
         ingestion to pick up changes in the normalization layer.
      3. Live ingestion: fetch SEC filings + market data, persist, then
         run the analysis pipeline. Any unknown / delisted ticker
         surfaces as a clean 404.
    """
    normalized_ticker = ticker.strip().upper()

    try:
        return run_analysis_from_fixture(normalized_ticker)
    except NotFoundError:
        pass
    except AppError as error:
        raise _to_http_exception(error) from error

    settings = get_settings()
    if not settings.has_supabase:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No fixture is available for '{normalized_ticker}' and Supabase "
                "storage is not configured. Configure Supabase to enable live "
                "ingestion."
            ),
        )

    storage = StorageService(settings)
    if not refresh:
        try:
            payload: dict[str, Any] = await storage.get_latest_analysis_input(
                normalized_ticker
            )
            analysis_input = AnalysisInput.model_validate(payload)
            return run_analysis_pipeline(analysis_input, source="live")
        except NotFoundError:
            logger.info(
                "No stored analysis for %s; running live ingestion.",
                normalized_ticker,
            )
        except AppError as error:
            raise _to_http_exception(error) from error
    else:
        logger.info(
            "Refresh requested for %s; bypassing storage cache.",
            normalized_ticker,
        )

    try:
        result = await run_ingestion(normalized_ticker)
    except NotFoundError as error:
        raise HTTPException(status_code=404, detail=error.message) from error
    except AppError as error:
        raise _to_http_exception(error) from error

    return run_analysis_pipeline(result.analysis_input, source="live")


@router.get("/analysis/{ticker}", response_model=AnalysisResponse)
async def get_analysis(ticker: str, refresh: bool = False) -> AnalysisResponse:
    """Assemble an analysis response from fixture or persisted live data.

    Pass `?refresh=true` to bypass the Supabase cache and re-run live
    ingestion. Useful after upgrading the normalization or scoring code,
    when stale cached `AnalysisInput` blobs would otherwise hide the
    improvement.
    """
    return await _resolve_analysis(ticker, refresh=refresh)


@router.get("/analysis/{ticker}/dashboard", response_class=HTMLResponse)
async def get_analysis_dashboard(
    ticker: str, request: Request, refresh: bool = False
) -> HTMLResponse:
    """Return an HTML dashboard for the analysis of the given ticker."""
    result = await _resolve_analysis(ticker, refresh=refresh)
    normalized_ticker = ticker.strip().upper()

    return _templates.TemplateResponse(
        request=request,
        name="analysis_dashboard.html",
        context={
            "ticker": normalized_ticker,
            "generated_at": result.generated_at,
            "source": result.source,
            "data": result.model_dump(),
        },
    )
