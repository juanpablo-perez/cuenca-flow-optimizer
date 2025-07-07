#!/usr/bin/env python3
"""
plot_waiting_time_over_time.py –
Average waiting time per vehicle vs. simulation time (10-min bins) with 95% CI.
"""
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
from scipy.stats import t

from fuzzylts.utils.stats import load_all_tripinfo
from plotters.ieee_style import set_plot_style

# ─── Configuration ────────────────────────────────────────────────────────
SCENARIO     = "medium"        # low / medium / high / very_high
CONTROLLERS  = ["static", "actuated", "gap_actuated"]
BIN_WIDTH    = 600             # seconds (10 min)
OUTPUT_DIR   = Path("plots")
OUTPUT_DIR.mkdir(exist_ok=True)


def human_time(sec: int) -> str:
    h = sec // 3600
    m = (sec % 3600) // 60
    return f"{h:02d}:{m:02d}"


def main() -> None:
    set_plot_style()
    df_all = load_all_tripinfo()
    df_all = df_all[df_all["scenario"] == SCENARIO]

    fig, ax = plt.subplots(figsize=(16, 9))

    for ctl in CONTROLLERS:
        df_ctl = df_all[df_all["controller"] == ctl]
        if df_ctl.empty:
            continue

        # define bins and intervals
        max_t = int(df_ctl["arrival"].max())
        bins  = np.arange(0, max_t + BIN_WIDTH, BIN_WIDTH)
        df_ctl["interval"] = pd.cut(df_ctl["arrival"], bins=bins, right=False)

        # compute per‐run means
        grouped = (
            df_ctl
            .groupby(["interval","run"])["waitingTime"]
            .mean()
            .unstack("run")
        )

        # mean and 95% CI
        mean = grouped.mean(axis=1)
        sem  = grouped.sem(axis=1)
        t_crit = t.ppf(0.975, df=grouped.shape[1]-1)
        ci95   = sem * t_crit
        lower  = mean - ci95
        upper  = mean + ci95

        # smooth with rolling window
        mean_s  = mean.rolling(3, center=True, min_periods=1).mean()
        lower_s = lower.rolling(3, center=True, min_periods=1).mean()
        upper_s = upper.rolling(3, center=True, min_periods=1).mean()

        # prepare x-labels
        x_labels = [human_time(iv.left) for iv in mean_s.index]

        # plot
        ax.plot(x_labels, mean_s, label=ctl.capitalize(), marker="o")
        ax.fill_between(x_labels, lower_s, upper_s, alpha=0.2)

    # only show ticks at the top of each hour
    hourly_idxs   = [i for i, iv in enumerate(mean_s.index) if iv.left % 3600 == 0]
    hourly_labels = [x_labels[i] for i in hourly_idxs]
    ax.set_xticks(hourly_idxs)
    ax.set_xticklabels(hourly_labels, rotation=45)

    ax.set_xlabel("Time of day (HH:MM)", fontsize=20)
    ax.set_ylabel("Mean waiting time (s)", fontsize=20)
    ax.set_title(
        f"Avg waiting time vs. simulation time\n"
        f"(Scenario: {SCENARIO}, 10-min bins, 95% CI)",
        fontsize=22
    )
    ax.legend(fontsize=16)
    plt.tight_layout()

    out = OUTPUT_DIR / f"waiting_time_over_time_{SCENARIO}_ci95.pdf"
    plt.savefig(out, dpi=300)
    print(f"✔ Saved {out}")
    plt.show()


if __name__ == "__main__":
    main()
