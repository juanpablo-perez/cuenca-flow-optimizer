#!/usr/bin/env python3
"""
plot_emissions_bar.py –
Bar chart of total CO₂ emissions per controller (mean ± 95% CI).
"""
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
from scipy.stats import t

from fuzzylts.utils.stats import load_all_emissions
from plotters.ieee_style import set_plot_style, arch_color_intense

# ─── Configuration ────────────────────────────────────────────────────────
SCENARIO    = "medium"                        # low / medium / high / very_high
CONTROLLERS = ["static", "actuated", "gap_actuated"]
POLLUTANT   = "CO2"
OUTPUT_DIR  = Path("plots")
OUTPUT_DIR.mkdir(exist_ok=True)


def main() -> None:
    set_plot_style()

    # load everything and filter to our scenario
    df_all = load_all_emissions(POLLUTANT)
    df = df_all[df_all["scenario"] == SCENARIO]

    means: list[float] = []
    cis:   list[float] = []
    labels: list[str] = []

    # compute per-run totals → mean ± CI
    for i, ctl in enumerate(CONTROLLERS):
        df_ctl = df[df["controller"] == ctl]
        total_by_run = df_ctl.groupby("run")[POLLUTANT].sum()
        n = total_by_run.count()
        mean_val = total_by_run.mean()
        sem_val  = total_by_run.sem()
        t_crit   = t.ppf(0.975, df=n - 1)
        ci95     = sem_val * t_crit

        means.append(mean_val)
        cis.append(ci95)
        labels.append(ctl.capitalize())

    # plot
    fig, ax = plt.subplots(figsize=(8, 6))
    x = np.arange(len(labels))
    colors = [arch_color_intense(i) for i in range(len(labels))]
    ax.bar(x, means, yerr=cis, capsize=8, width=0.6, color=colors)

    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=12)
    ax.set_ylabel(f"Total {POLLUTANT} emitted (g)", fontsize=14)
    ax.set_title(
        f"Total {POLLUTANT} Emissions by Controller\n"
        f"(Scenario: {SCENARIO}, mean ± 95% CI)",
        fontsize=16
    )
    ax.grid(axis="y", linestyle="--", alpha=0.5)

    plt.tight_layout()
    out = OUTPUT_DIR / f"{POLLUTANT.lower()}_bar_{SCENARIO}.pdf"
    plt.savefig(out, dpi=300)
    print(f"✔ Saved {out}")
    plt.show()


if __name__ == "__main__":
    main()
