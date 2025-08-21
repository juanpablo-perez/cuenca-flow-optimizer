#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
plot_waiting_time_bar.py

Grouped bar chart of **average waiting time per scenario**, with controllers as series.
Each bar shows **mean ± 95% CI** (computed **over per-run means**) and a value label.

Data expectation
----------------
- `data/tripinfo.csv` with columns:
    ['controller', 'scenario', 'run', 'arrival', 'waitingTime']
  (Only 'controller', 'scenario', 'run', 'waitingTime' are required for this plot.)

Method
------
1) Compute **per-run mean waitingTime** first (to avoid bias from unbalanced run sizes).
2) For each (scenario, controller), aggregate across runs:
   - mean of per-run means
   - 95% CI (Student's t, df = n_runs − 1)
3) Render grouped bars (scenarios on X; controllers as series), with error bars and labels.

Usage
-----
    python -m plotters.plot_waiting_time_bar

Output
------
- PDF: `plots/waiting_time_bar_by_scenario.pdf`

Notes
-----
- This script uses the project's IEEE plotting style helpers.
- If `fuzzylts.utils.stats.load_all_tripinfo` is available, it will be used; otherwise,
  the script falls back to `data/tripinfo.csv`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Sequence, Tuple

import logging

import matplotlib.pyplot as plt
import numpy as np
import numpy.typing as npt
import pandas as pd
from scipy.stats import t

# Project styling helpers
from plotters.ieee_style import (  # type: ignore
    set_ieee_style,
    new_figure,
    arch_color_intense,
)

# Optional project loader
try:
    # Preferred: load from your module (returns a DataFrame like tripinfo.csv)
    from fuzzylts.utils.stats import load_all_tripinfo  # type: ignore
except Exception:
    load_all_tripinfo = None  # type: ignore[assignment]

# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

SCENARIOS: List[str] = ["low", "medium", "high", "very_high", "medium_extended"]
CONTROLLERS: List[str] = ["static", "actuated", "gap_fuzzy"]

OUTPUT_DIR: Path = Path("plots")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

TRIPINFO_CSV_FALLBACK: Path = Path("data/tripinfo.csv")
CONFIDENCE: float = 0.95

# Logging
LOGGER = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Data loading & validation
# ─────────────────────────────────────────────────────────────────────────────
def read_tripinfo() -> pd.DataFrame:
    """Read tripinfo data via project loader or CSV fallback and validate columns.

    Returns:
        A cleaned DataFrame with at least:
        ['controller', 'scenario', 'run', 'waitingTime']

    Raises:
        FileNotFoundError: If CSV fallback is required but not found.
        ValueError: If required columns are missing after normalization.
    """
    if callable(load_all_tripinfo):
        df = load_all_tripinfo()  # type: ignore[misc]
        LOGGER.info("Loaded tripinfo using fuzzylts.utils.stats.load_all_tripinfo()")
    else:
        if not TRIPINFO_CSV_FALLBACK.exists():
            raise FileNotFoundError(
                f"tripinfo not found. Expected {TRIPINFO_CSV_FALLBACK} "
                "or a working fuzzylts.utils.stats.load_all_tripinfo()."
            )
        df = pd.read_csv(TRIPINFO_CSV_FALLBACK, low_memory=False)
        LOGGER.info("Loaded tripinfo CSV: %s", TRIPINFO_CSV_FALLBACK)

    # Normalize common column variants
    rename_map: Dict[str, str] = {}
    if "run_id" in df.columns and "run" not in df.columns:
        rename_map["run_id"] = "run"
    if "waiting_time" in df.columns and "waitingTime" not in df.columns:
        rename_map["waiting_time"] = "waitingTime"
    if "arriveTime" in df.columns and "arrival" not in df.columns:
        rename_map["arriveTime"] = "arrival"
    if rename_map:
        df = df.rename(columns=rename_map)

    required = {"controller", "scenario", "run", "waitingTime"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns in tripinfo: {sorted(missing)}")

    # Dtypes & basic sanity
    df["run"] = df["run"].astype(str)
    df["waitingTime"] = pd.to_numeric(df["waitingTime"], errors="coerce")

    # Keep finite, non-negative waiting times
    df = df[np.isfinite(df["waitingTime"])]
    df = df[df["waitingTime"] >= 0]

    if df.empty:
        raise ValueError("tripinfo is empty after cleaning required columns.")
    return df


# ─────────────────────────────────────────────────────────────────────────────
# Stats computation
# ─────────────────────────────────────────────────────────────────────────────
def _mean_ci_from_per_run(
    vals: pd.Series, confidence: float = CONFIDENCE
) -> Tuple[float, float, int]:
    """Compute (mean, CI half-width, n) for a vector of per-run means.

    If n <= 1, CI half-width is 0.
    """
    x = vals.dropna()
    n = int(x.shape[0])
    mean = float(x.mean()) if n > 0 else float("nan")
    if n <= 1:
        return mean, 0.0, n
    sem = float(x.sem())
    tcrit = float(t.ppf(0.5 * (1 + confidence), df=n - 1))
    return mean, sem * tcrit, n


def compute_waiting_time_stats(
    df: pd.DataFrame,
    scenarios: Sequence[str],
    controllers: Sequence[str],
) -> Tuple[npt.NDArray[np.float64], npt.NDArray[np.float64], npt.NDArray[np.int_]]:
    """Compute per-(scenario, controller) mean ± CI from per-run means.

    Returns:
        means: [S, C] matrix with mean waiting time (seconds)
        cis:   [S, C] matrix with CI half-width (seconds)
        ns:    [S, C] matrix with number of runs
    """
    # Per-run mean waiting time
    per_run = (
        df.groupby(["scenario", "controller", "run"], as_index=False)["waitingTime"]
        .mean()
        .rename(columns={"waitingTime": "waitingTime_mean_per_run"})
    )

    S, C = len(scenarios), len(controllers)
    means = np.zeros((S, C), dtype=np.float64)
    cis = np.zeros((S, C), dtype=np.float64)
    ns = np.zeros((S, C), dtype=np.int_)

    for i, scen in enumerate(scenarios):
        g_scen = per_run[per_run["scenario"] == scen]
        for j, ctrl in enumerate(controllers):
            g = g_scen[g_scen["controller"] == ctrl]
            m, ci, n = _mean_ci_from_per_run(g["waitingTime_mean_per_run"])
            means[i, j] = 0.0 if not np.isfinite(m) else m
            cis[i, j] = 0.0 if not np.isfinite(ci) else ci
            ns[i, j] = n

    return means, cis, ns


# ─────────────────────────────────────────────────────────────────────────────
# Plot
# ─────────────────────────────────────────────────────────────────────────────
def plot_grouped_bars(
    means: npt.NDArray[np.float64],
    cis: npt.NDArray[np.float64],
    scenarios: Sequence[str],
    controllers: Sequence[str],
    *,
    outpath: Path,
) -> None:
    """Render grouped bars (scenarios × controllers) with mean ± CI and labels."""
    set_ieee_style()
    fig, ax = new_figure(columns=2)

    n_scen = len(scenarios)
    n_ctrl = len(controllers)
    x = np.arange(n_scen, dtype=float)

    total_width = 0.8
    bar_width = total_width / max(n_ctrl, 1)
    offsets = (np.arange(n_ctrl) - (n_ctrl - 1) / 2.0) * bar_width

    max_ci = float(np.nanmax(cis)) if cis.size else 0.0

    for j, ctrl in enumerate(controllers):
        heights = means[:, j]
        errors = cis[:, j]
        xpos = x + offsets[j]

        bars = ax.bar(
            xpos,
            heights,
            width=bar_width,
            yerr=errors,
            capsize=5,
            label=ctrl.replace("_", " ").capitalize(),
            color=arch_color_intense(j),  # palette from ieee_style
        )

        # Compute dynamic label offset after autoscale is known
        y_min, y_max = ax.get_ylim()
        y_offset = max((y_max - y_min) * 0.02, max_ci * 0.25) if y_max > y_min else (max_ci * 0.25 or 1.0)

        for bar in bars:
            h = bar.get_height()
            ax.text(
                bar.get_x() + bar.get_width() / 2.0,
                h + y_offset,
                f"{h:.1f}",
                ha="center",
                va="bottom",
                fontsize=7,
            )

    ax.set_xticks(x)
    ax.set_xticklabels([s.replace("_", " ").capitalize() for s in scenarios])
    ax.set_ylabel("Mean waiting time (s)")
    ax.set_xlabel("Scenarios")
    ax.legend(
        title="Controller",
        loc="upper center",
        bbox_to_anchor=(0.5, 1.20),
        ncol=min(3, n_ctrl),
        frameon=False,
    )
    ax.grid(axis="y")
    plt.tight_layout()

    outpath.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(outpath, bbox_inches="tight")
    LOGGER.info("Saved figure: %s", outpath)

    # Show for interactive workflows; harmless in headless backends
    plt.show()
    plt.close(fig)


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────
def main() -> None:
    """Entry-point for module execution."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    df = read_tripinfo()
    means, cis, ns = compute_waiting_time_stats(df, SCENARIOS, CONTROLLERS)

    # Optional sanity logs (disabled by default)
    # LOGGER.debug("n_runs matrix:\n%s", ns)
    # LOGGER.debug("means:\n%s", means)
    # LOGGER.debug("cis:\n%s", cis)

    out = OUTPUT_DIR / "waiting_time_bar_by_scenario.pdf"
    plot_grouped_bars(means, cis, SCENARIOS, CONTROLLERS, outpath=out)


if __name__ == "__main__":
    main()
