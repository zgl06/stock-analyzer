from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, patch

import httpx

from backend.app.config import Settings
from backend.app.errors import NotFoundError, UpstreamServiceError
from backend.app.services.sec import SecService


class SecServiceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        SecService._ticker_mapping_cache = None
        self.settings = Settings(
            sec_user_agent="test-agent",
            sec_ticker_mapping_url="https://www.sec.gov/files/company_tickers.json",
            sec_submissions_base_url="https://data.sec.gov",
            sec_archives_base_url="https://www.sec.gov",
        )
        self.service = SecService(self.settings)

    async def test_resolve_company_returns_normalized_snapshot(self) -> None:
        self.service._fetch_ticker_mapping = AsyncMock(
            return_value={
                "0": {"ticker": "AAPL", "title": "Apple Inc.", "cik_str": 320193},
            }
        )

        company = await self.service.resolve_company("  aapl ")

        self.assertEqual(company.ticker, "AAPL")
        self.assertEqual(company.company_name, "Apple Inc.")
        self.assertEqual(company.cik, "0000320193")
        self.assertIsNone(company.exchange)
        self.assertIsNone(company.sector)

    async def test_resolve_company_raises_not_found_for_unknown_ticker(self) -> None:
        self.service._fetch_ticker_mapping = AsyncMock(return_value={})

        with self.assertRaises(NotFoundError):
            await self.service.resolve_company("MISSING")

    async def test_fetch_recent_filings_filters_and_normalizes_records(self) -> None:
        self.service._fetch_company_submissions = AsyncMock(
            return_value={
                "filings": {
                    "recent": {
                        "form": ["10-K", "8-K", "8-K", "10-Q"],
                        "accessionNumber": [
                            "0000320193-24-000123",
                            "0000320193-25-000001",
                            "0000320193-25-000002",
                            "0000320193-25-000073",
                        ],
                        "filingDate": ["2024-11-01", "2025-01-01", "2025-01-02", "2025-02-01"],
                        "reportDate": ["2024-09-28", "", None, "2024-12-28"],
                        "primaryDocument": ["aapl10k.htm", "item202.htm", "", "aapl10q.htm"],
                        "primaryDocDescription": ["Annual report", "Press release", "", None],
                        "items": ["", "2.02, 9.01", "1.01", []],
                    }
                }
            }
        )

        filings, raw = await self.service.fetch_recent_filings("0000320193")

        self.assertEqual(len(filings), 3)
        self.assertEqual([filing.filing_type for filing in filings], ["10-K", "8-K", "10-Q"])
        self.assertEqual(filings[0].period_end.isoformat(), "2024-09-28")
        self.assertIsNone(filings[1].period_end)
        self.assertEqual(filings[1].items, ["2.02", "9.01"])
        self.assertEqual(
            filings[1].filing_url,
            "https://www.sec.gov/Archives/edgar/data/320193/000032019325000001/0000320193-25-000001-index.htm",
        )
        self.assertEqual(
            filings[2].primary_document_url,
            "https://www.sec.gov/Archives/edgar/data/320193/000032019325000073/aapl10q.htm",
        )
        self.assertIn("filings", raw)

    async def test_fetch_recent_filings_handles_missing_recent_shape(self) -> None:
        self.service._fetch_company_submissions = AsyncMock(return_value={"filings": {}})

        filings, _ = await self.service.fetch_recent_filings("320193")

        self.assertEqual(filings, [])

    async def test_get_json_maps_404_to_not_found(self) -> None:
        request = httpx.Request("GET", "https://example.com")
        response = httpx.Response(404, request=request)
        error = httpx.HTTPStatusError("not found", request=request, response=response)

        with self._mock_async_client(get_side_effect=error):
            with self.assertRaises(NotFoundError):
                await self.service._get_json("https://example.com")

    async def test_get_json_maps_non_404_to_upstream_error(self) -> None:
        request = httpx.Request("GET", "https://example.com")
        response = httpx.Response(500, request=request)
        error = httpx.HTTPStatusError("server error", request=request, response=response)

        with self._mock_async_client(get_side_effect=error):
            with self.assertRaises(UpstreamServiceError):
                await self.service._get_json("https://example.com")

    async def test_get_json_maps_invalid_json_to_upstream_error(self) -> None:
        request = httpx.Request("GET", "https://example.com")
        response = httpx.Response(200, request=request, content=b"not-json")

        with self._mock_async_client(response=response):
            with self.assertRaises(UpstreamServiceError):
                await self.service._get_json("https://example.com")

    async def test_fetch_ticker_mapping_uses_in_process_cache(self) -> None:
        self.service._get_json = AsyncMock(return_value={"0": {"ticker": "AAPL"}})

        first = await self.service._fetch_ticker_mapping()
        second = await self.service._fetch_ticker_mapping()

        self.assertEqual(first, second)
        self.service._get_json.assert_awaited_once()

    def _mock_async_client(
        self,
        *,
        response: httpx.Response | None = None,
        get_side_effect: Exception | None = None,
    ):
        client = AsyncMock()
        if get_side_effect is not None:
            client.get.side_effect = get_side_effect
        else:
            client.get.return_value = response

        context_manager = AsyncMock()
        context_manager.__aenter__.return_value = client
        context_manager.__aexit__.return_value = False
        return patch("backend.app.services.sec.httpx.AsyncClient", return_value=context_manager)


if __name__ == "__main__":
    unittest.main()
