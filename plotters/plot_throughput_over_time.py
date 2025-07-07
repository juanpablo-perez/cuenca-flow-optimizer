#!/usr/bin/env python3
"""
plot_throughput_over_time.py –
Vehicle throughput vs. simulation time (10-min bins) with 95% CI.
"""
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
from scipy.stats import t
import pandas as pd

from fuzzylts.utils.stats import load_all_tripinfo
from plotters.ieee_style import set_plot_style, arch_color_intense

# ─── Configuration ────────────────────────────────────────────────────────
SCENARIO    = "low"                           # low / medium / high / very_high
CONTROLLERS = ["static", "actuated", "gap_actuated"]
BIN_WIDTH   = 600                             # seconds (10 min)
OUTPUT_DIR  = Path("plots")
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

    for i, ctl in enumerate(CONTROLLERS):
        df_ctl = df_all[df_all["controller"] == ctl]
        if df_ctl.empty:
            continue

        max_t = int(df_ctl["arrival"].max())
        bins  = np.arange(0, max_t + BIN_WIDTH, BIN_WIDTH)
        df_ctl["interval"] = pd.cut(df_ctl["arrival"], bins=bins, right=False)

        grouped = (
            df_ctl
            .groupby(["interval", "run"])["arrival"]
            .count()
            .unstack("run")
        )

        mean   = grouped.mean(axis=1)
        sem    = grouped.sem(axis=1)
        t_crit = t.ppf(0.975, df=grouped.shape[1] - 1)
        ci95   = sem * t_crit
        lower  = mean - ci95
        upper  = mean + ci95

        mean_s  = mean.rolling(3, center=True, min_periods=1).mean()
        lower_s = lower.rolling(3, center=True, min_periods=1).mean()
        upper_s = upper.rolling(3, center=True, min_periods=1).mean()

        x = [human_time(iv.left) for iv in mean_s.index]
        ax.plot(x, mean_s, label=ctl.capitalize(), marker="o", color=arch_color_intense(i))
        ax.fill_between(x, lower_s, upper_s, alpha=0.2)

    hourly_idxs   = [i for i, iv in enumerate(mean_s.index) if iv.left % 3600 == 0]
    hourly_labels = [x[i] for i in hourly_idxs]
    ax.set_xticks(hourly_idxs)
    ax.set_xticklabels(hourly_labels, rotation=45)

    ax.set_xlabel("Time of day (HH:MM)", fontsize=20)
    ax.set_ylabel("Vehicles passed", fontsize=20)
    ax.set_title("Vehicle Throughput over Time (95% CI)", fontsize=22)
    ax.legend(fontsize=16)
    plt.tight_layout()

    out = OUTPUT_DIR / f"throughput_over_time_{SCENARIO}_ci95.pdf"
    plt.savefig(out, dpi=300)
    print(f"✔ Saved {out}")
    plt.show()


if __name__ == "__main__":
    main()
