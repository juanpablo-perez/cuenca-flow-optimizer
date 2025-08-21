#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
plot_emissions_over_time.py

CO₂ emissions vs. simulation time (BIN_WIDTH-second bins), with across-run
mean ± 95% confidence interval (Student's t, df = n_runs - 1).

Assumptions
-----------
- Input CSV column `CO2` is in **milligrams (mg)** per timestep.
- Values are converted mg → kg **before** computing statistics.

Method
------
1) Bin by `time` (seconds) using `BIN_WIDTH` (e.g., 900 = 15 min).
2) For each controller & bin: compute per-run CO₂ (sum in bin), convert to kg.
3) Aggregate across runs per bin: mean ± 95% CI.
4) Optional cosmetic smoothing (rolling window = 3, centered).
5) X-axis ticks forced at full hours and rendered as `H:00` (no leading zero).

Input CSV (default)
-------------------
`data/emissions_CO2.csv` with columns:
    ['time', 'CO2', 'controller', 'scenario', 'run']
where:
    - `time` is seconds (bin start),
    - `CO2` is mg per timestep.

Output
------
- PDF under `plots/`: `emissions_co2_over_time_<scenario>.pdf`

Usage
-----
    python -m plotters.plot_emissions_over_time
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

# Project styling helpers
from plotters.ieee_style import (  # type: ignore
    set_ieee_style,
    new_figure,
    arch_color_intense,
)

# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

SCENARIO: str = "medium_extended"  # e.g., 'low', 'medium', 'high', 'very_high', 'medium_extended'
CONTROLLERS: List[str] = ["static", "actuated", "gap_fuzzy"]

BIN_WIDTH: int = 900         # seconds; SUMO period is typically 900 (15 min)
SMOOTH_WINDOW: int = 3       # rolling window size (centered) for cosmetic smoothing

OUTPUT_DIR: Path = Path("plots")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

EMISSIONS_CSV_FALLBACK: Path = Path("data/emissions_CO2.csv")
CONFIDENCE: float = 0.95

# Units (mg → kg)
UNIT_FACTOR: float = 1e-6
UNIT_LABEL: str = "kg"

# Logging
LOGGER = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# IO & utils
# ─────────────────────────────────────────────────────────────────────────────
def _human_hh00(sec: int) -> str:
    """Format an absolute second count as `H:00` (no leading zero on hours)."""
    h = sec // 3600
    return f"{int(h)}:00"


def _read_emissions_co2(path: Path | None = None) -> pd.DataFrame:
    """Read and validate the emissions CSV.

    Required columns: `time (s)`, `CO2 (mg)`, `controller`, `scenario`, `run`.

    Args:
        path: Optional CSV path; defaults to `EMISSIONS_CSV_FALLBACK`.

    Returns:
        Cleaned dataframe with numeric `time` and `CO2`, and `run` as string.

    Raises:
        FileNotFoundError: If the CSV does not exist.
        ValueError: If required columns are missing or data is invalid.
    """
    csv_path = path or EMISSIONS_CSV_FALLBACK
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV not found: {csv_path}")

    df = pd.read_csv(csv_path, low_memory=False)

    # Normalize variants (backward compatibility)
    if "t_s" in df.columns and "time" not in df.columns:
        df = df.rename(columns={"t_s": "time"})

    required = {"time", "CO2", "controller", "scenario", "run"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns in emissions CSV: {sorted(missing)}")

    # Dtypes & basic sanity
    df["time"] = pd.to_numeric(df["time"], errors="coerce")
    df["CO2"] = pd.to_numeric(df["CO2"], errors="coerce")  # mg
    df["run"] = df["run"].astype(str)

    df = df[df["time"].notna() & df["CO2"].notna()]
    if df.empty:
        raise ValueError("Emissions CSV is empty after cleaning numeric columns.")
    return df


# ─────────────────────────────────────────────────────────────────────────────
# Aggregation
# ─────────────────────────────────────────────────────────────────────────────
def _aggregate_over_time(
    df_scen: pd.DataFrame,
    controllers: Sequence[str],
    bin_width: int,
    smooth_window: int,
) -> Dict[str, pd.DataFrame]:
    """Aggregate CO₂ over time and compute mean ± CI per controller.

    Returns, per controller, a DataFrame with:
        ['controller', 'bin_left', 'n_runs',
         'mean_kg', 'ci95_low_kg', 'ci95_high_kg',
         'mean_kg_s', 'ci95_low_kg_s', 'ci95_high_kg_s']

    Args:
        df_scen: DataFrame filtered to a single scenario.
        controllers: Controllers to include (order is preserved).
        bin_width: Bin width in seconds (e.g., 900).
        smooth_window: Optional smoothing window; if <= 1, no smoothing.

    Returns:
        Mapping controller → summary table.
    """
    out: Dict[str, pd.DataFrame] = {}

    # Align bins across controllers using integer `bin_left`
    df_scen = df_scen.assign(bin_left=(df_scen["time"] // bin_width).astype(int) * bin_width)

    for ctl in controllers:
        sub = df_scen[df_scen["controller"] == ctl].copy()
        if sub.empty:
            continue

        # Per-run CO₂ per bin (sum within bin) in mg → convert to kg before stats
        per_run = (
            sub.groupby(["bin_left", "run"], as_index=False)["CO2"]
            .sum()
            .rename(columns={"CO2": "co2_mg_per_run"})
        )
        per_run["co2_kg_per_run"] = per_run["co2_mg_per_run"] * UNIT_FACTOR

        # Pivot: rows = bin_left, cols = run
        pivot = per_run.pivot(index="bin_left", columns="run", values="co2_kg_per_run").sort_index()

        # Across-run statistics per bin
        mean = pivot.mean(axis=1)
        n = pivot.count(axis=1)
        std = pivot.std(axis=1, ddof=1)
        sem = std / np.sqrt(n.replace(0, np.nan))
        tcrit = t.ppf(0.5 * (1 + CONFIDENCE), df=(n - 1).clip(lower=1))
        ci_half = (sem * tcrit).where(n > 1, 0.0)

        tbl = pd.DataFrame(
            {
                "controller": ctl,
                "bin_left": mean.index.astype(int),
                "n_runs": n.astype(int).values,
                "mean_kg": mean.values,
                "ci95_low_kg": (mean - ci_half).values,
                "ci95_high_kg": (mean + ci_half).values,
            }
        )

        # Optional smoothing
        if smooth_window and smooth_window > 1:
            tbl["mean_kg_s"] = tbl["mean_kg"].rolling(smooth_window, center=True, min_periods=1).mean()
            tbl["ci95_low_kg_s"] = tbl["ci95_low_kg"].rolling(smooth_window, center=True, min_periods=1).mean()
            tbl["ci95_high_kg_s"] = tbl["ci95_high_kg"].rolling(smooth_window, center=True, min_periods=1).mean()
        else:
            tbl["mean_kg_s"] = tbl["mean_kg"]
            tbl["ci95_low_kg_s"] = tbl["ci95_low_kg"]
            tbl["ci95_high_kg_s"] = tbl["ci95_high_kg"]

        out[ctl] = tbl

    return out


# ─────────────────────────────────────────────────────────────────────────────
# Plot
# ─────────────────────────────────────────────────────────────────────────────
def plot_emissions_over_time(
    series_by_ctrl: Dict[str, pd.DataFrame],
    controllers: Sequence[str],
    *,
    outpath: Path,
) -> None:
    """Render smoothed mean ± CI over time; X ticks at full hours (H:00)."""
    set_ieee_style()
    fig, ax = new_figure(columns=2)

    plotted_any = False
    xmin: int | None = None
    xmax: int | None = None

    for i, ctl in enumerate(controllers):
        tbl = series_by_ctrl.get(ctl)
        if tbl is None or tbl.empty:
            continue

        x: npt.NDArray[np.int_] = tbl["bin_left"].to_numpy(dtype=int)
        y: npt.NDArray[np.float_] = tbl["mean_kg_s"].to_numpy(dtype=float)
        lo: npt.NDArray[np.float_] = tbl["ci95_low_kg_s"].to_numpy(dtype=float)
        hi: npt.NDArray[np.float_] = tbl["ci95_high_kg_s"].to_numpy(dtype=float)

        ax.plot(x, y, label=ctl.replace("_", " ").capitalize(), marker="o", color=arch_color_intense(i))
        ax.fill_between(x, lo, hi, alpha=0.2, color=arch_color_intense(i))
        plotted_any = True

        xmin = int(x.min()) if xmin is None else min(xmin, int(x.min()))
        xmax = int(x.max()) if xmax is None else max(xmax, int(x.max()))

    if not plotted_any:
        raise RuntimeError("No data to plot for the selected scenario/controllers.")

    # Force ticks at full hours (H:00)
    assert xmin is not None and xmax is not None
    start = (xmin // 3600) * 3600
    end = ((xmax + 3599) // 3600) * 3600
    hour_ticks = np.arange(start, end + 1, 3600, dtype=int)
    ax.set_xticks(hour_ticks)
    ax.set_xticklabels([_human_hh00(int(t)) for t in hour_ticks])

    ax.set_xlabel("Simulation time (HH:MM)")
    ax.set_ylabel(f"CO₂ emissions ({UNIT_LABEL})")
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

    df = _read_emissions_co2()

    # Use the requested scenario if present; otherwise fall back to the first available.
    unique_scen = set(df["scenario"])
    scen = SCENARIO if SCENARIO in unique_scen else sorted(unique_scen)[0]

    df_scen = df[df["scenario"] == scen].copy()

    # Limit controllers to those actually present (preserve requested order)
    present_ctrls = [c for c in CONTROLLERS if c in set(df_scen["controller"])]
    if not present_ctrls:
        present_ctrls = sorted(df_scen["controller"].unique().tolist())

    series = _aggregate_over_time(
        df_scen,
        controllers=present_ctrls,
        bin_width=BIN_WIDTH,
        smooth_window=SMOOTH_WINDOW,
    )

    out = OUTPUT_DIR / f"emissions_co2_over_time_{scen}.pdf"
    plot_emissions_over_time(series, present_ctrls, outpath=out)


if __name__ == "__main__":
    main()