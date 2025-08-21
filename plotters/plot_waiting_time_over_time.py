#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
plot_waiting_time_over_time.py

Average per-vehicle waiting time vs. simulation time (BIN_WIDTH-second bins),
with across-run mean ± 95% confidence interval (Student's t, df = n_runs - 1).

Method
------
1) Bin by simulation time (`BIN_WIDTH` seconds) using each trip's `arrival` time.
2) Compute per-run mean `waitingTime` within each bin.
3) Aggregate across runs per bin: mean ± 95% CI.
4) (Optional) Smooth aggregated series with a centered rolling window (size = 3).

Input
-----
- Tripinfo table with at least: ['controller', 'scenario', 'run', 'waitingTime', 'arrival'].
  By default, loaded from `fuzzylts.utils.stats.load_all_tripinfo()` if available,
  otherwise from CSV fallback: `data/tripinfo.csv`.

Output
------
- PDF: `plots/waiting_time_over_time_<SCENARIO>.pdf`

Usage
-----
    python -m plotters.plot_waiting_time_over_time
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Sequence

import logging

import matplotlib.pyplot as plt
import numpy as np
import numpy.typing as npt
import pandas as pd
from scipy.stats import t

# Project styling helpers (kept as-is)
from plotters.ieee_style import (  # type: ignore
    set_ieee_style,
    new_figure,
    arch_color_intense,
)

# Optional project loader
try:
    from fuzzylts.utils.stats import load_all_tripinfo  # type: ignore
except Exception:
    load_all_tripinfo = None  # fallback to CSV below

# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

SCENARIO: str = "medium_extended"  # low / medium / high / very_high / medium_extended
CONTROLLERS: List[str] = ["static", "actuated", "gap_fuzzy"]

BIN_WIDTH: int = 900         # seconds (10 min)
SMOOTH_WINDOW: int = 3       # rolling window size for smoothing (centered)
CONFIDENCE: float = 0.95

OUTPUT_DIR: Path = Path("plots")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

TRIPINFO_CSV_FALLBACK: Path = Path("data/tripinfo.csv")

# Logging
LOGGER = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Utils
# ─────────────────────────────────────────────────────────────────────────────
def _human_time(sec: int) -> str:
    """Format seconds since t=0 as zero-padded `HH:MM`."""
    h = sec // 3600
    m = (sec % 3600) // 60
    return f"{h:02d}:{m:02d}"


def _read_tripinfo() -> pd.DataFrame:
    """Load tripinfo via project loader or CSV fallback; normalize columns & dtypes.

    Returns:
        DataFrame with required columns:
        ['controller', 'scenario', 'run', 'waitingTime', 'arrival'].

    Raises:
        FileNotFoundError: If CSV fallback is required but not present.
        ValueError: If required columns are missing or invalid after normalization.
    """
    if callable(load_all_tripinfo):
        df = load_all_tripinfo()  # type: ignore[misc]
        LOGGER.info("Loaded tripinfo using fuzzylts.utils.stats.load_all_tripinfo().")
    else:
        if not TRIPINFO_CSV_FALLBACK.exists():
            raise FileNotFoundError(
                f"tripinfo not found: {TRIPINFO_CSV_FALLBACK} "
                "or a working fuzzylts.utils.stats.load_all_tripinfo()."
            )
        df = pd.read_csv(TRIPINFO_CSV_FALLBACK, low_memory=False)
        LOGGER.info("Loaded tripinfo CSV: %s", TRIPINFO_CSV_FALLBACK)

    # Normalize possible variants
    rename_map: Dict[str, str] = {}
    if "run_id" in df.columns and "run" not in df.columns:
        rename_map["run_id"] = "run"
    if "waiting_time" in df.columns and "waitingTime" not in df.columns:
        rename_map["waiting_time"] = "waitingTime"
    if "arriveTime" in df.columns and "arrival" not in df.columns:
        rename_map["arriveTime"] = "arrival"
    if rename_map:
        df = df.rename(columns=rename_map)

    required = {"controller", "scenario", "run", "waitingTime", "arrival"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns in tripinfo: {sorted(missing)}")

    # Dtypes & basic sanity
    df["run"] = df["run"].astype(str)
    df["waitingTime"] = pd.to_numeric(df["waitingTime"], errors="coerce")
    df["arrival"] = pd.to_numeric(df["arrival"], errors="coerce")

    df = df[df["waitingTime"].notna() & df["arrival"].notna() & (df["waitingTime"] >= 0)]
    if df.empty:
        raise ValueError("tripinfo is empty after cleaning required columns.")
    return df


def _aggregate_over_time(
    df_scen: pd.DataFrame,
    controllers: Sequence[str],
    bin_width: int,
    smooth_window: int = 3,
) -> Dict[str, pd.DataFrame]:
    """Aggregate waiting time over time and compute mean ± CI per controller.

    For each controller, returns a DataFrame with:
        ['controller', 'bin_left', 'n_runs',
         'mean', 'ci95_low', 'ci95_high',
         'mean_s', 'ci95_low_s', 'ci95_high_s']

    Args:
        df_scen: Dataframe filtered to the selected scenario.
        controllers: Controllers to include (order is preserved).
        bin_width: Bin width in seconds (e.g., 900).
        smooth_window: Smoothing window for the aggregated series; if <= 1, no smoothing.

    Returns:
        Mapping controller → summary table with per-bin statistics.
    """
    out: Dict[str, pd.DataFrame] = {}

    # Use integer-based bins via floor-division to ensure aligned `bin_left`
    df_scen = df_scen.assign(bin_left=(df_scen["arrival"] // bin_width).astype(int) * bin_width)

    for ctl in controllers:
        sub = df_scen[df_scen["controller"] == ctl].copy()
        if sub.empty:
            continue

        # Per-run mean waiting time per bin
        per_run = (
            sub.groupby(["bin_left", "run"], as_index=False)["waitingTime"]
            .mean()
            .rename(columns={"waitingTime": "mean_wait_per_run"})
        )

        # Pivot: rows = bin_left, cols = run, values = per-run mean waiting time
        pivot = per_run.pivot(index="bin_left", columns="run", values="mean_wait_per_run").sort_index()

        # Across-run statistics per bin
        mean = pivot.mean(axis=1)
        n = pivot.count(axis=1)  # runs with data for that bin
        std = pivot.std(axis=1, ddof=1)
        sem = std / np.sqrt(n.replace(0, np.nan))

        # Student t critical per bin (df = n-1); if n <= 1 → CI = 0
        tcrit = t.ppf(0.5 * (1 + CONFIDENCE), df=(n - 1).clip(lower=1))
        ci_half = (sem * tcrit).where(n > 1, 0.0)

        out_df = pd.DataFrame(
            {
                "controller": ctl,
                "bin_left": mean.index.astype(int),
                "n_runs": n.astype(int).values,
                "mean": mean.values,
                "ci95_low": (mean - ci_half).values,
                "ci95_high": (mean + ci_half).values,
            }
        )

        # Optional smoothing on the aggregated series
        if smooth_window and smooth_window > 1:
            out_df["mean_s"] = out_df["mean"].rolling(smooth_window, center=True, min_periods=1).mean()
            out_df["ci95_low_s"] = out_df["ci95_low"].rolling(smooth_window, center=True, min_periods=1).mean()
            out_df["ci95_high_s"] = out_df["ci95_high"].rolling(smooth_window, center=True, min_periods=1).mean()
        else:
            out_df["mean_s"] = out_df["mean"]
            out_df["ci95_low_s"] = out_df["ci95_low"]
            out_df["ci95_high_s"] = out_df["ci95_high"]

        out[ctl] = out_df

    return out


# ─────────────────────────────────────────────────────────────────────────────
# Plot
# ─────────────────────────────────────────────────────────────────────────────
def plot_waiting_time_over_time(
    series_by_ctrl: Dict[str, pd.DataFrame],
    controllers: Sequence[str],
    *,
    outpath: Path,
) -> None:
    """Render mean ± CI over time; X ticks at full hours as `H:00`."""
    set_ieee_style()
    fig, ax = new_figure(columns=2)

    plotted_any = False
    for i, ctl in enumerate(controllers):
        tbl = series_by_ctrl.get(ctl)
        if tbl is None or tbl.empty:
            continue

        x: npt.NDArray[np.int_] = tbl["bin_left"].to_numpy(dtype=int)  # seconds since t=0
        y: npt.NDArray[np.float_] = tbl["mean_s"].to_numpy(dtype=float)
        lo: npt.NDArray[np.float_] = tbl["ci95_low_s"].to_numpy(dtype=float)
        hi: npt.NDArray[np.float_] = tbl["ci95_high_s"].to_numpy(dtype=float)

        ax.plot(x, y, label=ctl.replace("_", " ").capitalize(), marker="o", color=arch_color_intense(i))
        ax.fill_between(x, lo, hi, alpha=0.2, color=arch_color_intense(i))
        plotted_any = True

    if not plotted_any:
        raise RuntimeError("No data to plot for the selected scenario/controllers.")

    # Force ticks at full hours (H:00) using the combined range across controllers
    xmin = min(tbl["bin_left"].min() for tbl in series_by_ctrl.values() if not tbl.empty)
    xmax = max(tbl["bin_left"].max() for tbl in series_by_ctrl.values() if not tbl.empty)
    start = (int(xmin) // 3600) * 3600                     # round down to full hour
    end = ((int(xmax) + 3599) // 3600) * 3600              # round up to full hour
    hour_ticks = np.arange(start, end + 1, 3600, dtype=int)

    ax.set_xticks(hour_ticks)
    ax.set_xticklabels([f"{int(t // 3600)}:00" for t in hour_ticks])  # no leading zero on hours

    ax.set_xlabel("Simulation time (HH:MM)")
    ax.set_ylabel("Mean waiting time (s)")
    ax.legend(
        title="Controller",
        loc="upper center",
        bbox_to_anchor=(0.5, 1.20),
        ncol=min(3, len(controllers)),
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

    df = _read_tripinfo()
    df_scen = df[df["scenario"] == SCENARIO].copy()

    series = _aggregate_over_time(
        df_scen,
        controllers=CONTROLLERS,
        bin_width=BIN_WIDTH,
        smooth_window=SMOOTH_WINDOW,
    )

    out = OUTPUT_DIR / f"waiting_time_over_time_{SCENARIO}.pdf"
    plot_waiting_time_over_time(series, CONTROLLERS, outpath=out)


if __name__ == "__main__":
    main()
