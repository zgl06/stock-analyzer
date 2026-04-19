from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import httpx

from backend.app.config import Settings
from backend.app.errors import NotFoundError, UpstreamServiceError
from backend.app.models import CompanySnapshot, FilingRecord


SUPPORTED_FILING_TYPES = {"10-K", "10-Q", "8-K"}
RELEVANT_8K_ITEMS = {"2.02", "7.01", "8.01", "9.01"}


class SecService:
    _ticker_mapping_cache: dict[str, Any] | None = None

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.headers = {
            "User-Agent": settings.sec_user_agent,
            "Accept-Encoding": "gzip, deflate",
            "Accept": "application/json",
        }

    async def resolve_company(self, ticker: str) -> CompanySnapshot:
        normalized_ticker = ticker.strip().upper()
        mapping = await self._fetch_ticker_mapping()
        entry = next(
            (
                item
                for item in mapping.values()
                if str(item.get("ticker", "")).strip().upper() == normalized_ticker
            ),
            None,
        )
        if not entry:
            raise NotFoundError(
                f"Ticker '{normalized_ticker or ticker}' was not found in SEC mappings."
            )

        cik = str(entry["cik_str"]).strip().zfill(10)
        return CompanySnapshot(
            ticker=normalized_ticker,
            company_name=str(entry["title"]).strip(),
            cik=cik,
        )

    async def fetch_recent_filings(self, cik: str) -> tuple[list[FilingRecord], dict[str, Any]]:
        normalized_cik = str(int(str(cik).strip())).zfill(10)
        submissions = await self._fetch_company_submissions(normalized_cik)
        recent = self._recent_filings_payload(submissions)
        forms = self._coerce_list(recent.get("form"))
        accession_numbers = self._coerce_list(recent.get("accessionNumber"))
        filing_dates = self._coerce_list(recent.get("filingDate"))
        report_dates = self._coerce_list(recent.get("reportDate"))
        primary_documents = self._coerce_list(recent.get("primaryDocument"))
        primary_doc_descriptions = self._coerce_list(recent.get("primaryDocDescription"))
        items_list = self._coerce_list(recent.get("items"))

        filings: list[FilingRecord] = []
        for index, form in enumerate(forms):
            normalized_form = str(form).strip()
            if normalized_form not in SUPPORTED_FILING_TYPES:
                continue

            raw_items = self._split_items(items_list, index)
            if normalized_form == "8-K" and raw_items and not any(
                item in RELEVANT_8K_ITEMS for item in raw_items
            ):
                continue

            accession_number = self._optional_string(accession_numbers, index)
            filing_date = self._optional_string(filing_dates, index)
            if not accession_number or not filing_date:
                continue

            accession_without_dashes = accession_number.replace("-", "")
            primary_document = self._optional_string(primary_documents, index)
            filing_url = (
                f"{self.settings.sec_archives_base_url}/Archives/edgar/data/"
                f"{int(normalized_cik)}/{accession_without_dashes}/{accession_number}-index.htm"
            )
            primary_document_url = (
                f"{self.settings.sec_archives_base_url}/Archives/edgar/data/"
                f"{int(normalized_cik)}/{accession_without_dashes}/{primary_document}"
                if primary_document
                else None
            )

            filings.append(
                FilingRecord(
                    accession_number=accession_number,
                    filing_type=normalized_form,
                    filing_date=filing_date,
                    period_end=self._optional_string(report_dates, index),
                    filing_url=filing_url,
                    primary_document_url=primary_document_url,
                    description=self._optional_string(primary_doc_descriptions, index),
                    items=raw_items,
                )
            )

        return filings, submissions

    async def _fetch_ticker_mapping(self) -> dict[str, Any]:
        if self.__class__._ticker_mapping_cache is None:
            self.__class__._ticker_mapping_cache = await self._get_json(
                self.settings.sec_ticker_mapping_url
            )
        return self.__class__._ticker_mapping_cache

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

    @staticmethod
    def _recent_filings_payload(submissions: dict[str, Any]) -> Mapping[str, Any]:
        filings = submissions.get("filings")
        if not isinstance(filings, Mapping):
            return {}
        recent = filings.get("recent")
        if not isinstance(recent, Mapping):
            return {}
        return recent

    @staticmethod
    def _coerce_list(value: Any) -> list[Any]:
        return value if isinstance(value, list) else []

    @staticmethod
    def _optional_string(values: list[Any], index: int) -> str | None:
        if index >= len(values):
            return None
        value = values[index]
        if value is None:
            return None
        cleaned = str(value).strip()
        return cleaned or None
