"""Downstream analysis package.

Placeholder Day 1 boundaries for the modules Person 2 owns. Each
module accepts an `AnalysisInput` and produces one downstream output
type. Implementations are deterministic mocks until the real finance
logic is built out.
"""

from .benchmarks import (
    BROAD_BENCHMARK_NAME,
    BROAD_BENCHMARK_TICKER,
    list_sector_etf_names,
    sector_etf_ticker,
)
from .excess_returns import (
    HOLDING_YEARS,
    add_calendar_years,
    five_year_excess_table,
    resolve_sector_name,
)
from .forecast import build_forecast
from .feature_dataset import (
    FeatureBuildReport,
    YFinanceFeatureProvider,
    build_feature_dataset_from_labels,
    read_existing_feature_output,
    write_feature_output,
)
from .label_dataset import (
    LabelBuildReport,
    build_label_dataset,
    generate_as_of_dates,
    load_sector_file,
    load_tickers_file,
    read_existing_label_output,
    write_label_output,
)
from .label_returns import (
    StockLabelReturn,
    clear_merger_overrides,
    register_merger_override,
    total_return_stock_for_label,
)
from .modeling_baselines import (
    evaluate_baselines,
    infer_feature_columns,
    prepare_training_frame,
    split_by_time,
    top_tercile_hit_rate,
)
from .modeling_train import (
    gate_decision,
    train_lightgbm_regressor,
)
from .peers import select_peers
from .returns import total_return_simple
from .pipeline import run_analysis_from_fixture, run_analysis_pipeline
from .scoring import score_company
from .summary import summarize_documents
from .verdict import assemble_verdict

__all__ = [
    "BROAD_BENCHMARK_NAME",
    "BROAD_BENCHMARK_TICKER",
    "HOLDING_YEARS",
    "add_calendar_years",
    "assemble_verdict",
    "build_feature_dataset_from_labels",
    "build_forecast",
    "build_label_dataset",
    "clear_merger_overrides",
    "FeatureBuildReport",
    "generate_as_of_dates",
    "LabelBuildReport",
    "load_sector_file",
    "load_tickers_file",
    "evaluate_baselines",
    "five_year_excess_table",
    "infer_feature_columns",
    "gate_decision",
    "list_sector_etf_names",
    "prepare_training_frame",
    "read_existing_feature_output",
    "read_existing_label_output",
    "run_analysis_from_fixture",
    "register_merger_override",
    "resolve_sector_name",
    "run_analysis_pipeline",
    "score_company",
    "sector_etf_ticker",
    "select_peers",
    "split_by_time",
    "StockLabelReturn",
    "summarize_documents",
    "total_return_simple",
    "total_return_stock_for_label",
    "top_tercile_hit_rate",
    "train_lightgbm_regressor",
    "YFinanceFeatureProvider",
    "write_feature_output",
    "write_label_output",
]
