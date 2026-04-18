from __future__ import annotations

from typing import Any

import httpx

from backend.app.config import Settings
from backend.app.errors import NotFoundError, UpstreamServiceError
from backend.app.models import CompanySnapshot, FilingRecord


SUPPORTED_FILING_TYPES = {"10-K", "10-Q", "8-K"}
RELEVANT_8K_ITEMS = {"2.02", "7.01", "8.01", "9.01"}


class SecService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.headers = {
            "User-Agent": settings.sec_user_agent,
            "Accept-Encoding": "gzip, deflate",
            "Accept": "application/json",
        }

    async def resolve_company(self, ticker: str) -> CompanySnapshot:
        mapping = await self._fetch_ticker_mapping()
        entry = next(
            (
                item
                for item in mapping.values()
                if str(item.get("ticker", "")).upper() == ticker.upper()
            ),
            None,
        )
        if not entry:
            raise NotFoundError(f"Ticker '{ticker}' was not found in SEC mappings.")

        cik = str(entry["cik_str"]).zfill(10)
        return CompanySnapshot(
            ticker=ticker.upper(),
            company_name=entry["title"],
            cik=cik,
        )

    async def fetch_recent_filings(self, cik: str) -> tuple[list[FilingRecord], dict[str, Any]]:
        submissions = await self._fetch_company_submissions(cik)
        recent = submissions.get("filings", {}).get("recent", {})
        forms = recent.get("form", [])
        accession_numbers = recent.get("accessionNumber", [])
        filing_dates = recent.get("filingDate", [])
        report_dates = recent.get("reportDate", [])
        primary_documents = recent.get("primaryDocument", [])
        primary_doc_descriptions = recent.get("primaryDocDescription", [])
        items_list = recent.get("items", [])

        filings: list[FilingRecord] = []
        for index, form in enumerate(forms):
            if form not in SUPPORTED_FILING_TYPES:
                continue

            raw_items = self._split_items(items_list, index)
            if form == "8-K" and raw_items and not any(
                item in RELEVANT_8K_ITEMS for item in raw_items
            ):
                continue

            accession_number = accession_numbers[index]
            accession_without_dashes = accession_number.replace("-", "")
            primary_document = primary_documents[index] if index < len(primary_documents) else None
            filing_url = (
                f"{self.settings.sec_archives_base_url}/Archives/edgar/data/"
                f"{int(cik)}/{accession_without_dashes}/{accession_number}-index.htm"
            )
            primary_document_url = (
                f"{self.settings.sec_archives_base_url}/Archives/edgar/data/"
                f"{int(cik)}/{accession_without_dashes}/{primary_document}"
                if primary_document
                else None
            )

            filings.append(
                FilingRecord(
                    accession_number=accession_number,
                    filing_type=form,
                    filing_date=filing_dates[index],
                    period_end=report_dates[index] or None,
                    filing_url=filing_url,
                    primary_document_url=primary_document_url,
                    description=(
                        primary_doc_descriptions[index]
                        if index < len(primary_doc_descriptions)
                        else None
                    ),
                    items=raw_items,
                )
            )

        return filings, submissions

    async def _fetch_ticker_mapping(self) -> dict[str, Any]:
        return await self._get_json(self.settings.sec_ticker_mapping_url)

    async def _fetch_company_submissions(self, cik: str) -> dict[str, Any]:
        submissions_url = (
            f"{self.settings.sec_submissions_base_url}/submissions/CIK{cik}.json"
        )
        return await self._get_json(submissions_url)

    async def _get_json(self, url: str) -> dict[str, Any]:
        timeout = httpx.Timeout(20.0, connect=10.0)
        async with httpx.AsyncClient(headers=self.headers, timeout=timeout) as client:
            try:
                response = await client.get(url)
                response.raise_for_status()
            except httpx.HTTPStatusError as error:
                if error.response.status_code == 404:
                    raise NotFoundError(f"SEC resource not found: {url}") from error
                raise UpstreamServiceError(
                    f"SEC request failed with status {error.response.status_code}."
                ) from error
            except httpx.HTTPError as error:
                raise UpstreamServiceError("SEC request failed.") from error

        try:
            return response.json()
        except ValueError as error:
            raise UpstreamServiceError("SEC returned invalid JSON.") from error

    @staticmethod
    def _split_items(items_list: list[Any], index: int) -> list[str]:
        if index >= len(items_list):
            return []
        raw = items_list[index]
        if raw in (None, ""):
            return []
        if isinstance(raw, list):
            return [str(item).strip() for item in raw if str(item).strip()]
        return [part.strip() for part in str(raw).split(",") if part.strip()]
