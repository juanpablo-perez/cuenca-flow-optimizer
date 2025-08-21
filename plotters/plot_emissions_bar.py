#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
plot_emissions_bar.py

Grouped bar chart of total CO₂ per scenario with controllers as series.
Bars display mean total CO₂ per run ± 95% confidence interval (Student's t, df = n_runs - 1).

Assumptions
-----------
- Input CSV column `CO2` is in **milligrams (mg)** per timestep bin.
- Values are converted mg → kg **before** computing per-run totals and statistics.

Usage
-----
    python -m plotters.plot_emissions_bar

Inputs
------
- CSV: `data/emissions_CO2.csv` (default), with columns:
    ['time', 'CO2', 'controller', 'scenario', 'run']

Outputs
-------
- PDF: `plots/emissions_co2_bar_by_scenario.pdf`

Notes
-----
- This script targets publication-quality figures using the project's IEEE styling helpers.
- Missing scenarios/controllers are skipped gracefully while preserving the requested order.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Sequence, Tuple

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

# Preferred order; missing items are skipped gracefully
SCENARIOS: List[str] = ["low", "medium", "high", "very_high", "medium_extended"]
CONTROLLERS: List[str] = ["static", "actuated", "gap_fuzzy"]

EMISSIONS_CSV_FALLBACK: Path = Path("data/emissions_CO2.csv")

OUTPUT_DIR: Path = Path("plots")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

CONFIDENCE: float = 0.95

# Units (mg → kg)
UNIT_FACTOR: float = 1e-6
UNIT_LABEL: str = "kg"

# Logging
LOGGER = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# IO & validation
# ─────────────────────────────────────────────────────────────────────────────
def _read_emissions_co2(path: Path | None = None) -> pd.DataFrame:
    """Read the emissions CSV and validate required columns.

    The CSV must contain: ``['time', 'CO2', 'controller', 'scenario', 'run']``.

    - ``time`` is in seconds (bin start). It is not used for the bar chart.
    - ``CO2`` is per-bin emission in **mg**; we sum over time per run.

    Args:
        path: Optional path to the CSV. If omitted, uses ``EMISSIONS_CSV_FALLBACK``.

    Returns:
        A validated pandas DataFrame.

    Raises:
        FileNotFoundError: If the CSV file does not exist.
        ValueError: If required columns are missing or cannot be coerced to numeric.
    """
    csv_path = path or EMISSIONS_CSV_FALLBACK
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV not found: {csv_path}")

    df = pd.read_csv(csv_path, low_memory=False)

    # Normalize possible variants (backward compatibility)
    if "t_s" in df.columns and "time" not in df.columns:
        df = df.rename(columns={"t_s": "time"})

    required = {"time", "CO2", "controller", "scenario", "run"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing columns in emissions CSV: {sorted(missing)}")

    # Dtypes & sanity
    df["time"] = pd.to_numeric(df["time"], errors="coerce")
    df["CO2"] = pd.to_numeric(df["CO2"], errors="coerce")  # mg
    df["run"] = df["run"].astype(str)

    # Drop rows with invalid numbers
    df = df[df["time"].notna() & df["CO2"].notna()]
    if df.empty:
        raise ValueError("Emissions CSV is empty after cleaning numeric columns.")
    return df


# ─────────────────────────────────────────────────────────────────────────────
# Stats
# ─────────────────────────────────────────────────────────────────────────────
def _compute_bar_stats(
    df: pd.DataFrame,
    scenarios_order: Sequence[str],
    controllers_order: Sequence[str],
) -> Tuple[npt.NDArray[np.float64], npt.NDArray[np.float64], List[str], List[str]]:
    """Aggregate total CO₂ per run and compute mean ± CI for each (scenario, controller).

    Method:
        1) Aggregate per-run totals: ``total_CO2_mg_per_run = sum_t CO2_mg``.
        2) Convert to kg: ``total_CO2_kg_per_run = total_CO2_mg_per_run * 1e-6``.
        3) For each (scenario, controller), compute mean and 95% CI across runs.

    Args:
        df: Emissions dataframe with required columns.
        scenarios_order: Preferred scenarios order (missing ones are skipped).
        controllers_order: Preferred controllers order (missing ones are skipped).

    Returns:
        Tuple of:
            - means: Array shape [S, C] of means (kg).
            - ci_half: Array shape [S, C] of half-width CI (kg).
            - scen_present: Ordered list of scenarios present.
            - ctrl_present: Ordered list of controllers present.

    Raises:
        RuntimeError: If no matching scenarios/controllers are found.
    """
    # Total CO₂ per run (sum over all timesteps) in mg → convert to kg
    per_run = (
        df.groupby(["scenario", "controller", "run"], as_index=False)["CO2"]
        .sum()
        .rename(columns={"CO2": "total_CO2_mg_per_run"})
    )
    per_run["total_CO2_kg_per_run"] = per_run["total_CO2_mg_per_run"] * UNIT_FACTOR

    # Determine actual items present, preserving requested order
    scen_unique = set(per_run["scenario"])
    ctrl_unique = set(per_run["controller"])
    scen_present = [s for s in scenarios_order if s in scen_unique]
    ctrl_present = [c for c in controllers_order if c in ctrl_unique]

    if not scen_present or not ctrl_present:
        raise RuntimeError("No matching scenarios/controllers found in the dataset.")

    S, C = len(scen_present), len(ctrl_present)
    means = np.zeros((S, C), dtype=np.float64)
    ci_half = np.zeros((S, C), dtype=np.float64)

    for i, scen in enumerate(scen_present):
        g_scen = per_run[per_run["scenario"] == scen]
        for j, ctrl in enumerate(ctrl_present):
            x = g_scen.loc[
                g_scen["controller"] == ctrl, "total_CO2_kg_per_run"
            ].dropna()
            n = int(x.shape[0])
            mean_val = float(x.mean()) if n > 0 else 0.0
            if n <= 1:
                ci = 0.0
            else:
                sem = float(x.sem())
                tcrit = float(t.ppf(0.5 * (1 + CONFIDENCE), df=n - 1))
                ci = sem * tcrit

            means[i, j] = mean_val
            ci_half[i, j] = ci

    return means, ci_half, scen_present, ctrl_present


# ─────────────────────────────────────────────────────────────────────────────
# Plot
# ─────────────────────────────────────────────────────────────────────────────
def plot_emissions_bar(
    means: npt.NDArray[np.float64],
    cis: npt.NDArray[np.float64],
    scenarios: Sequence[str],
    controllers: Sequence[str],
    *,
    outpath: Path,
) -> None:
    """Render grouped bars by scenario with controllers as series.

    Bars show mean total CO₂ per run ± 95% CI (in kg). Values are annotated above bars.

    Args:
        means: Mean totals (kg), shape [S, C].
        cis: Half-width CI (kg), shape [S, C].
        scenarios: Scenario labels (length S).
        controllers: Controller labels (length C).
        outpath: Output PDF path.

    Raises:
        ValueError: If array shapes are inconsistent.
        OSError: If saving the figure fails.
    """
    if means.shape != cis.shape:
        raise ValueError("`means` and `cis` must have identical shapes [S, C].")
    if means.shape[0] != len(scenarios) or means.shape[1] != len(controllers):
        raise ValueError("Array shapes do not match `scenarios`/`controllers` lengths.")

    set_ieee_style()
    fig, ax = new_figure(columns=2)

    n_scen = len(scenarios)
    n_ctrl = len(controllers)
    x = np.arange(n_scen, dtype=float)

    total_width = 0.8
    bar_width = total_width / max(n_ctrl, 1)
    offsets = (np.arange(n_ctrl) - (n_ctrl - 1) / 2.0) * bar_width

    # Precompute to help with annotation offsets
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
            color=arch_color_intense(j),
        )

        # Compute a dynamic text offset after autoscale is known
        y_min, y_max = ax.get_ylim()
        y_offset = max((y_max - y_min) * 0.02, max_ci * 0.25) if y_max > y_min else (max_ci * 0.25 or 1.0)

        for bar in bars:
            h = bar.get_height()
            ax.text(
                bar.get_x() + bar.get_width() / 2.0,
                h + y_offset,
                f"{h:,.2f}",  # kg with two decimals and thousands separator
                ha="center",
                va="bottom",
                fontsize=7,
            )

    ax.set_xticks(x)
    ax.set_xticklabels([s.replace("_", " ").capitalize() for s in scenarios])
    ax.set_ylabel(f"Total CO₂ ({UNIT_LABEL})")
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
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    df = _read_emissions_co2()

    means, cis, scen_present, ctrl_present = _compute_bar_stats(
        df, scenarios_order=SCENARIOS, controllers_order=CONTROLLERS
    )

    out = OUTPUT_DIR / "emissions_co2_bar_by_scenario.pdf"
    plot_emissions_bar(means, cis, scen_present, ctrl_present, outpath=out)


if __name__ == "__main__":
    main()
