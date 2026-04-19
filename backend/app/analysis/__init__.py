"""Downstream analysis package.

Placeholder Day 1 boundaries for the modules Person 2 owns. Each
module accepts an `AnalysisInput` and produces one downstream output
type. Implementations are deterministic mocks until the real finance
logic is built out.
"""

from .forecast import build_forecast
from .peers import select_peers
from .pipeline import run_analysis_from_fixture, run_analysis_pipeline
from .scoring import score_company
from .summary import summarize_documents
from .verdict import assemble_verdict

__all__ = [
    "assemble_verdict",
    "build_forecast",
    "run_analysis_from_fixture",
    "run_analysis_pipeline",
    "score_company",
    "select_peers",
    "summarize_documents",
]
