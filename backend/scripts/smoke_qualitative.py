"""L2 qualitative summary smoke test: retrieve chunks, call Ollama, print result.

Usage:
    python -m backend.scripts.smoke_qualitative AAPL
    python -m backend.scripts.smoke_qualitative MSFT

Prereqs:
    1. Ollama running locally: `ollama serve`
    2. The configured model pulled: `ollama pull qwen2.5:7b`
       (or set OLLAMA_MODEL env var to a model you have pulled)
    3. backend/.env has SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY
    4. OLLAMA_BASE_URL set (default http://localhost:11434 if OLLAMA_BASE_URL not set,
       but OLLAMA_BASE_URL must be present in Settings or the call will fail)
    5. The ticker must have been indexed by L1:
         python -m backend.scripts.smoke_rag TICKER
"""

from __future__ import annotations

import asyncio
import json
import sys

from backend.app.config import get_settings
from backend.app.services.ollama_client import OllamaClient
from backend.app.services.qualitative import QualitativeService
from backend.app.services.rag import RagService


async def main(ticker: str) -> None:
    settings = get_settings()

    if not settings.has_supabase:
        print("ERROR: Supabase not configured. Check backend/.env.")
        sys.exit(1)

    if not settings.ollama_base_url:
        print("ERROR: OLLAMA_BASE_URL not configured. Check backend/.env.")
        sys.exit(1)

    rag = RagService(settings)
    ollama = OllamaClient(settings)
    svc = QualitativeService(settings, rag, ollama)

    print(f"Summarising {ticker} with model={settings.ollama_model} ...")
    summary = await svc.summarize(ticker.upper())

    print(json.dumps(summary.model_dump(), indent=2, default=str))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m backend.scripts.smoke_qualitative TICKER")
        sys.exit(1)
    asyncio.run(main(sys.argv[1]))
