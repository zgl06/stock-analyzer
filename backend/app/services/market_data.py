from __future__ import annotations

import asyncio
import math
from datetime import datetime, timezone
from typing import Any

import yfinance as yf

from backend.app.config import Settings
from backend.app.errors import UpstreamServiceError
from backend.app.models import CompanySnapshot, MarketDataSnapshot


class MarketDataService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def fetch_market_snapshot(
        self,
        ticker: str,
        company: CompanySnapshot,
    ) -> tuple[MarketDataSnapshot, CompanySnapshot, dict[str, Any]]:
        try:
            raw = await asyncio.to_thread(self._load_yfinance_payload, ticker)
        except Exception as error:  # pragma: no cover - network/provider errors are runtime only
            raise UpstreamServiceError(
                f"Market data request for '{ticker}' failed."
            ) from error

        info = raw["info"]
        history = raw["history"]
        fast_info = raw["fast_info"]

        price = self._coalesce(
            fast_info.get("lastPrice"),
            info.get("currentPrice"),
            info.get("regularMarketPrice"),
        )
        if price is None:
            raise UpstreamServiceError(f"No current price returned for '{ticker}'.")

        market_snapshot = MarketDataSnapshot(
            as_of=datetime.now(timezone.utc),
            price_usd=float(price),
            market_cap_usd=self._to_float(
                self._coalesce(fast_info.get("marketCap"), info.get("marketCap"))
            ),
            enterprise_value_usd=self._to_float(info.get("enterpriseValue")),
            price_to_earnings=self._to_float(info.get("trailingPE")),
            price_to_sales=self._to_float(info.get("priceToSalesTrailing12Months")),
            dividend_yield=self._normalize_dividend_yield(
                info.get("dividendYield")
            ),
            fifty_two_week_high_usd=self._to_float(
                self._coalesce(fast_info.get("yearHigh"), info.get("fiftyTwoWeekHigh"))
            ),
            fifty_two_week_low_usd=self._to_float(
                self._coalesce(fast_info.get("yearLow"), info.get("fiftyTwoWeekLow"))
            ),
            historical_prices=history,
        )

        enriched_company = company.model_copy(
            update={
                "exchange": company.exchange or info.get("exchange"),
                "sector": company.sector or info.get("sector"),
                "industry": company.industry or info.get("industry"),
                "country": company.country or info.get("country"),
                "website": company.website or info.get("website"),
            }
        )

        return market_snapshot, enriched_company, raw

    def _load_yfinance_payload(self, ticker: str) -> dict[str, Any]:
        stock = yf.Ticker(ticker)
        info = stock.info or {}
        fast_info = self._to_dict(getattr(stock, "fast_info", {}))
        history_df = stock.history(
            period=self.settings.yfinance_history_period,
            interval=self.settings.yfinance_history_interval,
            auto_adjust=True,
        )

        history: list[float] = []
        if history_df is not None and not history_df.empty:
            close_series = history_df["Close"].dropna().tolist()
            history = [
                float(value)
                for value in close_series
                if self._to_float(value) is not None
            ]

        financials = {
            "income_stmt": self._dataframe_to_records(getattr(stock, "income_stmt", None)),
            "quarterly_income_stmt": self._dataframe_to_records(
                getattr(stock, "quarterly_income_stmt", None)
            ),
            "balance_sheet": self._dataframe_to_records(getattr(stock, "balance_sheet", None)),
            "quarterly_balance_sheet": self._dataframe_to_records(
                getattr(stock, "quarterly_balance_sheet", None)
            ),
            "cashflow": self._dataframe_to_records(getattr(stock, "cashflow", None)),
            "quarterly_cashflow": self._dataframe_to_records(
                getattr(stock, "quarterly_cashflow", None)
            ),
        }

        return {
            "provider": "yfinance",
            "ticker": ticker.upper(),
            "info": info,
            "fast_info": fast_info,
            "history": history,
            "financials": financials,
        }

    @staticmethod
    def _dataframe_to_records(frame: Any) -> list[dict[str, Any]]:
        if frame is None:
            return []
        try:
            if frame.empty:
                return []
            normalized = frame.transpose().where(frame.transpose().notna(), None)
            records = normalized.reset_index().to_dict(orient="records")
        except Exception:
            return []

        serialized: list[dict[str, Any]] = []
        for record in records:
            output: dict[str, Any] = {}
            for key, value in record.items():
                if hasattr(value, "isoformat"):
                    output[str(key)] = value.isoformat()
                elif isinstance(value, (int, float, str, bool)) or value is None:
                    output[str(key)] = (
                        value
                        if not isinstance(value, float) or math.isfinite(value)
                        else None
                    )
                else:
                    output[str(key)] = str(value)
            serialized.append(output)
        return serialized

    @staticmethod
    def _to_dict(data: Any) -> dict[str, Any]:
        try:
            return dict(data)
        except Exception:
            return {}

    @staticmethod
    def _coalesce(*values: Any) -> Any:
        for value in values:
            if value is not None:
                return value
        return None

    @staticmethod
    def _to_float(value: Any) -> float | None:
        if value is None:
            return None
        try:
            result = float(value)
        except (TypeError, ValueError):
            return None
        if not math.isfinite(result):
            return None
        return result

    @classmethod
    def _normalize_dividend_yield(cls, value: Any) -> float | None:
        """Return a fractional yield (0.0086 = 0.86%).

        Modern yfinance returns ``info["dividendYield"]`` in percent form
        (e.g. ``0.86`` meaning 0.86%, ``7.2`` meaning 7.2%). The frontend
        formatter multiplies by 100, so we divide here to keep the stored
        value as a fraction. Values above 50 are treated as already
        fractional (paranoid guard for legacy yfinance payloads that
        returned 0.0086-style fractions -- extremely uncommon now).
        """
        result = cls._to_float(value)
        if result is None or not math.isfinite(result):
            return None
        if result < 0:
            return None
        # Reasonable dividend yields are 0-15%. Anything that looks like
        # it was already a fraction (>50, which would be absurd as percent)
        # we pass through. Everything else is treated as a percent value.
        if result > 50.0:
            return None
        return result / 100.0
