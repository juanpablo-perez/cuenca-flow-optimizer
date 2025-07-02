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
CONTROLLERS = ["static", "actuated", "gap_actuated", "fuzzy"]
SCENARIOS   = ["low", "medium", "high", "very_high"]
BAR_WIDTH   = 0.2
OUTPUT_DIR  = Path("plots")
OUTPUT_DIR.mkdir(exist_ok=True)

def main():
    set_plot_style()
    df = load_experiment_metrics()
    print(df.head(50))

    x = np.arange(len(CONTROLLERS))
    fig, ax = plt.subplots(figsize=(16, 9))

    for i, scen in enumerate(SCENARIOS):
        means, errs = [], []
        for ctl in CONTROLLERS:
            sub = df[(df.controller == ctl) & (df.scenario == scen)]
            m = sub.avg_wait.mean()
            lo, hi = ci(sub.avg_wait)
            means.append(m)
            errs.append((hi - lo) / 2)
        offset = (i - 1.5) * BAR_WIDTH
        bars = ax.bar(x + offset, means, BAR_WIDTH,
              yerr=errs, capsize=3,
              label=scen.capitalize(),
              color=arch_color_intense(i))
        for bar, val in zip(bars, means):                       # ← añade el texto
            ax.text(bar.get_x() + bar.get_width() / 2,
                    bar.get_height() + 0.01 * max(means),       # un pequeño margen arriba
                    f"{val:.1f}s",                              # muestra porcentaje
                    ha="center", va="bottom", fontsize=12)
        # ax.bar(
        #     x + offset, means, BAR_WIDTH,
        #     yerr=errs, capsize=3,
        #     label=scen.capitalize() if scen != "very" else "Very High",
        #     color=arch_color_intense(i)
        # )

    ax.set_xticks(x)
    ax.set_xticklabels([c.capitalize() for c in CONTROLLERS])
    ax.set_xlabel("Controller", fontsize=20)
    ax.set_ylabel("Avg waiting time (s)")
    ax.set_title("Average waiting time by controller & scenario")
    ax.legend(title="Scenario", ncol=2, fontsize=16)
    plt.tight_layout()

    out = OUTPUT_DIR / "avg_wait_bars.pdf"
    plt.savefig(out, dpi=300)
    print(f"✔ Saved {out}")
    plt.show()

if __name__ == "__main__":
    main()
