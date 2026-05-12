"""Total return over a calendar window (Phase B: same rules for stock and benchmark ETF).

Uses yfinance daily bars with **dividend and split adjusted** close prices
(``auto_adjust=True``), so the result is a **simple** total return
``P_end / P_start - 1`` over the window, not annualized.

**Date convention (locked for labels later):**

- ``start`` and ``end`` are **calendar** ``datetime.date`` values inclusive of the
  intended holding **period** (the last **calendar** day you care about is ``end``).
- The implementation uses the **first** daily **close** on or after ``start`` and
  the **last** daily **close** on or before ``end`` (US equity session; index is
  **timezone-aware** in yfinance, normalized to **date** for comparisons).
- If there is no trading on ``start`` (e.g. weekend or holiday), the first close
  **after** ``start`` still counts as the start price (normal for liquid names).
- **XLC** and **XLRE**: if ``start`` is **before** the ETF's first trade date
  (inception from yfinance), returns ``None`` (no silent truncation of the window
  in Phase B). The **parent** fallback for labels is introduced in Phase C.
- If daily history does not reach through ``end`` (e.g. recent IPO), returns ``None``.

**Limitations:** yfinance data quality, delisting, and corporate actions can still skew
rare cases; M&A is handled in a later label phase.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from functools import lru_cache
from typing import Any

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)

# Communication Services and Real Estate SPDRs: short public history vs broad market.
_INCEPTION_CHECK_TICKERS = frozenset({"XLC", "XLRE"})


def _date_only(ts: Any) -> date:
    if isinstance(ts, pd.Timestamp):
        return ts.date()
    if isinstance(ts, datetime):
        return ts.date()
    if hasattr(ts, "date") and not isinstance(ts, date):
        return ts.date()  # type: ignore[no-any-return]
    if isinstance(ts, date):
        return ts
    raise TypeError(f"Unsupported timestamp type: {type(ts)}")


@lru_cache(maxsize=32)
def _first_trade_date_utc(ticker: str) -> date | None:
    """First calendar day with a daily bar in yfinance ``period='max'`` (best-effort)."""
    t = ticker.strip().upper()
    try:
        hist = yf.Ticker(t).history(period="max", interval="1d", auto_adjust=True)
    except Exception as e:  # pragma: no cover - network
        logger.debug("yfinance max history failed for %s: %s", t, e)
        return None
    if hist is None or hist.empty or "Close" not in hist.columns:
        return None
    return _date_only(hist.index.min())


def total_return_simple(
    ticker: str,
    start: date,
    end: date,
    *,
    _yf_ticker: Any | None = None,
) -> float | None:
    """Return **simple** total return (fraction) from adjusted close: ``P_end/P_start - 1``.

    Parameters
    ----------
    ticker
        US equity or ETF symbol (e.g. ``'SPY'``, ``'AAPL'``).
    start, end
        **Inclusive** calendar window for the return; ``end`` must be **after** ``start``.
    _yf_ticker
        **Tests only:** inject a mock instead of ``yfinance.Ticker``.

    Returns
    -------
    float | None
        Total return as a **fraction** (0.1 is 10%), or ``None`` if data are missing
        or the window is not fully covered per the rules above.
    """
    if end <= start:
        return None
    t = (ticker or "").strip().upper()
    if not t:
        return None

    if t in _INCEPTION_CHECK_TICKERS:
        first = _first_trade_date_utc(t)
        if first is not None and start < first:
            return None

    # yfinance ``end`` is exclusive; add one day so ``end`` is inclusive as a calendar day.
    end_exclusive = end + timedelta(days=1)
    if _yf_ticker is not None:
        yft = _yf_ticker
    else:
        yft = yf.Ticker(t)

    try:
        hist = yft.history(
            start=start,
            end=end_exclusive,
            interval="1d",
            auto_adjust=True,
        )
    except Exception as e:  # pragma: no cover - network
        logger.debug("yfinance history failed for %s: %s", t, e)
        return None

    if hist is None or hist.empty or "Close" not in hist.columns:
        return None

    close = hist["Close"].dropna()
    if len(close) < 2:
        return None

    # Rows whose session date falls inside [start, end] (inclusive).
    idx_dates = pd.Index([_date_only(x) for x in close.index])
    mask = (idx_dates >= start) & (idx_dates <= end)
    window = close.loc[mask]
    if len(window) < 2:
        return None

    p0 = float(window.iloc[0])
    p1 = float(window.iloc[-1])
    if p0 <= 0:
        return None

    return p1 / p0 - 1.0
