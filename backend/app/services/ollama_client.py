"""Thin async HTTP wrapper around the Ollama chat API.

We call the Ollama HTTP API directly (POST /api/chat) rather than using the
ollama Python client package to avoid an additional dependency.
"""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from typing import Any

import httpx

from backend.app.config import Settings, get_settings
from backend.app.errors import LLMError


logger = logging.getLogger(__name__)


class OllamaClient:
    """Async Ollama chat client using httpx."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def generate_json(
        self,
        *,
        system: str,
        user: str,
        model: str | None = None,
        timeout_s: float | None = None,
    ) -> dict[str, Any]:
        """Call POST /api/chat with format=json and stream=false.

        Returns the parsed JSON object from the assistant message content.

        Raises
        ------
        LLMError
            On HTTP error, connection timeout, or unparseable JSON response.
        """
        base_url = self._settings.ollama_base_url
        if not base_url:
            raise LLMError("OLLAMA_BASE_URL is not configured.")

        effective_model = model or self._settings.ollama_model
        effective_timeout = timeout_s if timeout_s is not None else self._settings.ollama_timeout_s

        payload = {
            "model": effective_model,
            "format": "json",
            "stream": False,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }

        url = f"{base_url.rstrip('/')}/api/chat"
        logger.debug("Calling Ollama model=%s url=%s", effective_model, url)

        try:
            async with httpx.AsyncClient(timeout=effective_timeout) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise LLMError(f"Ollama request timed out: {exc}") from exc
        except httpx.HTTPStatusError as exc:
            raise LLMError(
                f"Ollama returned HTTP {exc.response.status_code}: {exc.response.text[:200]}"
            ) from exc
        except httpx.RequestError as exc:
            raise LLMError(f"Ollama connection error: {exc}") from exc

        try:
            body = response.json()
            content: str = body["message"]["content"]
            return json.loads(content)
        except (KeyError, ValueError, json.JSONDecodeError) as exc:
            raise LLMError(f"Ollama response could not be parsed as JSON: {exc}") from exc


@lru_cache(maxsize=8)
def get_ollama_client(settings: Settings | None = None) -> OllamaClient:
    """Return a cached OllamaClient for the given settings (or the default settings)."""
    return OllamaClient(settings or get_settings())
