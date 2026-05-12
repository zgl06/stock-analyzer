"""Phase C: realized 5y **simple** total returns and **excess** vs SPY and vs sector ETF.

For each *as_of* **calendar** date, the forward window is **[as_of, end]** inclusive,
where *end* is *as_of* with **five calendar years** added (Feb 29 -> Feb 28 in the
target year if needed). Returns match :func:`returns.total_return_simple` (dividend-
and split-adjusted closes).

**Sector leg**

- Resolve GICS-style **sector** from ``sector`` (if provided) or from
  ``yfinance.Ticker(ticker).info`` (``"sector"``). If you already have
  :class:`backend.app.models.contracts.CompanySnapshot`, pass
  ``company.sector`` so this module does not need an extra yfinance call.
- Map sector text to a SPDR ticker via :func:`benchmarks.sector_etf_ticker`
  (Phase A). If the sector string is **missing** or unmapped, **r_sector_5y** and
  **excess_sector** are left empty (``NaN``) for that row; we do not guess a sector ETF.

**M&A (Phase D, when** ``merger_aware`` **is True, default):**

- The **stock** return uses :func:`label_returns.total_return_stock_for_label`, which
  calls the same ``_total_return`` as SPY/sector, then may apply
  :data:`label_returns.MERGER_OVERRIDES` to price the **acquirer** when the effective
  merger date is **on or before** *as_of*, or set **skip** reasons if the merger
  **falls in** the 5y window.

**Parent fallback (when** ``use_spy_if_sector_etf_fails`` **is True, default):**

- If the mapped sector ETF’s **total return** is unavailable for that window
  (``None`` from :func:`returns.total_return_simple`, e.g. data gap), the **sector
  bench** reuses **SPY** for that row: *r_sector_5y* = *r_spy_5y*, and
  *excess_sector* equals *excess_spy*. Columns **sector_bench_ticker** is ``"SPY"`` and
  **parent_spy_filled** is True. This matches the “parent sector / broad” rule from
  the spec without silently dropping the row. When the flag is **False**, a missing
  sector ETF return leaves **r_sector_5y** / **excess_sector** as ``NaN`` instead.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import date
from typing import Any

import numpy as np
import pandas as pd
import yfinance as yf

from backend.app.analysis.benchmarks import (
    BROAD_BENCHMARK_TICKER,
    sector_etf_ticker,
)
from backend.app.analysis.label_returns import total_return_stock_for_label
from backend.app.analysis.returns import total_return_simple

logger = logging.getLogger(__name__)

HOLDING_YEARS = 5


def add_calendar_years(d: date, years: int) -> date:
    """Add *years* to *d*; map Feb 29 to Feb 28 in the target year if needed."""
    try:
        return d.replace(year=d.year + years)
    except ValueError:
        return date(d.year + years, 2, 28)


@dataclass(frozen=True, slots=True)
class SectorResolution:
    """How we resolved the GICS / vendor sector string and ETF symbol."""

    gics_or_vendor: str | None
    etf: str | None
    source: str  # "argument", "yfinance", or "missing"


def resolve_sector_name(
    ticker: str,
    sector: str | None = None,
    *,
    _yf: Any | None = None,
) -> SectorResolution:
    """Return provider sector string and SPDR symbol when mappable; else missing."""
    t = (ticker or "").strip().upper()
    if sector and str(sector).strip():
        g = str(sector).strip()
        etf = sector_etf_ticker(g)
        return SectorResolution(g, etf, "argument")
    yft = _yf or yf.Ticker(t)
    try:
        info = yft.info or {}
    except Exception as e:  # pragma: no cover
        logger.debug("yfinance .info for sector failed for %s: %s", t, e)
        return SectorResolution(None, None, "missing")
    g = (info.get("sector") or "").strip() or None
    if g is None:
        return SectorResolution(None, None, "missing")
    etf = sector_etf_ticker(g)
    return SectorResolution(g, etf, "yfinance")


def five_year_excess_table(
    ticker: str,
    as_of_dates: Iterable[date],
    *,
    sector: str | None = None,
    use_spy_if_sector_etf_fails: bool = True,
    merger_aware: bool = True,
    _total_return: Callable[..., float | None] = total_return_simple,
) -> pd.DataFrame:
    """One row per *as_of*: 5y returns and excess vs broad and sector benchmarks.

    Parameters
    ----------
    ticker
        US equity **symbol** (e.g. ``'AAPL'``).
    as_of_dates
        **Rebalance** or label dates; each starts a 5y **forward** window.
    sector
        Optional sector string (e.g. from ``AnalysisInput.company.sector``). If
        omitted, a single yfinance ``.info`` lookup is used (first row only) to
        avoid repeated network calls; call :func:`resolve_sector_name` yourself
        and pass *sector* for full control.
    use_spy_if_sector_etf_fails
        If True, when the sector ETF return is ``None`` but **SPY** is available,
        set the sector-bench return to **SPY** and mark **parent_spy_filled** True.
    merger_aware
        If True (default), the **stock** leg uses :func:`label_returns.total_return_stock_for_label`
        (Phase D: acquirer overrides, skip reasons). If False, call ``_total_return`` on
        *ticker* only, as in Phase C.
    _total_return
        Inject mock for unit tests; defaults to :func:`returns.total_return_simple`.

    Returns
    -------
    pandas.DataFrame
        Columns: ``ticker``, ``as_of``, ``end_date``, ``gics_or_vendor``,
        ``r_stock_5y``, ``r_spy_5y``, ``r_sector_5y`` (return of the **instrument
        used** for the sector leg), ``excess_spy``, ``excess_sector``,
        ``sector_bench_ticker`` (SPDR or ``SPY`` if parent used), ``parent_spy_filled``,
        ``mapped_sector_etf`` (ticker if mapping succeeded, else ``NaN``),
        ``stock_label_symbol``, ``stock_label_skip_reason``, ``stock_label_merger_note``
        (Phase D, empty when *merger_aware* is False or no skip).
    """
    t = (ticker or "").strip().upper()
    if not t:
        raise ValueError("ticker is required")

    as_of_list = sorted({d for d in as_of_dates})
    if not as_of_list:
        return _empty_excess_frame()

    sec_res: SectorResolution | None = None
    if sector and str(sector).strip():
        sec_res = resolve_sector_name(t, sector)
    else:
        sec_res = resolve_sector_name(t, None)
        if sec_res.gics_or_vendor and len(as_of_list) > 1:
            logger.debug(
                "Reusing sector from yfinance for %d as_of rows on %s: %r",
                len(as_of_list),
                t,
                sec_res.gics_or_vendor,
            )

    rows: list[dict[str, Any]] = []
    for as_of in as_of_list:
        end_d = add_calendar_years(as_of, HOLDING_YEARS)
        if end_d <= as_of:
            continue

        if merger_aware:
            slr = total_return_stock_for_label(t, as_of, end_d, _inner=_total_return)
            r_stock = slr.value
            stock_lbl_sym = slr.symbol_used
            stock_lbl_skip = slr.skip_reason
            stock_lbl_note = slr.merger_note
        else:
            r_stock = _total_return(t, as_of, end_d)
            stock_lbl_sym = t
            stock_lbl_skip = None
            stock_lbl_note = None

        r_spy = _total_return(BROAD_BENCHMARK_TICKER, as_of, end_d)
        gics = sec_res.gics_or_vendor if sec_res else None
        mapped_etf = sec_res.etf if sec_res else None

        r_sector: float | None = None
        parent_filled = False
        sector_bench_ticker: str | None = None

        if mapped_etf is not None:
            r_sector_etf = _total_return(mapped_etf, as_of, end_d)
            if r_sector_etf is not None:
                r_sector = r_sector_etf
                sector_bench_ticker = mapped_etf
            elif use_spy_if_sector_etf_fails and r_spy is not None:
                r_sector = r_spy
                sector_bench_ticker = BROAD_BENCHMARK_TICKER
                parent_filled = True
            else:
                r_sector = None
                sector_bench_ticker = mapped_etf
        else:
            r_sector = None
            sector_bench_ticker = None

        excess_spy = (r_stock - r_spy) if r_stock is not None and r_spy is not None else np.nan
        excess_sec = (
            (r_stock - r_sector) if r_stock is not None and r_sector is not None else np.nan
        )

        rows.append(
            {
                "ticker": t,
                "as_of": as_of,
                "end_date": end_d,
                "gics_or_vendor": gics,
                "r_stock_5y": r_stock if r_stock is not None else np.nan,
                "r_spy_5y": r_spy if r_spy is not None else np.nan,
                "r_sector_5y": r_sector if r_sector is not None else np.nan,
                "excess_spy": excess_spy,
                "excess_sector": excess_sec,
                "sector_bench_ticker": sector_bench_ticker,
                "parent_spy_filled": bool(parent_filled),
                "mapped_sector_etf": mapped_etf,
                "stock_label_symbol": stock_lbl_sym,
                "stock_label_skip_reason": stock_lbl_skip,
                "stock_label_merger_note": stock_lbl_note,
            }
        )

    if not rows:
        return _empty_excess_frame()
    return pd.DataFrame(rows)


def _empty_excess_frame() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "ticker",
            "as_of",
            "end_date",
            "gics_or_vendor",
            "r_stock_5y",
            "r_spy_5y",
            "r_sector_5y",
            "excess_spy",
            "excess_sector",
            "sector_bench_ticker",
            "parent_spy_filled",
            "mapped_sector_etf",
            "stock_label_symbol",
            "stock_label_skip_reason",
            "stock_label_merger_note",
        ]
    )
