"""GICS sector → SPDR Select Sector ETF mapping and broad index benchmark (Phase A).

Loads :file:`backend/gics_sector_etfs.yaml`. Use :func:`sector_etf_ticker` with
vendor sector strings (e.g. yfinance \"Technology\" → ``XLK``).
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
try:
    import yaml
except ImportError as e:  # pragma: no cover
    raise ImportError("benchmarks requires PyYAML; install pyyaml") from e


def _package_dir() -> Path:
    return Path(__file__).resolve().parent


def _backend_dir() -> Path:
    # .../backend/app/analysis/benchmarks.py -> parents[0]=app, [1]=backend
    return _package_dir().parents[1]


def _yaml_path() -> Path:
    return _backend_dir() / "gics_sector_etfs.yaml"


def _normalize_sector_key(s: str) -> str:
    """Collapse whitespace and case for matching."""
    s = s.strip()
    s = re.sub(r"\s+", " ", s)
    return s.casefold()


# Aliases: normalized key → canonical GICS sector name as in gics_sector_etfs.yaml
# Covers common yfinance / Yahoo strings that differ from official GICS spelling.
_SECTOR_ALIASES_TO_CANONICAL: dict[str, str] = {
    # Information Technology
    "information technology": "Information Technology",
    "technology": "Information Technology",
    "tech": "Information Technology",
    # Health
    "health care": "Health Care",
    "healthcare": "Health Care",
    # Consumer
    "consumer discretionary": "Consumer Discretionary",
    "consumer cyclical": "Consumer Discretionary",
    "consumer staples": "Consumer Staples",
    "consumer defensive": "Consumer Staples",
    # Materials
    "materials": "Materials",
    "basic materials": "Materials",
    # Financials (Yahoo often says "Financial Services")
    "financials": "Financials",
    "financial services": "Financials",
    # Communication Services (legacy GICS name)
    "communication services": "Communication Services",
    "telecommunication services": "Communication Services",
    "telecom": "Communication Services",
    "communications": "Communication Services",
    # Real estate
    "real estate": "Real Estate",
    # Other exact GICS names (help callers who already use official strings)
    "energy": "Energy",
    "industrials": "Industrials",
    "utilities": "Utilities",
    "industrial": "Industrials",  # occasional singular misuse
}

# No default ticker for unknown sectors (explicit None).


@lru_cache(maxsize=1)
def _load_mapping() -> tuple[str, str, dict[str, str], tuple[tuple[str, str, str], ...]]:
    """Returns (broad_ticker, broad_name, sector_key_to_ticker, ordered_rows)."""
    path = _yaml_path()
    if not path.is_file():
        raise FileNotFoundError(f"Missing benchmark config: {path}")

    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)

    bi = data.get("broad_index") or {}
    broad_ticker = str(bi.get("ticker", "SPY")).strip().upper()
    broad_name = str(bi.get("name", "")).strip()

    sector_key_to_ticker: dict[str, str] = {}
    rows: list[tuple[str, str, str]] = []

    for item in data.get("sectors") or []:
        gics = str(item.get("gics", "")).strip()
        t = str(item.get("ticker", "")).strip().upper()
        name = str(item.get("name", "")).strip()
        if not gics or not t:
            continue
        nkey = _normalize_sector_key(gics)
        sector_key_to_ticker[nkey] = t
        rows.append((gics, t, name))

    if len({r[1] for r in rows}) != len(rows):
        raise ValueError("gics_sector_etfs.yaml: duplicate tickers in sectors list")
    if len(rows) != 11:
        raise ValueError(
            f"gics_sector_etfs.yaml: expected 11 GICS sector rows, found {len(rows)}"
        )

    ordered = tuple(rows)
    return (broad_ticker, broad_name, sector_key_to_ticker, ordered)


def _broad() -> tuple[str, str]:
    t, n, _, _ = _load_mapping()
    return t, n


def get_broad_benchmark_ticker() -> str:
    """Total-return benchmark for \"vs index\" (excess vs broad market)."""
    t, _ = _broad()
    return t


def get_broad_benchmark_name() -> str:
    """Display name for the broad index ETF (from YAML)."""
    _, n = _broad()
    return n


# Public constants (resolved from YAML so a single file stays source of truth)
BROAD_BENCHMARK_TICKER: str = get_broad_benchmark_ticker()
BROAD_BENCHMARK_NAME: str = get_broad_benchmark_name()


def list_sector_etf_names() -> list[tuple[str, str, str]]:
    """Return ``(GICS sector name, ETF ticker, ETF name)`` for all 11 rows, YAML order.

    Handy for logging and UI dropdowns.
    """
    *_, ordered = _load_mapping()
    return list(ordered)


def sector_etf_ticker(gics_sector: str | None) -> str | None:
    """Map a vendor or GICS **sector** string to a SPDR sector ETF ticker.

    Returns ``None`` if *gics_sector* is empty, unrecognized, or ambiguous.
    Normalization: trim, collapse internal whitespace, case-insensitive. Includes
    aliases for common yfinance labels (e.g. \"Technology\" → ``XLK``).
    """
    if gics_sector is None:
        return None
    raw = str(gics_sector).strip()
    if not raw:
        return None

    n = _normalize_sector_key(raw)

    # Direct hit on official GICS name from YAML
    _, _, sector_key_to_ticker, _ = _load_mapping()
    if n in sector_key_to_ticker:
        return sector_key_to_ticker[n]

    # Alias → canonical GICS name as in YAML, then look up
    canonical = _SECTOR_ALIASES_TO_CANONICAL.get(n)
    if canonical is not None:
        cn = _normalize_sector_key(canonical)
        if cn in sector_key_to_ticker:
            return sector_key_to_ticker[cn]

    return None
