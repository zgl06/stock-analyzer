from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class RetrievedChunk(BaseModel):
    """A single filing chunk returned by RAG retrieval."""

    model_config = ConfigDict(extra="forbid")

    chunk_id: str = Field(..., description="UUID of the filing_chunks row.")
    accession_number: str
    filing_type: str
    filing_date: date
    text: str
    score: float = Field(..., description="Cosine similarity score (0-1).")
    token_count: int
