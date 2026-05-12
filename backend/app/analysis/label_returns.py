"""Phase D: M&A and delisting policy for **stock** total-return labels.

Free APIs (e.g. yfinance) do **not** expose a reliable, machine-friendly chain from a
**delisted** or **merged** symbol to the **acquirer** and **effective date**. v1
therefore does the following:

1. Call the same :func:`returns.total_return_simple` as Phase B.
2. If the return is ``None`` and the symbol has an entry in
   :data:`MERGER_OVERRIDES` (ticker, acquirer, effective **calendar** date), then:
   * If the merger effective date lies **in** ``(start, end]``, return **no** stock
     return and reason ``merger_spans_window`` (label row should be **dropped** or
     kept with NaN per your ETL; we surface the reason).
   * If the effective date is **on or before** ``start`` (holder already in acquirer
     stock for the full window), recompute a **simple** 5y return on the **acquirer**
     only and set ``merger_note="acquirer_post_merger"`` when it succeeds.
3. If still unresolved, return ``yfinance_unavailable`` (or a more specific string
   later).

**TODO (future feeds):** Point-in-time **CRSP**-style name changes, **SEC 8-K**,
or a paid **corporate actions** product can **populate** :data:`MERGER_OVERRIDES` at
ETL time, or call :func:`register_merger_override` from a batch job. Do not expect
:func:`try_yfinance_merger_hint` to work; it is a stub for logging or experiments.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from typing import Any

import yfinance as yf

from backend.app.analysis.returns import total_return_simple

logger = logging.getLogger(__name__)

# Populated in production by ETL or config; empty = only direct yfinance return.
MERGER_OVERRIDES: dict[str, tuple[str, date]] = {}


def register_merger_override(
    old_ticker: str,
    acquirer: str,
    effective: date,
) -> None:
    """Record that *old_ticker* became *acquirer* (symbol) on *effective* (calendar)."""
    MERGER_OVERRIDES[old_ticker.strip().upper()] = (
        acquirer.strip().upper(),
        date(effective.year, effective.month, effective.day),
    )


def clear_merger_overrides() -> None:
    """Clear override table (use in tests)."""
    MERGER_OVERRIDES.clear()


@dataclass(frozen=True, slots=True)
class StockLabelReturn:
    """Result of a single stock total-return label attempt."""

    value: float | None
    """Simple total return fraction, or ``None`` if the row should not be used."""
    symbol_used: str
    """Ticker that was **priced** (subject or acquirer)."""
    skip_reason: str | None
    """Machine-readable code when *value* is ``None``."""
    merger_note: str | None
    """Human/audit string, e.g. ``acquirer_post_merger`` when *symbol_used* is acquirer."""


def try_yfinance_merger_hint(ticker: str) -> None:
    """Log non-fatal yfinance *info* keys that might relate to M&A. No automatic mapping in v1."""
    t = (ticker or "").strip().upper()
    if not t:
        return
    try:
        info: dict[str, Any] = (yf.Ticker(t).info or {})  # type: ignore[assignment]
    except Exception as e:  # pragma: no cover
        logger.debug("try_yfinance_merger_hint: no .info for %s: %s", t, e)
        return
    for key in (
        "delisted",
        "longName",
        "quoteType",
    ):
        if key in info and info.get(key) is not None:
            logger.debug("try_yfinance_merger_hint %s: %s=%r", t, key, info.get(key))


def total_return_stock_for_label(
    ticker: str,
    start: date,
    end: date,
    *,
    _inner: Callable[..., float | None] = total_return_simple,
) -> StockLabelReturn:
    """Best-effort stock return for a **forward** label window, with optional acquirer leg."""
    t = (ticker or "").strip().upper()
    if not t:
        return StockLabelReturn(None, "", "empty_ticker", None)

    r0 = _inner(t, start, end)
    if r0 is not None:
        return StockLabelReturn(r0, t, None, None)

    if t in MERGER_OVERRIDES:
        acq, m_eff = MERGER_OVERRIDES[t]
        if start < m_eff <= end:
            try_yfinance_merger_hint(t)
            logger.info(
                "Label skip %s: merger effective %s inside (%s, %s]",
                t,
                m_eff,
                start,
                end,
            )
            return StockLabelReturn(
                None,
                t,
                "merger_spans_window",
                f"merger_effective={m_eff}",
            )
        if m_eff <= start:
            r1 = _inner(acq, start, end)
            if r1 is not None:
                return StockLabelReturn(
                    r1,
                    acq,
                    None,
                    "acquirer_post_merger",
                )
            return StockLabelReturn(
                None,
                acq,
                "acquirer_return_unavailable",
                "acquirer_post_merger",
            )
        return StockLabelReturn(
            None,
            t,
            "yfinance_unavailable",
            f"pre_merger_window_merger_after_end={m_eff}",
        )

    return StockLabelReturn(None, t, "yfinance_unavailable", None)
