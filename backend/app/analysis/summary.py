"""Optional qualitative summary stub.

Day 1: returns a fixed `DocumentSummary` flagged as a stub. The real
retrieval-first pipeline with `Qwen2.5-7B-Instruct` lands in a later
day; the API must already degrade gracefully when this layer is
unavailable, so the contract is in place from Day 1.
"""

from __future__ import annotations

from backend.app.models import AnalysisInput, DocumentSummary


def summarize_documents(analysis_input: AnalysisInput) -> DocumentSummary:
    """Return a deterministic stub document summary."""
    filings = analysis_input.filings
    source_filings = [f.accession_number for f in filings[:3]]

    return DocumentSummary(
        management_tone="neutral",
        guidance_direction="unknown",
        top_risks=[
            "Stub risk pending qualitative model integration.",
        ],
        top_positives=[
            "Stub positive pending qualitative model integration.",
        ],
        thesis_paragraph=(
            "Placeholder qualitative thesis. The qualitative summary layer "
            "will replace this with retrieval-grounded model output once "
            "the local inference path is wired up."
        ),
        source_filings=source_filings,
        available=True,
    )
