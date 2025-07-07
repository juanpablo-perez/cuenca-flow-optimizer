#!/usr/bin/env python3
"""
plot_waiting_time_bar.py –
Grouped bar chart of average waiting time per controller, with scenarios as bar series
(mean ± 95% CI), controllers on the X-axis and scenarios as grouped bars, values annotated.
"""
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
from scipy.stats import t

from fuzzylts.utils.stats import load_all_tripinfo
from plotters.ieee_style import set_plot_style, arch_color_intense

# ─── Configuration ────────────────────────────────────────────────────────
SCENARIOS   = ["low", "medium", "high", "very_high"]
CONTROLLERS = ["static", "actuated", "gap_actuated"]
OUTPUT_DIR  = Path("plots")
OUTPUT_DIR.mkdir(exist_ok=True)

def main() -> None:
    set_plot_style()

    # load all tripinfo data
    df_all = load_all_tripinfo()

    n_ctrls     = len(CONTROLLERS)
    n_scenarios = len(SCENARIOS)

    # compute mean and CI arrays [controller, scenario]
    means = np.zeros((n_ctrls, n_scenarios))
    cis   = np.zeros((n_ctrls, n_scenarios))

    for j, scenario in enumerate(SCENARIOS):
        df_sc = df_all[df_all["scenario"] == scenario]
        for i, ctl in enumerate(CONTROLLERS):
            df_ctl    = df_sc[df_sc["controller"] == ctl]
            avg_by_run = df_ctl.groupby("run")["waitingTime"].mean()
            n         = avg_by_run.count()
            mean_val  = avg_by_run.mean() if n > 0 else 0.0
            sem_val   = avg_by_run.sem()  if n > 1 else 0.0
            t_crit    = t.ppf(0.975, df=n-1) if n > 1 else 0.0
            ci95      = sem_val * t_crit

            means[i, j] = mean_val
            cis[i, j]   = ci95

    # plotting
    fig, ax = plt.subplots(figsize=(10, 6))
    x = np.arange(n_ctrls)
    total_width = 0.8
    bar_width   = total_width / n_scenarios
    offsets     = (np.arange(n_scenarios) - (n_scenarios - 1) / 2) * bar_width

    max_ci = cis.max()

    for j, scenario in enumerate(SCENARIOS):
        heights = means[:, j]
        errors  = cis[:, j]
        xpos    = x + offsets[j]
        bars = ax.bar(
            xpos,
            heights,
            width=bar_width,
            yerr=errors,
            capsize=5,
            label=scenario.capitalize(),
            color=arch_color_intense(j)
        )
        # annotate each bar
        for bar in bars:
            h = bar.get_height()
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                h + max_ci * 0.05,
                f"{h:.1f}",
                ha="center",
                va="bottom",
                fontsize=10
            )

    ax.set_xticks(x)
    ax.set_xticklabels([c.capitalize() for c in CONTROLLERS], fontsize=12)
    ax.set_ylabel("Mean waiting time (s)", fontsize=14)
    ax.set_title(
        "Average Waiting Time by Controller and Scenario\n"
        "(controllers on X-axis, mean ± 95% CI)",
        fontsize=16
    )
    ax.legend(title="Scenario", fontsize=12, title_fontsize=12)
    ax.grid(axis="y", linestyle="--", alpha=0.4)

    plt.tight_layout()
    out = OUTPUT_DIR / "waiting_time_bar_by_controller.pdf"
    plt.savefig(out, dpi=300)
    print(f"✔ Saved {out}")
    plt.show()

if __name__ == "__main__":
    main()
