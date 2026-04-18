from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from backend.app.config import get_settings
from backend.app.models import AnalysisInput
from backend.app.services.market_data import MarketDataService
from backend.app.services.normalize import build_analysis_input
from backend.app.services.sec import SecService
from backend.app.services.storage import StorageService


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
    market_data, company, market_raw_payload = await market_service.fetch_market_snapshot(
        ticker,
        company,
    )

    analysis_input = build_analysis_input(
        company=company,
        filings=filings,
        market_data=market_data,
        market_raw_payload=market_raw_payload,
    )
    generated_at = datetime.now(timezone.utc)

    await storage.persist_analysis_input(
        company=analysis_input.company,
        filings=analysis_input.filings,
        raw_filings_payload=raw_filings_payload,
        market_raw_payload=market_raw_payload,
        analysis_input=analysis_input,
        generated_at=generated_at,
        schema_version=settings.schema_version,
    )

    return IngestionResult(
        generated_at=generated_at,
        analysis_input=analysis_input,
    )
