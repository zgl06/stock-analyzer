from __future__ import annotations

import asyncio
from datetime import datetime
import math
from typing import Any

from supabase import Client, create_client

from backend.app.config import Settings
from backend.app.errors import NotFoundError, PersistenceError
from backend.app.models import AnalysisInput, CompanySnapshot, FilingRecord, NormalizedFinancials


class StorageService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._client: Client | None = None

    async def check_health(self) -> bool:
        if not self.settings.has_supabase:
            return False

        try:
            await asyncio.to_thread(
                lambda: self.client.table("companies").select("id").limit(1).execute()
            )
        except Exception:
            return False
        return True

    async def persist_analysis_input(
        self,
        *,
        company: CompanySnapshot,
        filings: list[FilingRecord],
        raw_filings_payload: dict[str, Any],
        market_raw_payload: dict[str, Any],
        analysis_input: AnalysisInput,
        generated_at: datetime,
        schema_version: str,
    ) -> None:
        if not self.settings.has_supabase:
            raise PersistenceError("Supabase is not configured.")

        company_row = await asyncio.to_thread(self._upsert_company, company)
        company_id = company_row["id"]

        await asyncio.to_thread(self._upsert_filings, company_id, filings, raw_filings_payload)
        await asyncio.to_thread(self._insert_raw_market_data, company_id, market_raw_payload, generated_at)
        await asyncio.to_thread(
            self._upsert_normalized_periods,
            company_id,
            analysis_input.financials,
            filings,
        )
        await asyncio.to_thread(
            self._insert_market_snapshot,
            company_id,
            analysis_input.market_data.model_dump(mode="json"),
        )
        await asyncio.to_thread(
            self._replace_latest_analysis_input,
            company_id,
            analysis_input.model_dump(by_alias=True, mode="json"),
            generated_at,
            schema_version,
        )

    async def get_latest_analysis_input(self, ticker: str) -> dict[str, Any]:
        if not self.settings.has_supabase:
            raise PersistenceError("Supabase is not configured.")

        companies_response = await asyncio.to_thread(
            lambda: self.client.table("companies")
            .select("id")
            .eq("ticker", ticker.upper())
            .limit(1)
            .execute()
        )
        companies = companies_response.data or []
        if not companies:
            raise NotFoundError(f"No company has been stored for ticker '{ticker}'.")

        company_id = companies[0]["id"]
        response = await asyncio.to_thread(
            lambda: self.client.table("analysis_inputs")
            .select("input_payload")
            .eq("company_id", company_id)
            .eq("is_latest", True)
            .order("generated_at", desc=True)
            .limit(1)
            .execute()
        )

        rows = response.data or []
        if not rows:
            raise NotFoundError(f"No analysis input has been stored for ticker '{ticker}'.")
        return rows[0]["input_payload"]

    @property
    def client(self) -> Client:
        if self._client is None:
            if not self.settings.has_supabase:
                raise PersistenceError("Supabase is not configured.")
            self._client = create_client(
                self.settings.supabase_url,
                self.settings.supabase_service_role_key,
            )
        return self._client

    def _upsert_company(self, company: CompanySnapshot) -> dict[str, Any]:
        payload = company.model_dump(mode="json")
        payload = self._sanitize_json_value(payload)
        response = (
            self.client.table("companies")
            .upsert(payload, on_conflict="ticker")
            .execute()
        )
        rows = response.data or []
        if not rows:
            raise PersistenceError("Failed to upsert company row.")
        return rows[0]

    def _upsert_filings(
        self,
        company_id: str,
        filings: list[FilingRecord],
        raw_filings_payload: dict[str, Any],
    ) -> None:
        for filing in filings:
            payload = {
                "company_id": company_id,
                **filing.model_dump(mode="json"),
                "raw_payload": raw_filings_payload,
            }
            payload = self._sanitize_json_value(payload)
            self.client.table("raw_filings").upsert(
                payload,
                on_conflict="accession_number",
            ).execute()

    def _insert_raw_market_data(
        self,
        company_id: str,
        market_raw_payload: dict[str, Any],
        generated_at: datetime,
    ) -> None:
        payload = {
            "company_id": company_id,
            "provider": market_raw_payload.get("provider", "yfinance"),
            "as_of": generated_at.isoformat(),
            "raw_payload": market_raw_payload,
        }
        payload = self._sanitize_json_value(payload)
        self.client.table("raw_market_data").insert(payload).execute()

    def _insert_market_snapshot(self, company_id: str, snapshot: dict[str, Any]) -> None:
        payload = {
            "company_id": company_id,
            **snapshot,
        }
        payload = self._sanitize_json_value(payload)
        self.client.table("market_data_snapshots").insert(payload).execute()

    def _upsert_normalized_periods(
        self,
        company_id: str,
        financials: NormalizedFinancials,
        filings: list[FilingRecord],
    ) -> None:
        source_accession = filings[0].accession_number if filings else None
        for period in financials.periods:
            payload = {
                "company_id": company_id,
                "reporting_basis": financials.reporting_basis,
                "source_filing_accession": source_accession,
                **period.model_dump(mode="json"),
            }
            payload = self._sanitize_json_value(payload)
            self.client.table("normalized_financial_periods").upsert(
                payload,
                on_conflict="company_id,period_end,fiscal_period",
            ).execute()

    def _replace_latest_analysis_input(
        self,
        company_id: str,
        input_payload: dict[str, Any],
        generated_at: datetime,
        schema_version: str,
    ) -> None:
        self.client.table("analysis_inputs").update({"is_latest": False}).eq(
            "company_id",
            company_id,
        ).eq("is_latest", True).execute()

        self.client.table("analysis_inputs").insert(
            self._sanitize_json_value({
                "company_id": company_id,
                "generated_at": generated_at.isoformat(),
                "schema_version": schema_version,
                "input_payload": input_payload,
                "is_latest": True,
            })
        ).execute()

    def _sanitize_json_value(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {key: self._sanitize_json_value(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self._sanitize_json_value(item) for item in value]
        if isinstance(value, tuple):
            return [self._sanitize_json_value(item) for item in value]
        if isinstance(value, float):
            return value if math.isfinite(value) else None
        return value
