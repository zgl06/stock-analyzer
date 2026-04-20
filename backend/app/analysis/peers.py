"""Industry-based peer selection.

Strategy:
  1. Look up the input company's industry in a curated industry → peers
     map. Fall back to a sector-level pool if industry isn't covered.
  2. Exclude the input ticker itself.
  3. Fetch live metrics (market cap, margins, multiples) for each
     candidate from yfinance, in parallel with a small thread pool.
  4. Sort the survivors by market-cap proximity to the input company.
  5. Return the closest `MAX_PEERS`.

Designed to degrade gracefully:
  * unknown industry / sector → empty peer list (the dashboard already
    handles this).
  * any individual yfinance lookup that fails → that peer is dropped,
    the rest still come back.
  * a recent successful lookup for a peer is cached in-process for
    `_PEER_CACHE_TTL_SECONDS` so repeated dashboard loads don't re-pull.
"""

from __future__ import annotations

import logging
import math
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import yfinance as yf

from backend.app.models import AnalysisInput, PeerComparison


logger = logging.getLogger(__name__)


MAX_PEERS = 5

# Curated peer pools keyed by Yahoo Finance "industry" strings.
# Each pool is intentionally a little wider than MAX_PEERS so the
# market-cap proximity filter has room to choose from.
INDUSTRY_PEERS: dict[str, list[str]] = {
    "Semiconductors": [
        "NVDA", "AMD", "AVGO", "INTC", "QCOM", "TXN", "MU", "MRVL", "ON", "ARM"
    ],
    "Semiconductor Equipment & Materials": [
        "ASML", "AMAT", "LRCX", "KLAC", "TER", "ENTG"
    ],
    "Software - Infrastructure": [
        "MSFT", "ORCL", "PANW", "FTNT", "CRWD", "DDOG", "NET", "SNPS", "CDNS", "ZS"
    ],
    "Software - Application": [
        "CRM", "ADBE", "INTU", "WDAY", "SNOW", "NOW", "PLTR", "TEAM", "HUBS"
    ],
    "Internet Content & Information": [
        "GOOGL", "META", "PINS", "SNAP", "RDDT", "BIDU"
    ],
    "Internet Retail": [
        "AMZN", "BABA", "MELI", "EBAY", "ETSY", "JD"
    ],
    "Consumer Electronics": [
        "AAPL", "SONY", "GRMN", "LOGI", "GPRO"
    ],
    "Auto Manufacturers": [
        "TSLA", "F", "GM", "TM", "STLA", "RIVN", "LCID", "HMC"
    ],
    "Banks - Diversified": [
        "JPM", "BAC", "WFC", "C", "HSBC", "RY", "TD"
    ],
    "Banks - Regional": [
        "USB", "PNC", "TFC", "MTB", "RF", "FITB", "HBAN"
    ],
    "Drug Manufacturers - General": [
        "JNJ", "PFE", "MRK", "ABBV", "LLY", "BMY", "NVS", "AZN", "GSK", "NVO"
    ],
    "Biotechnology": [
        "AMGN", "GILD", "REGN", "VRTX", "BIIB", "MRNA", "BNTX"
    ],
    "Oil & Gas Integrated": [
        "XOM", "CVX", "BP", "SHEL", "TTE"
    ],
    "Oil & Gas E&P": [
        "EOG", "COP", "OXY", "DVN", "FANG"
    ],
    "Aerospace & Defense": [
        "BA", "LMT", "RTX", "GD", "NOC", "TXT", "HII"
    ],
    "Discount Stores": [
        "WMT", "COST", "TGT", "DG", "DLTR", "BJ"
    ],
    "Restaurants": [
        "MCD", "SBUX", "CMG", "YUM", "QSR", "DPZ"
    ],
    "Footwear & Accessories": [
        "NKE", "DECK", "SKX", "UAA", "CROX"
    ],
    "Credit Services": [
        "V", "MA", "AXP", "PYPL", "DFS", "COF", "SYF"
    ],
    "Insurance - Diversified": [
        "BRK-B", "AIG", "ALL", "TRV", "PRU", "MET"
    ],
    "Telecom Services": [
        "VZ", "T", "TMUS", "CMCSA", "CHTR"
    ],
    "Entertainment": [
        "DIS", "NFLX", "WBD", "PARA", "FOXA", "ROKU"
    ],
    "REIT - Industrial": [
        "PLD", "AMT", "CCI", "EQIX", "DLR", "PSA"
    ],
    "Asset Management": [
        "BLK", "BX", "KKR", "APO", "TROW"
    ],
    "Capital Markets": [
        "GS", "MS", "SCHW", "IBKR", "RJF", "LPLA"
    ],
    "Home Improvement Retail": [
        "HD", "LOW", "FND"
    ],
    "Specialty Retail": [
        "TJX", "BBY", "ULTA", "ROST", "BURL"
    ],
    "Packaged Foods": [
        "PEP", "MDLZ", "GIS", "K", "HSY", "KHC", "CAG"
    ],
    "Beverages - Non-Alcoholic": [
        "KO", "PEP", "MNST", "KDP", "CELH"
    ],
    "Tobacco": [
        "MO", "PM", "BTI"
    ],
    "Steel": [
        "NUE", "STLD", "X", "CLF", "RS"
    ],
    "Specialty Chemicals": [
        "LIN", "APD", "ECL", "SHW", "PPG", "DD"
    ],
    "Medical Devices": [
        "MDT", "ABT", "BSX", "SYK", "EW", "ZBH"
    ],
    "Healthcare Plans": [
        "UNH", "ELV", "CI", "HUM", "CNC", "MOH"
    ],
    "Diagnostics & Research": [
        "TMO", "DHR", "IQV", "A", "MTD"
    ],
    "Information Technology Services": [
        "IBM", "ACN", "CTSH", "INFY", "WIT"
    ],
    "Communication Equipment": [
        "CSCO", "ANET", "JNPR", "MSI"
    ],
    "Computer Hardware": [
        "DELL", "HPQ", "HPE", "STX", "WDC", "NTAP", "PSTG"
    ],
    "Travel Services": [
        "BKNG", "ABNB", "EXPE", "TRIP"
    ],
    "Airlines": [
        "DAL", "UAL", "AAL", "LUV", "ALK"
    ],
    "Lodging": [
        "MAR", "HLT", "H", "WH", "IHG"
    ],
}

# Sector fallback pools (used only when industry doesn't match).
SECTOR_PEERS: dict[str, list[str]] = {
    "Technology": ["AAPL", "MSFT", "NVDA", "AVGO", "ORCL", "ADBE", "CRM"],
    "Communication Services": ["GOOGL", "META", "DIS", "NFLX", "VZ", "T"],
    "Financial Services": ["JPM", "BAC", "WFC", "BLK", "GS", "MS", "V", "MA"],
    "Healthcare": ["JNJ", "LLY", "UNH", "MRK", "ABBV", "PFE"],
    "Consumer Cyclical": ["AMZN", "TSLA", "HD", "MCD", "NKE"],
    "Consumer Defensive": ["WMT", "COST", "PG", "KO", "PEP"],
    "Energy": ["XOM", "CVX", "COP", "EOG"],
    "Industrials": ["GE", "CAT", "BA", "RTX", "HON", "UNP"],
    "Basic Materials": ["LIN", "APD", "FCX", "NEM"],
    "Real Estate": ["PLD", "AMT", "EQIX", "PSA", "WELL"],
    "Utilities": ["NEE", "DUK", "SO", "AEP", "D"],
}


# ---------- Public API ----------

def select_peers(analysis_input: AnalysisInput) -> list[PeerComparison]:
    """Return up to MAX_PEERS comparable companies for the input."""
    own_ticker = analysis_input.company.ticker.upper()
    industry = (analysis_input.company.industry or "").strip()
    sector = (analysis_input.company.sector or "").strip()
    own_market_cap = analysis_input.market_data.market_cap_usd

    pool = INDUSTRY_PEERS.get(industry) or SECTOR_PEERS.get(sector) or []
    candidates = [t.upper() for t in pool if t.upper() != own_ticker]

    # Cap the live-fetch fanout. We pull a slightly larger pool than
    # MAX_PEERS so the proximity filter has room to choose from.
    candidate_pool = candidates[: MAX_PEERS * 2]

    if not candidate_pool:
        logger.info(
            "No peer pool found for %s (industry=%r, sector=%r).",
            own_ticker,
            industry,
            sector,
        )
        return []

    fetched = _fetch_peers_parallel(candidate_pool)

    if own_market_cap and own_market_cap > 0:
        fetched.sort(
            key=lambda p: _market_cap_distance(p.market_cap_usd, own_market_cap)
        )

    return fetched[:MAX_PEERS]


# ---------- Internals ----------

# Simple in-process TTL cache so repeated dashboard loads don't refetch
# the same peer info from yfinance.
_PEER_CACHE: dict[str, tuple[float, PeerComparison | None]] = {}
_PEER_CACHE_TTL_SECONDS = 30 * 60  # 30 minutes


def _fetch_peers_parallel(tickers: list[str]) -> list[PeerComparison]:
    workers = max(1, min(len(tickers), 6))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        results = list(executor.map(_fetch_peer_metrics_cached, tickers))
    return [peer for peer in results if peer is not None]


def _fetch_peer_metrics_cached(ticker: str) -> PeerComparison | None:
    now = time.time()
    cached = _PEER_CACHE.get(ticker)
    if cached and (now - cached[0]) < _PEER_CACHE_TTL_SECONDS:
        return cached[1]

    peer = _fetch_peer_metrics(ticker)
    _PEER_CACHE[ticker] = (now, peer)
    return peer


def _fetch_peer_metrics(ticker: str) -> PeerComparison | None:
    try:
        info: dict[str, Any] = yf.Ticker(ticker).info or {}
    except Exception as error:
        logger.warning("Peer metrics fetch failed for %s: %s", ticker, error)
        return None

    if not info or not info.get("symbol"):
        # yfinance returns a near-empty dict for unknown tickers.
        return None

    return PeerComparison(
        ticker=ticker,
        company_name=info.get("shortName") or info.get("longName"),
        market_cap_usd=_to_float(info.get("marketCap")),
        revenue_yoy_growth=_to_float(info.get("revenueGrowth")),
        gross_margin=_to_float(info.get("grossMargins")),
        operating_margin=_to_float(info.get("operatingMargins")),
        price_to_earnings=_to_float(info.get("trailingPE")),
        price_to_sales=_to_float(info.get("priceToSalesTrailing12Months")),
        notes=None,
    )


def _market_cap_distance(peer_cap: float | None, own_cap: float) -> float:
    if peer_cap is None or peer_cap <= 0:
        return float("inf")
    # Log distance keeps tiny + huge differences comparable.
    return abs(math.log10(peer_cap) - math.log10(own_cap))


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
