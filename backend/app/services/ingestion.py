from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from backend.app.config import get_settings
from backend.app.errors import AppError, NotFoundError, PersistenceError
from backend.app.models import AnalysisInput
from backend.app.services.market_data import MarketDataService
from backend.app.services.normalize import build_analysis_input
from backend.app.services.sec import SecService
from backend.app.services.sec_facts import extract_period_metrics
from backend.app.services.storage import StorageService


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class IngestionResult:
    generated_at: datetime
    analysis_input: AnalysisInput


async def run_ingestion(ticker: str) -> IngestionResult:
    settings = get_settings()
    sec_service = SecService(settings)
    market_service = MarketDataService(settings)
    storage = StorageService(settings)

    company = await sec_service.resolve_company(ticker)
    filings, raw_filings_payload = await sec_service.fetch_recent_filings(company.cik)
    if not filings:
        raise NotFoundError(
            f"No supported SEC filings were found for ticker '{company.ticker}'."
        )

    market_data, company, market_raw_payload = await market_service.fetch_market_snapshot(
        ticker,
        company,
    )

    sec_period_metrics: dict = {}
    try:
        company_facts = await sec_service.fetch_company_facts(company.cik)
        sec_period_metrics = extract_period_metrics(company_facts)
    except AppError as error:
        logger.info(
            "SEC companyfacts fetch failed for %s (cik=%s): %s; "
            "continuing with yfinance only.",
            company.ticker,
            company.cik,
            error.message,
        )

    analysis_input = build_analysis_input(
        company=company,
        filings=filings,
        market_data=market_data,
        market_raw_payload=market_raw_payload,
        sec_period_metrics=sec_period_metrics,
    )
    generated_at = datetime.now(timezone.utc)

    if not settings.has_supabase:
        logger.info(
            "Skipping persistence for %s because Supabase is not configured.",
            analysis_input.company.ticker,
        )
    else:
        try:
            await storage.persist_analysis_input(
                company=analysis_input.company,
                filings=analysis_input.filings,
                raw_filings_payload=raw_filings_payload,
                market_raw_payload=market_raw_payload,
                analysis_input=analysis_input,
                generated_at=generated_at,
                schema_version=settings.schema_version,
            )
        except PersistenceError as error:
            logger.warning(
                "Persistence unavailable for %s: %s",
                analysis_input.company.ticker,
                error.message,
            )

    return IngestionResult(
        generated_at=generated_at,
        analysis_input=analysis_input,
    )
