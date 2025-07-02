# src/fuzzylts/utils/stats.py

"""
Aggregate experiment metrics and compute confidence intervals.
"""

from pathlib import Path
from typing import Any, Dict, List, Tuple

import pandas as pd
from scipy.stats import t

# Default confidence level for intervals (e.g. 95%)
CONFIDENCE = 0.95


def load_experiment_metrics(exp_dir: Path = Path("experiments")) -> pd.DataFrame:
    """
    Load all metrics.json files from subdirectories of `exp_dir`.
    Each run directory is expected to be named "<controller>_<scenario>_<seed>_...".
    Returns a DataFrame with one row per run and columns:
      controller, scenario, seed, avg_wait, avg_duration, avg_speed, vehicles, inserted,
      ended, teleports, sim_time, etc.
    """
    records: List[Dict[str, Any]] = []
    for run_dir in exp_dir.iterdir():
        if not run_dir.is_dir():
            continue
        metrics_file = run_dir / "metrics.json"
        if not metrics_file.exists():
            continue

        # load metrics.json into a dict
        rec = pd.read_json(metrics_file, typ="series").to_dict()

        # parse controller, scenario, seed from directory name
        parts = run_dir.name.split("_")
        if len(parts) >= 3:
            rec["controller"] = parts[0]
            rec["scenario"]   = parts[1]
            try:
                rec["seed"] = int(parts[2])
            except ValueError:
                rec["seed"] = parts[2]

        records.append(rec)

    return pd.DataFrame(records)


def ci(series: pd.Series, confidence: float = CONFIDENCE) -> Tuple[float, float]:
    """
    Compute two-sided confidence interval for a pandas Series.
    Returns (lower_bound, upper_bound). If insufficient data, returns (mean, mean).
    """
    n = series.count()
    mean = series.mean()
    if n < 2:
        return mean, mean

    sem = series.sem()  # standard error of the mean
    h = sem * t.ppf((1 + confidence) / 2, df=n - 1)
    return mean - h, mean + h
