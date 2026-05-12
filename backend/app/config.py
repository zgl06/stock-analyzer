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
    ollama_base_url: str | None = None
    ollama_model: str = "qwen2.5:7b"
    ollama_timeout_s: float = 240.0
    relative_model_path: str | None = None
    relative_model_features_path: str | None = None
    relative_model_predictions_path: str | None = None
    relative_model_sector_path: str | None = None
    relative_model_sector_features_path: str | None = None
    relative_model_sector_predictions_path: str | None = None
    embedding_model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    enable_qualitative_summary: bool = False
    max_8k_per_ticker: int = 8

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
        ollama_base_url=os.getenv("OLLAMA_BASE_URL"),
        ollama_model=os.getenv("OLLAMA_MODEL", "qwen2.5:7b"),
        ollama_timeout_s=float(os.getenv("OLLAMA_TIMEOUT_S", "240")),
        relative_model_path=os.getenv("RELATIVE_MODEL_PATH"),
        relative_model_features_path=os.getenv("RELATIVE_MODEL_FEATURES_PATH"),
        relative_model_predictions_path=os.getenv("RELATIVE_MODEL_PREDICTIONS_PATH"),
        relative_model_sector_path=os.getenv("RELATIVE_MODEL_SECTOR_PATH"),
        relative_model_sector_features_path=os.getenv("RELATIVE_MODEL_SECTOR_FEATURES_PATH"),
        relative_model_sector_predictions_path=os.getenv("RELATIVE_MODEL_SECTOR_PREDICTIONS_PATH"),
        embedding_model_name=os.getenv(
            "EMBEDDING_MODEL_NAME",
            "sentence-transformers/all-MiniLM-L6-v2",
        ),
        enable_qualitative_summary=os.getenv(
            "ENABLE_QUALITATIVE_SUMMARY", "false"
        ).lower() == "true",
        max_8k_per_ticker=int(os.getenv("MAX_8K_PER_TICKER", "8")),
    )
