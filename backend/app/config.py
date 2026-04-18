from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv


_CONFIG_DIR = Path(__file__).resolve().parent
_BACKEND_DIR = _CONFIG_DIR.parent
_REPO_ROOT = _BACKEND_DIR.parent

load_dotenv(_REPO_ROOT / ".env")
load_dotenv(_BACKEND_DIR / ".env")


@dataclass(frozen=True)
class Settings:
    app_env: str = "development"
    supabase_url: str | None = None
    supabase_service_role_key: str | None = None
    sec_user_agent: str = "stock-analyzer/0.1 (contact: dev@example.com)"
    sec_ticker_mapping_url: str = "https://www.sec.gov/files/company_tickers.json"
    sec_submissions_base_url: str = "https://data.sec.gov"
    sec_archives_base_url: str = "https://www.sec.gov"
    yfinance_history_period: str = "1y"
    yfinance_history_interval: str = "1mo"
    schema_version: str = "v1"

    @property
    def has_supabase(self) -> bool:
        return bool(self.supabase_url and self.supabase_service_role_key)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings(
        app_env=os.getenv("APP_ENV", "development"),
        supabase_url=os.getenv("SUPABASE_URL"),
        supabase_service_role_key=os.getenv("SUPABASE_SERVICE_ROLE_KEY"),
        sec_user_agent=os.getenv(
            "SEC_USER_AGENT",
            "stock-analyzer/0.1 (contact: dev@example.com)",
        ),
        sec_ticker_mapping_url=os.getenv(
            "SEC_TICKER_MAPPING_URL",
            "https://www.sec.gov/files/company_tickers.json",
        ),
        sec_submissions_base_url=os.getenv(
            "SEC_SUBMISSIONS_BASE_URL",
            "https://data.sec.gov",
        ),
        sec_archives_base_url=os.getenv(
            "SEC_ARCHIVES_BASE_URL",
            "https://www.sec.gov",
        ),
        yfinance_history_period=os.getenv("YFINANCE_HISTORY_PERIOD", "1y"),
        yfinance_history_interval=os.getenv("YFINANCE_HISTORY_INTERVAL", "1mo"),
        schema_version=os.getenv("ANALYSIS_INPUT_SCHEMA_VERSION", "v1"),
    )
