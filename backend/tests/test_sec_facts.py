from __future__ import annotations

from datetime import date

from backend.app.services.sec_facts import extract_period_metrics


def _entry(*, end: str, val: float, filed: str, form: str = "10-K") -> dict:
    return {
        "end": end,
        "val": val,
        "fy": int(end[:4]),
        "fp": "FY",
        "form": form,
        "filed": filed,
        "accn": "0000000000-00-000000",
    }


def test_extract_period_metrics_returns_empty_for_missing_payload() -> None:
    assert extract_period_metrics(None) == {}
    assert extract_period_metrics({}) == {}
    assert extract_period_metrics({"facts": {}}) == {}


def test_extract_period_metrics_picks_freshest_filing_per_period() -> None:
    payload = {
        "facts": {
            "us-gaap": {
                "LongTermDebtNoncurrent": {
                    "units": {
                        "USD": [
                            _entry(end="2024-09-28", val=80_000_000_000, filed="2024-11-01"),
                            _entry(
                                end="2024-09-28",
                                val=82_000_000_000,
                                filed="2025-02-01",
                            ),
                        ]
                    }
                },
                "CashAndCashEquivalentsAtCarryingValue": {
                    "units": {
                        "USD": [
                            _entry(end="2024-09-28", val=29_000_000_000, filed="2024-11-01"),
                        ]
                    }
                },
            }
        }
    }

    result = extract_period_metrics(payload)

    assert result == {
        date(2024, 9, 28): {
            "long_term_debt_usd": 82_000_000_000.0,
            "cash_and_equivalents_usd": 29_000_000_000.0,
        }
    }


def test_extract_period_metrics_prefers_first_alias_when_both_present() -> None:
    payload = {
        "facts": {
            "us-gaap": {
                "CashAndCashEquivalentsAtCarryingValue": {
                    "units": {
                        "USD": [
                            _entry(end="2024-09-28", val=29_000_000_000, filed="2024-11-01"),
                        ]
                    }
                },
                "Cash": {
                    "units": {
                        "USD": [
                            _entry(end="2024-09-28", val=15_000_000_000, filed="2024-11-01"),
                        ]
                    }
                },
            }
        }
    }

    result = extract_period_metrics(payload)
    # Earlier alias in TAG_MAP wins.
    assert result[date(2024, 9, 28)]["cash_and_equivalents_usd"] == 29_000_000_000.0


def test_extract_period_metrics_skips_quarterly_entries() -> None:
    payload = {
        "facts": {
            "us-gaap": {
                "Revenues": {
                    "units": {
                        "USD": [
                            {
                                "end": "2024-06-30",
                                "val": 100,
                                "fy": 2024,
                                "fp": "Q3",
                                "form": "10-Q",
                                "filed": "2024-08-01",
                            },
                            _entry(end="2024-09-28", val=400, filed="2024-11-01"),
                        ]
                    }
                }
            }
        }
    }

    result = extract_period_metrics(payload)

    assert date(2024, 6, 30) not in result
    assert result[date(2024, 9, 28)] == {"revenue_usd": 400.0}


def test_extract_period_metrics_ignores_unknown_tags() -> None:
    payload = {
        "facts": {
            "us-gaap": {
                "SomeRandomTag": {
                    "units": {
                        "USD": [_entry(end="2024-09-28", val=1, filed="2024-11-01")]
                    }
                }
            }
        }
    }

    assert extract_period_metrics(payload) == {}
