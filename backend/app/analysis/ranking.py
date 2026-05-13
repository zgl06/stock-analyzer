"""Industry-wide, market-wide, and peer-relative rank context.

Uses the same yfinance peer rows as :mod:`peers` and a small benchmark
universe so the UI can show "where this name sits" without a trained ML
ranker. Numbers are a transparent proxy, not a price forecast.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from backend.app.models import (
    AnalysisInput,
    AmongPeersRanks,
    PeerComparison,
    RankingContext,
)

from .peers import INDUSTRY_PEERS, SECTOR_PEERS, _fetch_peer_metrics_cached

logger = logging.getLogger(__name__)

# Liquid US names across sectors for a coarse "market" cohort (v1).
MARKET_BENCHMARK_TICKERS: tuple[str, ...] = (
    "AAPL",
    "MSFT",
    "GOOGL",
    "AMZN",
    "NVDA",
    "META",
    "JPM",
    "JNJ",
    "V",
    "WMT",
    "XOM",
    "UNH",
    "PG",
    "MA",
    "HD",
    "CVX",
    "MRK",
    "PEP",
    "COST",
    "ABBV",
    "TMO",
    "ACN",
    "DHR",
    "MCD",
    "CSCO",
    "ORCL",
    "NFLX",
    "DIS",
    "BMY",
    "HON",
    "LOW",
    "GS",
    "PM",
    "TXN",
    "QCOM",
    "INTC",
    "AMGN",
    "IBM",
    "RTX",
    "NKE",
)

METHODOLOGY = (
    "Ranks use min-max normalized growth, gross margin, operating margin, "
    "and 1/(1+P/E) within each cohort; not a return forecast or buy signal on its own."
)


@dataclass(frozen=True)
class _Row:
    ticker: str
    growth: float | None
    gross_m: float | None
    op_m: float | None
    pe: float | None
    ps: float | None


def _row_from_input(inp: AnalysisInput) -> _Row:
    latest = (
        inp.financials.periods[-1] if inp.financials.periods else None
    )
    return _Row(
        ticker=inp.company.ticker.upper(),
        growth=(latest.revenue_yoy_growth if latest else None),
        gross_m=(latest.gross_margin if latest else None),
        op_m=(latest.operating_margin if latest else None),
        pe=inp.market_data.price_to_earnings,
        ps=inp.market_data.price_to_sales,
    )


def _row_from_peer(peer: PeerComparison) -> _Row:
    return _Row(
        ticker=peer.ticker.upper(),
        growth=peer.revenue_yoy_growth,
        gross_m=peer.gross_margin,
        op_m=peer.operating_margin,
        pe=peer.price_to_earnings,
        ps=peer.price_to_sales,
    )


def _percentile(
    value: float | None,
    cohort: Sequence[float | None],
    *,
    higher_is_better: bool = True,
) -> float | None:
    """Percentile 0-100 of `value` within the combined sample (value included in cohort)."""
    clean: list[float] = []
    for x in cohort:
        if x is not None and math.isfinite(float(x)):
            v = float(x) if not higher_is_better else float(x)
            clean.append(v)
    if value is None or not math.isfinite(value):
        return None
    if not clean:
        return None
    v0 = float(value)
    v = v0 if higher_is_better else -v0
    if not higher_is_better:
        clean = [-x for x in clean]
    if v not in clean:
        clean.append(v)
    clean.sort()
    n = len(clean)
    if n <= 1:
        return 50.0
    # Mid-rank for ties, then scale to 0-100
    first = min(i for i, x in enumerate(clean) if x == v)
    last = max(i for i, x in enumerate(clean) if x == v)
    mid = 0.5 * (first + last)
    return 100.0 * mid / (n - 1)


def _value_proxy(
    row: _Row,
    mins: list[float],
    maxs: list[float],
) -> float:
    """Average of min-max normalized growth, gross_m, op_m, value_lean."""
    def norm(i: int, x: float | None) -> float:
        lo, hi = mins[i], maxs[i]
        if x is None or not math.isfinite(x):
            return 0.5
        if hi - lo < 1e-12:
            return 0.5
        return (float(x) - lo) / (hi - lo)

    g, gm, om = row.growth, row.gross_m, row.op_m
    pe = row.pe if row.pe and row.pe > 0 else 1.0
    value_lean = 1.0 / (1.0 + pe)  # higher when cheaper; comparable across cohort via norm

    parts = [norm(0, g), norm(1, gm), norm(2, om), norm(3, value_lean)]
    return sum(parts) / len(parts)


def _min_max_for_columns(rows: list[_Row]) -> tuple[list[float], list[float]]:
    def col_vals(getter: int) -> list[float]:
        out: list[float] = []
        for r in rows:
            if getter == 0:
                v = r.growth
            elif getter == 1:
                v = r.gross_m
            elif getter == 2:
                v = r.op_m
            else:
                pe = r.pe if r.pe and r.pe > 0 else 1.0
                v = 1.0 / (1.0 + pe)
            if v is not None and math.isfinite(v):
                out.append(float(v))
        return out

    mins: list[float] = []
    maxs: list[float] = []
    for c in range(4):
        vals = col_vals(c)
        if not vals:
            mins.append(0.0)
            maxs.append(1.0)
        else:
            mins.append(min(vals))
            maxs.append(max(vals))
    return mins, maxs


def _proxy_percentile_in_rows(subject: _Row, rows: list[_Row]) -> float | None:
    if not rows:
        return None
    if not any(r.ticker == subject.ticker for r in rows):
        rows = [*rows, subject]
    mins, maxs = _min_max_for_columns(rows)
    scores = [_value_proxy(r, mins, maxs) for r in rows]
    try:
        idx = next(i for i, r in enumerate(rows) if r.ticker == subject.ticker)
    except StopIteration:
        return None
    return _percentile(scores[idx], scores, higher_is_better=True)


def _industry_cohort_tickers(inp: AnalysisInput) -> list[str]:
    ind = (inp.company.industry or "").strip()
    sec = (inp.company.sector or "").strip()
    own = inp.company.ticker.upper()
    pool = INDUSTRY_PEERS.get(ind) or SECTOR_PEERS.get(sec) or []
    out: list[str] = [own]
    for t in pool:
        t = t.strip().upper()
        if t and t not in out:
            out.append(t)
        if len(out) >= 24:
            break
    return out


def _market_cohort_tickers(inp: AnalysisInput) -> list[str]:
    own = inp.company.ticker.upper()
    out: list[str] = [own]
    for t in MARKET_BENCHMARK_TICKERS:
        if t not in out:
            out.append(t)
    return out


def _cohort_rows(tickers: list[str], analysis_input: AnalysisInput) -> list[_Row]:
    """Build metric rows, using the analysis snapshot for the subject ticker."""
    own = analysis_input.company.ticker.upper()
    rows: list[_Row] = []
    for raw in tickers:
        t = raw.strip().upper()
        if not t:
            continue
        if t == own:
            rows.append(_row_from_input(analysis_input))
            continue
        peer = _fetch_peer_metrics_cached(t)
        if peer is not None:
            rows.append(_row_from_peer(peer))
    return rows


def _among_peer_metrics(
    subject: _Row,
    peers: list[PeerComparison],
) -> AmongPeersRanks:
    peer_rows = [_row_from_peer(p) for p in peers]
    if not peer_rows:
        return AmongPeersRanks()

    g_coh = [subject.growth] + [r.growth for r in peer_rows]
    gm_coh = [subject.gross_m] + [r.gross_m for r in peer_rows]
    om_coh = [subject.op_m] + [r.op_m for r in peer_rows]
    pe_coh = [subject.pe] + [r.pe for r in peer_rows]
    ps_coh = [subject.ps] + [r.ps for r in peer_rows]

    growth_pct = _percentile(subject.growth, g_coh)
    gmp = _percentile(subject.gross_m, gm_coh)
    omp = _percentile(subject.op_m, om_coh)
    if gmp is not None and omp is not None:
        prof = (gmp + omp) / 2.0
    elif gmp is not None:
        prof = gmp
    elif omp is not None:
        prof = omp
    else:
        prof = None
    val = _percentile(subject.ps, ps_coh) or _percentile(
        subject.pe, pe_coh, higher_is_better=True
    )
    all_rows = [subject] + peer_rows
    comp = _proxy_percentile_in_rows(subject, all_rows)
    return AmongPeersRanks(
        growth_percentile=growth_pct,
        profitability_percentile=prof,
        valuation_percentile=val,
        composite_proxy_percentile=comp,
    )


def build_ranking_context(
    analysis_input: AnalysisInput,
    peers: list[PeerComparison],
) -> RankingContext:
    subject = _row_from_input(analysis_input)
    among = _among_peer_metrics(subject, peers)

    industry_tickers = _industry_cohort_tickers(analysis_input)
    ind_rows = _cohort_rows(industry_tickers, analysis_input)
    ind_n = len(ind_rows)
    ind_pct: float | None = None
    if ind_rows:
        subj_row = next((r for r in ind_rows if r.ticker == subject.ticker), None)
        if subj_row is not None and len(ind_rows) > 1:
            ind_pct = _proxy_percentile_in_rows(subj_row, ind_rows)
        elif len(ind_rows) == 1:
            ind_pct = 50.0
    if ind_n == 0:
        logger.info(
            "Industry cohort empty for %s; skipping industry rank.",
            subject.ticker,
        )

    market_tickers = _market_cohort_tickers(analysis_input)
    m_rows = _cohort_rows(market_tickers, analysis_input)
    m_n = len(m_rows)
    m_pct: float | None = None
    if m_rows:
        subj_row = next((r for r in m_rows if r.ticker == subject.ticker), None)
        if subj_row is not None and len(m_rows) > 1:
            m_pct = _proxy_percentile_in_rows(subj_row, m_rows)
        elif len(m_rows) == 1:
            m_pct = 50.0

    return RankingContext(
        among_peers=among,
        industry_universe_size=ind_n or None,
        industry_percentile=ind_pct,
        market_universe_size=m_n or None,
        market_percentile=m_pct,
        methodology_note=METHODOLOGY,
    )
