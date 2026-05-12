# Bugs To Revisit

## 2026-05-01 - L2 qualitative smoke fails DocumentSummary validation

- **Command:** `python -m backend.scripts.smoke_qualitative AAPL`
- **Environment:** local Windows, `.stock-analyzer-venv`, Ollama with `qwen2.5:7b`
- **Observed error:** `backend.app.errors.LLMError: Qualitative summary unavailable: two consecutive Ollama responses failed validation`
- **Primary failure mode:** model returns nested/invalid payload shape (for example `systemResponse -> jsonObject`) instead of direct `DocumentSummary` fields.
- **Validation failures seen:**
  - Missing required fields (`tone`, `thesis`, `positives`, `risks`, `guidance_flavor`, `evidence_quality`, `prompt_version`, `model_name`, `chunk_ids`)
  - Extra fields (`systemResponse`)
  - Wrong enum/string types on retry (`tone=""`, `guidance_flavor=""`, `evidence_quality=""`, list fields returned as string)
- **Impact:** L2 qualitative summary cannot complete for smoke run; endpoint path depending on this can degrade to unavailable.
- **Next fix direction:**
  - Add robust response unwrapping/normalization before Pydantic validation
  - Harden prompt/output contract for strict JSON object schema
  - Keep retry, but coerce known enum synonyms and empty-string invalids to safe defaults

