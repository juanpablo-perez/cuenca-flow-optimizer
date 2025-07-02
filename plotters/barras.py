#!/usr/bin/env python3
"""
barras.py – Bar chart of mean waiting time ±95% CI by controller & scenario.
"""
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

from fuzzylts.utils.stats import load_experiment_metrics, ci
from plotters.ieee_style import set_plot_style, arch_color_intense

# ─── Configuration ───────────────────────────────────────────────────────
CONTROLLERS = ["static", "actuated", "fuzzy"]
SCENARIOS   = ["low", "medium", "high", "very"]
BAR_WIDTH   = 0.2
OUTPUT_DIR  = Path("plots")
OUTPUT_DIR.mkdir(exist_ok=True)

def main():
    set_plot_style()
    df = load_experiment_metrics()

    x = np.arange(len(CONTROLLERS))
    fig, ax = plt.subplots(figsize=(7, 3))

    for i, scen in enumerate(SCENARIOS):
        means, errs = [], []
        for ctl in CONTROLLERS:
            sub = df[(df.controller == ctl) & (df.scenario == scen)]
            m = sub.avg_wait.mean()
            lo, hi = ci(sub.avg_wait)
            means.append(m)
            errs.append((hi - lo) / 2)
        offset = (i - 1.5) * BAR_WIDTH
        ax.bar(
            x + offset, means, BAR_WIDTH,
            yerr=errs, capsize=3,
            label=scen.capitalize() if scen != "very" else "Very High",
            color=arch_color_intense(i)
        )

    ax.set_xticks(x)
    ax.set_xticklabels([c.capitalize() for c in CONTROLLERS])
    ax.set_xlabel("Controller")
    ax.set_ylabel("Avg waiting time (s)")
    ax.set_title("Average waiting time by controller & scenario")
    ax.legend(title="Scenario", ncol=2)
    plt.tight_layout()

    out = OUTPUT_DIR / "avg_wait_bars.pdf"
    plt.savefig(out)
    print(f"✔ Saved {out}")
    plt.show()

if __name__ == "__main__":
    main()
