from __future__ import annotations

from datetime import date, datetime, timezone
import unittest
from unittest.mock import AsyncMock, patch

from backend.app.config import Settings
from backend.app.errors import NotFoundError, PersistenceError, UpstreamServiceError
from backend.app.models import CompanySnapshot, FilingRecord, MarketDataSnapshot
from backend.app.services.ingestion import run_ingestion


def _settings(*, with_supabase: bool = True) -> Settings:
    return Settings(
        supabase_url="https://example.supabase.co" if with_supabase else None,
        supabase_service_role_key="service-role-key" if with_supabase else None,
        schema_version="v1",
    )


def _company() -> CompanySnapshot:
    return CompanySnapshot(
        ticker="AAPL",
        company_name="Apple Inc.",
        cik="0000320193",
    )


def _filing() -> FilingRecord:
    return FilingRecord(
        accession_number="0000320193-24-000123",
        filing_type="10-K",
        filing_date=date(2024, 11, 1),
        period_end=date(2024, 9, 28),
        filing_url="https://example.com/10k",
    )


def _market_snapshot() -> MarketDataSnapshot:
    return MarketDataSnapshot(
        as_of=datetime(2026, 1, 1, tzinfo=timezone.utc),
        price_usd=200.0,
        historical_prices=[180.0, 190.0, 200.0],
    )


class IngestionServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_run_ingestion_raises_when_no_supported_filings_are_found(self) -> None:
        with (
            patch("backend.app.services.ingestion.get_settings", return_value=_settings()),
            patch("backend.app.services.ingestion.SecService") as sec_cls,
            patch("backend.app.services.ingestion.MarketDataService"),
            patch("backend.app.services.ingestion.StorageService"),
        ):
            sec_instance = sec_cls.return_value
            sec_instance.resolve_company = AsyncMock(return_value=_company())
            sec_instance.fetch_recent_filings = AsyncMock(return_value=([], {"filings": {}}))

            with self.assertRaisesRegex(
                NotFoundError,
                "No supported SEC filings were found",
            ):
                await run_ingestion("AAPL")

    async def test_run_ingestion_returns_analysis_input_when_persistence_is_unavailable(self) -> None:
        with (
            patch(
                "backend.app.services.ingestion.get_settings",
                return_value=_settings(with_supabase=False),
            ),
            patch("backend.app.services.ingestion.SecService") as sec_cls,
            patch("backend.app.services.ingestion.MarketDataService") as market_cls,
            patch("backend.app.services.ingestion.StorageService") as storage_cls,
            patch("backend.app.services.ingestion.build_analysis_input") as build_analysis_input,
        ):
            sec_instance = sec_cls.return_value
            sec_instance.resolve_company = AsyncMock(return_value=_company())
            sec_instance.fetch_recent_filings = AsyncMock(
                return_value=([_filing()], {"filings": {}})
            )
            sec_instance.fetch_company_facts = AsyncMock(return_value={})

            market_instance = market_cls.return_value
            market_instance.fetch_market_snapshot = AsyncMock(
                return_value=(_market_snapshot(), _company(), {"financials": {}})
            )

            expected_analysis_input = build_analysis_input.return_value
            result = await run_ingestion("AAPL")

            self.assertIs(result.analysis_input, expected_analysis_input)
            storage_cls.return_value.persist_analysis_input.assert_not_called()

    async def test_run_ingestion_propagates_market_data_unavailable_errors(self) -> None:
        with (
            patch("backend.app.services.ingestion.get_settings", return_value=_settings()),
            patch("backend.app.services.ingestion.SecService") as sec_cls,
            patch("backend.app.services.ingestion.MarketDataService") as market_cls,
            patch("backend.app.services.ingestion.StorageService"),
        ):
            sec_instance = sec_cls.return_value
            sec_instance.resolve_company = AsyncMock(return_value=_company())
            sec_instance.fetch_recent_filings = AsyncMock(
                return_value=([_filing()], {"filings": {}})
            )

            market_cls.return_value.fetch_market_snapshot = AsyncMock(
                side_effect=UpstreamServiceError("No current price returned for 'AAPL'.")
            )

            with self.assertRaisesRegex(
                UpstreamServiceError,
                "No current price returned for 'AAPL'",
            ):
                await run_ingestion("AAPL")

    async def test_run_ingestion_continues_when_persist_raises_runtime_persistence_error(
        self,
    ) -> None:
        with (
            patch("backend.app.services.ingestion.get_settings", return_value=_settings()),
            patch("backend.app.services.ingestion.SecService") as sec_cls,
            patch("backend.app.services.ingestion.MarketDataService") as market_cls,
            patch("backend.app.services.ingestion.StorageService") as storage_cls,
            patch("backend.app.services.ingestion.build_analysis_input") as build_analysis_input,
        ):
            sec_instance = sec_cls.return_value
            sec_instance.resolve_company = AsyncMock(return_value=_company())
            sec_instance.fetch_recent_filings = AsyncMock(
                return_value=([_filing()], {"filings": {}})
            )
            sec_instance.fetch_company_facts = AsyncMock(return_value={})

            market_cls.return_value.fetch_market_snapshot = AsyncMock(
                return_value=(_market_snapshot(), _company(), {"financials": {}})
            )

            storage_cls.return_value.persist_analysis_input = AsyncMock(
                side_effect=PersistenceError("Supabase insert failed.")
            )

            expected_analysis_input = build_analysis_input.return_value
            result = await run_ingestion("AAPL")

            self.assertIs(result.analysis_input, expected_analysis_input)


if __name__ == "__main__":
    unittest.main()
