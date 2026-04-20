"""Unit tests for industry-based peer selection."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from backend.app.analysis import peers as peers_module
from backend.app.analysis.peers import (
    INDUSTRY_PEERS,
    MAX_PEERS,
    select_peers,
)
from backend.app.models import (
    AnalysisInput,
    CompanySnapshot,
    FinancialPeriod,
    MarketDataSnapshot,
    NormalizedFinancials,
    PeerComparison,
)


def _make_input(
    *,
    ticker: str,
    industry: str | None,
    sector: str | None,
    market_cap: float | None,
) -> AnalysisInput:
    company = CompanySnapshot(
        ticker=ticker,
        company_name=f"{ticker} Inc.",
        cik="0000000000",
        exchange="NMS",
        sector=sector,
        industry=industry,
        currency="USD",
        country="United States",
    )
    period = FinancialPeriod(
        fiscal_year=2024,
        fiscal_period="FY",
        period_end=datetime(2024, 9, 30, tzinfo=timezone.utc).date(),
        revenue_usd=100_000_000_000,
        net_income_usd=20_000_000_000,
        diluted_eps=5.0,
        gross_margin=0.5,
        operating_margin=0.3,
        free_cash_flow_usd=18_000_000_000,
        cash_and_equivalents_usd=30_000_000_000,
        total_debt_usd=5_000_000_000,
        revenue_yoy_growth=0.1,
    )
    financials = NormalizedFinancials(
        reporting_basis="annual",
        latest_fiscal_year=2024,
        latest_fiscal_period="FY",
        periods=[period],
    )
    market = MarketDataSnapshot(
        as_of=datetime(2026, 4, 19, tzinfo=timezone.utc),
        price_usd=100.0,
        market_cap_usd=market_cap,
        enterprise_value_usd=None,
        price_to_earnings=20.0,
        price_to_sales=5.0,
        dividend_yield=None,
        fifty_two_week_high_usd=None,
        fifty_two_week_low_usd=None,
        historical_prices=[],
    )
    return AnalysisInput(
        company=company,
        financials=financials,
        filings=[],
        market_data=market,
    )


def _stub_metrics(market_cap_by_ticker: dict[str, float | None]):
    """Return a stub fetcher that yields PeerComparison rows offline."""

    def _fetch(ticker: str) -> PeerComparison | None:
        if ticker not in market_cap_by_ticker:
            return None
        cap = market_cap_by_ticker[ticker]
        return PeerComparison(
            ticker=ticker,
            company_name=f"{ticker} Corp",
            market_cap_usd=cap,
            revenue_yoy_growth=0.1,
            gross_margin=0.5,
            operating_margin=0.3,
            price_to_earnings=20.0,
            price_to_sales=5.0,
            notes=None,
        )

    return _fetch


@pytest.fixture(autouse=True)
def _clear_peer_cache():
    peers_module._PEER_CACHE.clear()
    yield
    peers_module._PEER_CACHE.clear()


def test_select_peers_uses_industry_pool_for_semiconductors(monkeypatch):
    """NVDA's industry should resolve to AMD/AVGO/INTC/etc., never NVDA itself."""
    market_caps = {
        "AMD": 250_000_000_000,
        "AVGO": 800_000_000_000,
        "INTC": 150_000_000_000,
        "QCOM": 180_000_000_000,
        "TXN": 160_000_000_000,
        "MU": 110_000_000_000,
        "MRVL": 60_000_000_000,
        "ON": 30_000_000_000,
        "ARM": 130_000_000_000,
    }
    monkeypatch.setattr(
        peers_module, "_fetch_peer_metrics", _stub_metrics(market_caps)
    )

    nvda = _make_input(
        ticker="NVDA",
        industry="Semiconductors",
        sector="Technology",
        market_cap=2_500_000_000_000,
    )

    selected = select_peers(nvda)

    assert len(selected) == MAX_PEERS
    tickers = {p.ticker for p in selected}
    assert "NVDA" not in tickers
    # All chosen peers must come from the curated semiconductor pool.
    assert tickers.issubset(set(INDUSTRY_PEERS["Semiconductors"]))


def test_select_peers_orders_by_market_cap_proximity(monkeypatch):
    """Closest market caps to the input should be returned first."""
    market_caps = {
        "AMD": 250_000_000_000,    # closest to NVDA
        "AVGO": 800_000_000_000,
        "INTC": 150_000_000_000,
        "QCOM": 180_000_000_000,
        "TXN": 160_000_000_000,
        "MU": 110_000_000_000,
        "MRVL": 60_000_000_000,
        "ON": 30_000_000_000,
        "ARM": 130_000_000_000,
    }
    monkeypatch.setattr(
        peers_module, "_fetch_peer_metrics", _stub_metrics(market_caps)
    )

    nvda = _make_input(
        ticker="NVDA",
        industry="Semiconductors",
        sector="Technology",
        market_cap=300_000_000_000,
    )

    selected = select_peers(nvda)

    distances = [
        abs(p.market_cap_usd - nvda.market_data.market_cap_usd)
        for p in selected
        if p.market_cap_usd is not None
    ]
    assert distances == sorted(distances), (
        "peers should be sorted by market-cap proximity to the input"
    )


def test_select_peers_falls_back_to_sector(monkeypatch):
    """Unknown industry should fall back to the sector pool."""
    market_caps = {
        "MSFT": 3_000_000_000_000,
        "AAPL": 3_500_000_000_000,
        "ORCL": 400_000_000_000,
        "ADBE": 200_000_000_000,
        "CRM": 250_000_000_000,
        "NVDA": 2_500_000_000_000,
        "AVGO": 800_000_000_000,
    }
    monkeypatch.setattr(
        peers_module, "_fetch_peer_metrics", _stub_metrics(market_caps)
    )

    snowflake = _make_input(
        ticker="SNOW",
        industry="Database Management Systems",
        sector="Technology",
        market_cap=50_000_000_000,
    )

    selected = select_peers(snowflake)

    assert selected, "sector fallback should yield peers"
    assert "SNOW" not in {p.ticker for p in selected}


def test_select_peers_returns_empty_when_no_pool(monkeypatch):
    """Unknown industry AND sector should return [] cleanly, not raise."""
    monkeypatch.setattr(
        peers_module, "_fetch_peer_metrics", _stub_metrics({})
    )

    obscure = _make_input(
        ticker="ZZZZ",
        industry="Made-up Industry",
        sector="Made-up Sector",
        market_cap=1_000_000_000,
    )

    assert select_peers(obscure) == []


def test_select_peers_drops_failed_lookups(monkeypatch):
    """Individual yfinance failures should not break the whole list."""

    def _flaky(ticker: str) -> PeerComparison | None:
        # Only AMD and INTC return data; everything else "fails".
        if ticker in {"AMD", "INTC"}:
            return PeerComparison(
                ticker=ticker,
                company_name=f"{ticker} Corp",
                market_cap_usd=100_000_000_000,
                revenue_yoy_growth=0.1,
                gross_margin=0.5,
                operating_margin=0.3,
                price_to_earnings=20.0,
                price_to_sales=5.0,
                notes=None,
            )
        return None

    monkeypatch.setattr(peers_module, "_fetch_peer_metrics", _flaky)

    nvda = _make_input(
        ticker="NVDA",
        industry="Semiconductors",
        sector="Technology",
        market_cap=2_500_000_000_000,
    )

    selected = select_peers(nvda)
    assert {p.ticker for p in selected} == {"AMD", "INTC"}
