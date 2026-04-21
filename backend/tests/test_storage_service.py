from __future__ import annotations

from datetime import date, datetime, timezone
from types import SimpleNamespace
import unittest

from backend.app.config import Settings
from backend.app.models import (
    AnalysisInput,
    CompanySnapshot,
    FilingRecord,
    FinancialPeriod,
    MarketDataSnapshot,
    NormalizedFinancials,
)
from backend.app.services.storage import StorageService


def _company() -> CompanySnapshot:
    return CompanySnapshot(
        ticker="AAPL",
        company_name="Apple Inc.",
        cik="0000320193",
    )


def _market_data() -> MarketDataSnapshot:
    return MarketDataSnapshot(
        as_of=datetime(2026, 1, 1, tzinfo=timezone.utc),
        price_usd=200.0,
        historical_prices=[180.0, 190.0, 200.0],
    )


def _analysis_input() -> AnalysisInput:
    return AnalysisInput(
        company=_company(),
        financials=NormalizedFinancials(
            reporting_basis="annual_plus_ttm",
            latest_fiscal_year=2025,
            latest_fiscal_period="TTM",
            periods=[
                FinancialPeriod(
                    period_end=date(2024, 9, 28),
                    fiscal_year=2024,
                    fiscal_period="FY",
                    revenue_usd=391_000_000_000.0,
                    net_income_usd=97_000_000_000.0,
                ),
                FinancialPeriod(
                    period_end=date(2025, 6, 28),
                    fiscal_year=2025,
                    fiscal_period="TTM",
                    revenue_usd=405_000_000_000.0,
                    net_income_usd=103_000_000_000.0,
                ),
            ],
        ),
        filings=[
            FilingRecord(
                accession_number="0000320193-24-000123",
                filing_type="10-K",
                filing_date=date(2024, 11, 1),
                period_end=date(2024, 9, 28),
                filing_url="https://example.com/10k",
            ),
            FilingRecord(
                accession_number="0000320193-25-000073",
                filing_type="10-Q",
                filing_date=date(2025, 8, 1),
                period_end=date(2025, 6, 28),
                filing_url="https://example.com/10q",
            ),
        ],
        marketData=_market_data(),
    )


class _FakeTable:
    def __init__(self, name: str, client: "_FakeClient") -> None:
        self.name = name
        self.client = client
        self.operation = "select"
        self.payload = None
        self.filters: list[tuple[str, object]] = []

    def upsert(self, payload, on_conflict=None):
        self.operation = "upsert"
        self.payload = payload
        return self

    def insert(self, payload):
        self.operation = "insert"
        self.payload = payload
        return self

    def update(self, payload):
        self.operation = "update"
        self.payload = payload
        return self

    def select(self, *_args):
        self.operation = "select"
        return self

    def eq(self, key, value):
        self.filters.append((key, value))
        return self

    def order(self, *_args, **_kwargs):
        return self

    def limit(self, _value):
        return self

    def execute(self):
        if self.name == "companies":
            if self.operation == "upsert":
                return SimpleNamespace(data=[{"id": "company-1", **self.payload}])
            return SimpleNamespace(data=[{"id": "company-1"}])

        if self.name == "normalized_financial_periods" and self.operation == "upsert":
            self.client.normalized_rows.append(self.payload)
            return SimpleNamespace(data=[self.payload])

        if self.name == "analysis_inputs":
            if self.operation == "insert":
                self.client.latest_analysis_input = self.payload["input_payload"]
                return SimpleNamespace(data=[self.payload])
            if self.operation == "select":
                payload = self.client.latest_analysis_input
                return SimpleNamespace(data=[{"input_payload": payload}] if payload else [])
            return SimpleNamespace(data=[])

        return SimpleNamespace(data=[self.payload] if self.payload is not None else [])


class _FakeClient:
    def __init__(self) -> None:
        self.normalized_rows: list[dict] = []
        self.latest_analysis_input: dict | None = None

    def table(self, name: str) -> _FakeTable:
        return _FakeTable(name, self)


class StorageServiceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        settings = Settings(
            supabase_url="https://example.supabase.co",
            supabase_service_role_key="service-role-key",
        )
        self.service = StorageService(settings)
        self.fake_client = _FakeClient()
        self.service._client = self.fake_client

    def test_match_source_accession_uses_exact_fy_match_and_latest_ttm_covering_filing(
        self,
    ) -> None:
        filings = _analysis_input().filings

        self.assertEqual(
            StorageService._match_source_accession(
                period_end=date(2024, 9, 28),
                fiscal_period="FY",
                filings=filings,
            ),
            "0000320193-24-000123",
        )
        self.assertEqual(
            StorageService._match_source_accession(
                period_end=date(2025, 6, 28),
                fiscal_period="TTM",
                filings=filings,
            ),
            "0000320193-25-000073",
        )

    async def test_analysis_input_round_trips_through_storage_read_path(self) -> None:
        analysis_input = _analysis_input()

        self.service._replace_latest_analysis_input(
            "company-1",
            analysis_input.model_dump(by_alias=True, mode="json"),
            datetime(2026, 1, 1, tzinfo=timezone.utc),
            "v1",
        )

        payload = await self.service.get_latest_analysis_input("AAPL")
        restored = AnalysisInput.model_validate(payload)

        self.assertEqual(
            restored.model_dump(by_alias=True, mode="json"),
            analysis_input.model_dump(by_alias=True, mode="json"),
        )

    def test_upsert_normalized_periods_persists_best_effort_source_accessions(self) -> None:
        analysis_input = _analysis_input()

        self.service._upsert_normalized_periods(
            "company-1",
            analysis_input.financials,
            analysis_input.filings,
        )

        accessions = [row["source_filing_accession"] for row in self.fake_client.normalized_rows]
        self.assertEqual(
            accessions,
            [
                "0000320193-24-000123",
                "0000320193-25-000073",
            ],
        )


if __name__ == "__main__":
    unittest.main()
