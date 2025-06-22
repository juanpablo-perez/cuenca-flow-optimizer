# src/fuzzylts/utils/stats.py

"""
Aggregate metrics loader and 95% confidence interval calculator.

Provides:
  - load_experiment_metrics: load all metrics.json files under experiments/ into a DataFrame
  - confidence_interval_95: compute the 95% CI for a numeric pandas Series
"""
from __future__ import annotations
from pathlib import Path
from typing import Tuple

import pandas as pd
from scipy.stats import t

# Confidence level for interval calculation
_CONFIDENCE = 0.95


def load_experiment_metrics(experiments_dir: Path = Path("experiments")) -> pd.DataFrame:
    """
    Load metrics.json from each experiment run into a single DataFrame.

    Args:
        experiments_dir: Path to the directory containing experiment subfolders.

    Returns:
        DataFrame with each row representing one run's metrics and metadata
        (controller, scenario, seed).
    """
    records: list[dict] = []
    for run_dir in experiments_dir.iterdir():
        metrics_file = run_dir / "metrics.json"
        if not metrics_file.exists():
            continue
        metrics = pd.read_json(metrics_file, typ="series").to_dict()
        # Extract metadata from folder name: <controller>_<scenario>_<seed>_...
        parts = run_dir.name.split("_")
        if len(parts) >= 3:
            metrics["controller"] = parts[0]
            metrics["scenario"]   = parts[1]
            try:
                metrics["seed"] = int(parts[2])
            except ValueError:
                metrics["seed"] = None
        records.append(metrics)
    return pd.DataFrame(records)


def confidence_interval_95(series: pd.Series) -> Tuple[float, float]:
    """
    Compute the 95% confidence interval for the mean of a sample.

    Uses Student's t-distribution.

    Args:
        series: pandas Series of numeric observations.

    Returns:
        Tuple (lower_bound, upper_bound).
    """
    n = series.count()
    if n < 2:
        return (series.mean(), series.mean())

    mean = series.mean()
    sem = series.sem()
    # t critical value for two-tailed
    t_crit = t.ppf((1 + _CONFIDENCE) / 2, df=n - 1)
    margin = sem * t_crit
    return (mean - margin, mean + margin)
