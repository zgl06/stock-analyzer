"""L2 qualitative summary schema.

DocumentSummary is the stable output contract for the qualitative LLM layer.
It is produced by QualitativeService and consumed by the analysis pipeline (L3).
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# Field-level constants
# ---------------------------------------------------------------------------

_THESIS_MAX = 600
_THESIS_MIN = 20
_BULLET_MAX = 240
_LIST_MIN = 2
_LIST_MAX = 5

_DEFAULT_DISCLAIMER = (
    "Not investment advice. Generated from filings; may be incomplete."
)


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------


class DocumentSummary(BaseModel):
    """Rich qualitative summary produced by the LLM layer from filing chunks."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    tone: Literal["positive", "neutral", "cautious", "negative", "mixed"] = Field(
        ...,
        description="Overall tone of the retrieved filing excerpts.",
    )
    thesis: str = Field(
        ...,
        description=(
            "One paragraph (≤ 600 chars) plain-English bull/bear takeaway "
            "grounded in the retrieved chunks."
        ),
    )
    positives: list[str] = Field(
        ...,
        description="2–5 bullet strings (each ≤ 240 chars) citing positive signals.",
    )
    risks: list[str] = Field(
        ...,
        description="2–5 bullet strings (each ≤ 240 chars) citing risk factors.",
    )
    guidance_flavor: Literal[
        "raised", "reaffirmed", "lowered", "withdrawn", "none_mentioned"
    ] = Field(
        ...,
        description="Direction of forward guidance as stated in the filings.",
    )
    evidence_quality: Literal["strong", "moderate", "thin"] = Field(
        ...,
        description=(
            "thin when retrieval returned <2 useful chunks; "
            "strong/moderate otherwise based on chunk count and relevance."
        ),
    )
    disclaimer: str = Field(
        default=_DEFAULT_DISCLAIMER,
        description="Immutable legal disclaimer; not overridable by the model.",
    )
    prompt_version: str = Field(
        ...,
        description="Prompt template version used to produce this summary (set by service).",
    )
    model_name: str = Field(
        ...,
        description="Ollama model name used to generate this summary (set by service).",
    )
    chunk_ids: list[str] = Field(
        ...,
        description="IDs of the filing chunks fed to the model (set by service).",
    )

    # ------------------------------------------------------------------
    # Validators
    # ------------------------------------------------------------------

    @field_validator("thesis")
    @classmethod
    def _thesis_length(cls, v: str) -> str:
        stripped = v.strip()
        if len(stripped) < _THESIS_MIN:
            raise ValueError(
                f"thesis must be >= {_THESIS_MIN} chars, got {len(stripped)}"
            )
        if len(v) > _THESIS_MAX:
            raise ValueError(f"thesis must be <= {_THESIS_MAX} chars, got {len(v)}")
        return v

    @field_validator("positives", "risks")
    @classmethod
    def _bullet_list_bounds(cls, v: list[str]) -> list[str]:
        if len(v) < _LIST_MIN or len(v) > _LIST_MAX:
            raise ValueError(
                f"List must have {_LIST_MIN}-{_LIST_MAX} items, got {len(v)}"
            )
        for item in v:
            if len(item) > _BULLET_MAX:
                raise ValueError(
                    f"Each bullet must be <= {_BULLET_MAX} chars, got {len(item)!r}"
                )
        return v

    @model_validator(mode="after")
    def _disclaimer_locked(self) -> "DocumentSummary":
        # Ensure the disclaimer is always the canonical value regardless of what
        # the model emits. This runs after field assignment, so it's a final guard.
        if self.disclaimer != _DEFAULT_DISCLAIMER:
            object.__setattr__(self, "disclaimer", _DEFAULT_DISCLAIMER)
        return self
