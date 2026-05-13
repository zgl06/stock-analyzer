from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from pydantic import BaseModel, ConfigDict

import logging

from backend.app.analysis import run_analysis_pipeline
from backend.app.config import get_settings
from backend.app.errors import AppError, NotFoundError
from backend.app.models import (
    AnalysisInput,
    AnalysisResponse,
    PeersResponse,
    RelativePerformanceView,
    RelativeTercileEstimate,
)
from backend.app.services.ingestion import attach_fresh_market_snapshot, run_ingestion
from backend.app.services.ollama_client import OllamaClient
from backend.app.services.qualitative import QualitativeService
from backend.app.services.rag import RagService
from backend.app.services.relative_model import RelativeModelService
from backend.app.services.sec import SecService
from backend.app.services.storage import StorageService

# When a ticker has fewer than this many indexed chunks at request time, the
# route fetches its latest 10-K + 10-Q and indexes them inline before calling
# the qualitative summary service. Same threshold the offline smoke script uses.
_AUTO_INDEX_MIN_CHUNKS = 5

logger = logging.getLogger(__name__)


router = APIRouter()
_relative_model_service = RelativeModelService.from_settings(get_settings())

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

    - Base snapshot comes from persisted Supabase rows (filings/financials).
    - On each GET, quotes are refreshed from yfinance before scoring and forecasts.
    - ``refresh=true`` reruns full SEC + market ingestion, then persists, then analyzes.
    """
    normalized_ticker = ticker.strip().upper()

    settings = get_settings()
    if not settings.has_supabase:
        raise HTTPException(
            status_code=404,
            detail=(
                "Supabase is required: set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY "
                "so analysis snapshots can be loaded and stored."
            ),
        )

    storage = StorageService(settings)
    loaded_from_storage = False

    if refresh:
        logger.info(
            "Full ingestion refresh requested for %s.",
            normalized_ticker,
        )
        try:
            result = await run_ingestion(normalized_ticker)
        except NotFoundError as error:
            raise HTTPException(status_code=404, detail=error.message) from error
        except AppError as error:
            raise _to_http_exception(error) from error
        analysis_input = result.analysis_input
    else:
        try:
            payload: dict[str, Any] = await storage.get_latest_analysis_input(
                normalized_ticker
            )
            analysis_input = AnalysisInput.model_validate(payload)
            loaded_from_storage = True
        except NotFoundError:
            logger.info(
                "No stored analysis for %s; running live ingestion.",
                normalized_ticker,
            )
            try:
                result = await run_ingestion(normalized_ticker)
            except NotFoundError as error:
                raise HTTPException(status_code=404, detail=error.message) from error
            except AppError as error:
                raise _to_http_exception(error) from error
            analysis_input = result.analysis_input
        except AppError as error:
            raise _to_http_exception(error) from error

    # Always serve current quotes + downstream outputs built from those quotes.
    # Skip redundant yfinance fetch when this row was just assembled by ingestion.
    if loaded_from_storage:
        try:
            analysis_input = await attach_fresh_market_snapshot(
                analysis_input, settings=settings
            )
        except AppError as error:
            raise _to_http_exception(error) from error

    response = run_analysis_pipeline(analysis_input, source="live")
    response.relative_performance = _resolve_relative_performance(
        ticker=response.ticker,
        sector=response.company.sector,
    )
    if settings.enable_qualitative_summary:
        response.document_summary = await _resolve_qualitative_summary(
            ticker=normalized_ticker,
            settings=settings,
        )
    return response


async def _resolve_qualitative_summary(*, ticker: str, settings: Any) -> Any:
    """Return a DocumentSummary or None on any failure (graceful degradation).

    Auto-index path: if the ticker has fewer than _AUTO_INDEX_MIN_CHUNKS
    indexed chunks (or no companies row at all), fetch its latest 10-K + 10-Q
    from SEC EDGAR and index them inline before summarizing. This makes the
    /analysis endpoint self-sufficient — a fresh ticker hits the endpoint,
    waits for indexing + summarization, and gets a fully populated response.

    Trade-off: first-request latency for a fresh ticker is on the order of
    30-90s (SEC fetch + chunking + embedding + LLM call). Subsequent requests
    hit the qualitative cache and the chunk index, and complete in seconds.
    """
    try:
        rag = RagService(settings)
        ollama = OllamaClient(settings)
        sec = SecService(settings)
        svc = QualitativeService(settings, rag, ollama)

        await _ensure_indexed_for_qualitative(ticker, rag=rag, sec=sec)
        return await svc.summarize(ticker)
    except Exception as exc:
        logger.warning("Qualitative summary unavailable for %s: %s", ticker, exc)
        return None


async def _ensure_indexed_for_qualitative(
    ticker: str, *, rag: RagService, sec: SecService
) -> None:
    """Ensure the ticker has a companies row and at least _AUTO_INDEX_MIN_CHUNKS
    indexed filing chunks. If not, fetch + index the latest 10-K and 10-Q.

    Best-effort: any partial indexing failure is logged and swallowed so the
    qualitative service still gets to attempt a summary on whatever was
    indexed successfully.
    """
    upper = ticker.upper()

    # Resolve or insert companies row.
    company_rows = (
        rag.client.table("companies")
        .select("id, cik")
        .eq("ticker", upper)
        .limit(1)
        .execute()
        .data
        or []
    )
    if company_rows:
        company_id = company_rows[0]["id"]
    else:
        snapshot = await sec.resolve_company(upper)
        inserted = (
            rag.client.table("companies")
            .insert(
                {
                    "ticker": snapshot.ticker,
                    "company_name": snapshot.company_name,
                    "cik": snapshot.cik,
                }
            )
            .execute()
            .data
        )
        company_id = inserted[0]["id"]

    # Skip if already indexed.
    chunk_count_resp = (
        rag.client.table("filing_chunks")
        .select("id", count="exact")
        .eq("company_id", company_id)
        .limit(1)
        .execute()
    )
    if (chunk_count_resp.count or 0) >= _AUTO_INDEX_MIN_CHUNKS:
        return

    # Fetch the latest 10-K + 10-Q + recent 8-Ks and index them.
    snapshot = await sec.resolve_company(upper)
    filings, _ = await sec.fetch_recent_filings(snapshot.cik)
    settings = get_settings()
    targets = (
        [f for f in filings if f.filing_type == "10-K"][:1]
        + [f for f in filings if f.filing_type == "10-Q"][:1]
        + [f for f in filings if f.filing_type == "8-K"][: settings.max_8k_per_ticker]
    )
    if not targets:
        targets = filings[:2]

    logger.info("Auto-indexing %d filing(s) for %s", len(targets), upper)
    for filing in targets:
        try:
            await rag.index_filing(company_id, filing)
        except Exception as exc:
            logger.warning(
                "Auto-index failed for %s %s: %s",
                upper,
                filing.accession_number,
                exc,
            )


def _resolve_relative_performance(*, ticker: str, sector: str | None) -> RelativePerformanceView:
    try:
        return _relative_model_service.get_relative_view(ticker=ticker, sector=sector)
    except Exception as error:
        # Keep core analysis endpoint healthy even if model artifacts are unavailable.
        detail = f"Relative model unavailable: {error}"
        return RelativePerformanceView(
            horizon_years=5,
            as_of=datetime.now(timezone.utc).date().isoformat(),
            gics_sector=sector,
            sector_etf=None,
            used_parent_etf=False,
            vs_spy=RelativeTercileEstimate(
                benchmark_ticker="SPY",
                tercile=None,
                score=None,
                methodology="unavailable",
                detail=detail,
            ),
            vs_sector=RelativeTercileEstimate(
                benchmark_ticker="UNKNOWN",
                tercile=None,
                score=None,
                methodology="unavailable",
                detail="Sector relative model unavailable.",
            ),
        )


@router.get("/peers/{ticker}", response_model=PeersResponse)
async def get_peers(ticker: str, refresh: bool = False) -> PeersResponse:
    """Return peer set and ranking context (same as embedded in `GET /analysis`)."""
    result = await _resolve_analysis(ticker, refresh=refresh)
    return PeersResponse(
        ticker=result.ticker,
        company_name=result.company.company_name,
        generated_at=result.generated_at,
        source=result.source,
        peers=result.peers,
        ranking_context=result.ranking_context,
    )


@router.get("/analysis/{ticker}", response_model=AnalysisResponse)
async def get_analysis(ticker: str, refresh: bool = False) -> AnalysisResponse:
    """Assemble analysis from persisted input plus freshly fetched market quotes.

    Pass ``?refresh=true`` to rerun full ingestion (SEC + market) before analysis.
    """
    return await _resolve_analysis(ticker, refresh=refresh)


@router.get("/analysis/{ticker}/relative-model", response_model=RelativePerformanceView)
async def get_relative_model_view(ticker: str, refresh: bool = False) -> RelativePerformanceView:
    analysis = await _resolve_analysis(ticker, refresh=refresh)
    if analysis.relative_performance is not None:
        return analysis.relative_performance
    return _resolve_relative_performance(ticker=analysis.ticker, sector=analysis.company.sector)


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
