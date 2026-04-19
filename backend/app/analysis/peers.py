"""Placeholder peer-selection module.

Day 1: returns a deterministic mock peer list so the response shape
stays stable. Real sector/industry plus market-cap proximity peer
selection lands in a later day.
"""

from __future__ import annotations

from backend.app.models import AnalysisInput, PeerComparison


def select_peers(analysis_input: AnalysisInput) -> list[PeerComparison]:
    """Return mock peers for the given input.

    The fixture-backed implementation never returns the input company
    as its own peer, matching the documented MVP behavior.
    """
    own_ticker = analysis_input.company.ticker.upper()

    candidates: list[PeerComparison] = [
        PeerComparison(
            ticker="MSFT",
            company_name="Microsoft Corporation",
            market_cap_usd=3_100_000_000_000,
            revenue_yoy_growth=0.12,
            gross_margin=0.69,
            operating_margin=0.44,
            price_to_earnings=35.1,
            price_to_sales=12.6,
            notes="Stub peer entry.",
        ),
        PeerComparison(
            ticker="GOOGL",
            company_name="Alphabet Inc.",
            market_cap_usd=2_300_000_000_000,
            revenue_yoy_growth=0.13,
            gross_margin=0.57,
            operating_margin=0.30,
            price_to_earnings=25.4,
            price_to_sales=6.8,
            notes="Stub peer entry.",
        ),
        PeerComparison(
            ticker="AMZN",
            company_name="Amazon.com, Inc.",
            market_cap_usd=2_000_000_000_000,
            revenue_yoy_growth=0.11,
            gross_margin=0.47,
            operating_margin=0.10,
            price_to_earnings=46.0,
            price_to_sales=3.4,
            notes="Stub peer entry.",
        ),
        PeerComparison(
            ticker="META",
            company_name="Meta Platforms, Inc.",
            market_cap_usd=1_400_000_000_000,
            revenue_yoy_growth=0.16,
            gross_margin=0.81,
            operating_margin=0.40,
            price_to_earnings=27.5,
            price_to_sales=9.1,
            notes="Stub peer entry.",
        ),
        PeerComparison(
            ticker="AAPL",
            company_name="Apple Inc.",
            market_cap_usd=3_654_000_000_000,
            revenue_yoy_growth=0.02,
            gross_margin=0.46,
            operating_margin=0.31,
            price_to_earnings=37.6,
            price_to_sales=9.3,
            notes="Stub peer entry.",
        ),
    ]

    return [peer for peer in candidates if peer.ticker.upper() != own_ticker][:5]
