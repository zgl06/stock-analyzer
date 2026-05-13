"""Phase E: batch build of 5y label rows over a `(ticker, as_of)` grid.

This module keeps Phase E intentionally lightweight and file-based:

- No database required.
- Input grid comes from ticker/date lists.
- Output is a DataFrame that can be written to CSV/Parquet.
- Resume behavior uses `(ticker, as_of)` keys from an existing output.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from backend.app.analysis.excess_returns import five_year_excess_table


@dataclass(frozen=True, slots=True)
class LabelBuildReport:
    tickers_requested: int
    as_of_requested: int
    requested_pairs: int
    existing_pairs: int
    new_pairs_attempted: int
    rows_written_new: int
    rows_total: int
    date_min: date | None
    date_max: date | None
    null_rate_excess_spy: float
    null_rate_excess_sector: float
    null_rate_stock_skip_reason: float

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def generate_as_of_dates(start: date, end: date, frequency: str) -> list[date]:
    """Generate inclusive `as_of` dates for `monthly` or `quarterly` grids."""
    if end < start:
        return []
    f = frequency.strip().lower()
    if f not in {"monthly", "quarterly"}:
        raise ValueError("frequency must be one of: monthly, quarterly")
    pandas_freq = "MS" if f == "monthly" else "QS"
    idx = pd.date_range(start=start, end=end, freq=pandas_freq)
    return [ts.date() for ts in idx]


def read_existing_label_output(path: Path) -> pd.DataFrame:
    """Read existing label output by extension (`.csv`, `.parquet`); empty if missing."""
    if not path.exists():
        return pd.DataFrame()
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path, parse_dates=["as_of", "end_date"], keep_default_na=True)
    if path.suffix.lower() in {".parquet", ".pq"}:
        return pd.read_parquet(path)
    raise ValueError(f"Unsupported output extension: {path.suffix}. Use .csv or .parquet")


def write_label_output(df: pd.DataFrame, path: Path) -> None:
    """Write label output by extension (`.csv`, `.parquet`)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix.lower() == ".csv":
        df.to_csv(path, index=False)
        return
    if path.suffix.lower() in {".parquet", ".pq"}:
        df.to_parquet(path, index=False)
        return
    raise ValueError(f"Unsupported output extension: {path.suffix}. Use .csv or .parquet")


def build_label_dataset(
    tickers: Iterable[str],
    as_of_dates: Iterable[date],
    *,
    sector_by_ticker: dict[str, str] | None = None,
    existing: pd.DataFrame | None = None,
    use_spy_if_sector_etf_fails: bool = True,
    merger_aware: bool = True,
    build_fn: Callable[..., pd.DataFrame] = five_year_excess_table,
) -> tuple[pd.DataFrame, LabelBuildReport]:
    """Build a batch label dataset and report.

    The output DataFrame contains one row per `(ticker, as_of)` attempt.
    Rows already present in `existing` are skipped (idempotent/resume behavior).
    """
    tickers_clean = sorted({t.strip().upper() for t in tickers if t and t.strip()})
    as_of_list = sorted({d for d in as_of_dates})
    existing_df = existing.copy() if existing is not None else pd.DataFrame()

    existing_keys: set[tuple[str, date]] = set()
    if not existing_df.empty and {"ticker", "as_of"}.issubset(existing_df.columns):
        tmp = existing_df.copy()
        tmp["ticker"] = tmp["ticker"].astype(str).str.upper().str.strip()
        tmp["as_of"] = pd.to_datetime(tmp["as_of"]).dt.date
        existing_keys = {(r.ticker, r.as_of) for r in tmp.itertuples(index=False)}

    requested_pairs = len(tickers_clean) * len(as_of_list)

    new_frames: list[pd.DataFrame] = []
    new_pairs_attempted = 0
    for ticker in tickers_clean:
        pending_dates = [d for d in as_of_list if (ticker, d) not in existing_keys]
        if not pending_dates:
            continue
        new_pairs_attempted += len(pending_dates)
        sector = None
        if sector_by_ticker:
            sector = sector_by_ticker.get(ticker)
        df_t = build_fn(
            ticker,
            pending_dates,
            sector=sector,
            use_spy_if_sector_etf_fails=use_spy_if_sector_etf_fails,
            merger_aware=merger_aware,
        )
        if not df_t.empty:
            new_frames.append(df_t)

    if new_frames:
        new_df = pd.concat(new_frames, ignore_index=True)
    else:
        new_df = pd.DataFrame()

    if existing_df.empty:
        all_df = new_df.copy()
    elif new_df.empty:
        all_df = existing_df.copy()
    else:
        all_df = pd.concat([existing_df, new_df], ignore_index=True)

    # Normalize for deterministic output and report.
    if not all_df.empty and "as_of" in all_df.columns:
        all_df["ticker"] = all_df["ticker"].astype(str).str.upper().str.strip()
        all_df["as_of"] = pd.to_datetime(all_df["as_of"]).dt.date
        all_df = all_df.sort_values(["ticker", "as_of"]).drop_duplicates(
            subset=["ticker", "as_of"], keep="last"
        )
        all_df = all_df.reset_index(drop=True)

    def _null_rate(col: str) -> float:
        if all_df.empty or col not in all_df.columns:
            return 1.0
        return float(all_df[col].isna().mean())

    dmin: date | None = None
    dmax: date | None = None
    if not all_df.empty and "as_of" in all_df.columns:
        dmin = min(all_df["as_of"])
        dmax = max(all_df["as_of"])

    report = LabelBuildReport(
        tickers_requested=len(tickers_clean),
        as_of_requested=len(as_of_list),
        requested_pairs=requested_pairs,
        existing_pairs=len(existing_keys),
        new_pairs_attempted=new_pairs_attempted,
        rows_written_new=len(new_df),
        rows_total=len(all_df),
        date_min=dmin,
        date_max=dmax,
        null_rate_excess_spy=_null_rate("excess_spy"),
        null_rate_excess_sector=_null_rate("excess_sector"),
        null_rate_stock_skip_reason=_null_rate("stock_label_skip_reason"),
    )
    return all_df, report


def load_tickers_file(path: Path) -> list[str]:
    """Load tickers from `.txt` (one per line) or `.csv` (`ticker` column preferred)."""
    if not path.exists():
        raise FileNotFoundError(path)
    if path.suffix.lower() == ".txt":
        return [ln.strip().upper() for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    if path.suffix.lower() == ".csv":
        df = pd.read_csv(path)
        if "ticker" in df.columns:
            col = df["ticker"]
        else:
            # fallback: first column
            col = df.iloc[:, 0]
        return [str(v).strip().upper() for v in col.tolist() if str(v).strip()]
    raise ValueError("Unsupported ticker file. Use .txt or .csv")


def load_sector_file(path: Path) -> dict[str, str]:
    """Load optional ticker->sector overrides from CSV columns: `ticker,sector`."""
    if not path.exists():
        raise FileNotFoundError(path)
    df = pd.read_csv(path)
    if not {"ticker", "sector"}.issubset(df.columns):
        raise ValueError("sector file must contain columns: ticker,sector")
    out: dict[str, str] = {}
    for row in df.itertuples(index=False):
        t = str(getattr(row, "ticker", "")).strip().upper()
        s = str(getattr(row, "sector", "")).strip()
        if t and s:
            out[t] = s
    return out

