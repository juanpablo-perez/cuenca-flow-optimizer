#!/usr/bin/env python3
"""
plot_throughput_over_time.py –
Vehicle throughput vs. simulation time (10-min bins) with 95% CI.
"""
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.stats import t

from fuzzylts.utils.stats import load_all_tripinfo
from plotters.ieee_style import set_ieee_style, new_figure, arch_color_intense

# ─── Configuration ────────────────────────────────────────────────────────
SCENARIO    = "medium_extended"                           # low / medium / high / very_high
CONTROLLERS = ["static", "actuated", "gap_fuzzy"]
BIN_WIDTH   = 600                             # seconds (10 min)
OUTPUT_DIR  = Path("plots")
OUTPUT_DIR.mkdir(exist_ok=True)

def human_time(sec: int) -> str:
    h = sec // 3600
    m = (sec % 3600) // 60
    return f"{h:02d}:{m:02d}"

def main() -> None:
    set_ieee_style()
    fig, ax = new_figure(columns=2)

    df_all = load_all_tripinfo()
    if "run" in df_all.columns and "run_id" not in df_all.columns:
        df_all = df_all.rename(columns={"run": "run_id"})
    df_all = df_all[df_all["scenario"] == SCENARIO]

    for i, ctl in enumerate(CONTROLLERS):
        df_ctl = df_all[df_all["controller"] == ctl]
        if df_ctl.empty:
            continue

        max_t = int(df_ctl["arrival"].max())
        bins  = np.arange(0, max_t + BIN_WIDTH, BIN_WIDTH)
        df_ctl["interval"] = pd.cut(df_ctl["arrival"], bins=bins, right=False)

        grouped = (
            df_ctl
            .groupby(["interval", "run_id"])["arrival"]
            .count()
            .unstack("run_id")
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
        ax.plot(x, mean_s, label=ctl.replace("_", " ").capitalize(),
                marker="o", color=arch_color_intense(i))
        ax.fill_between(x, lower_s, upper_s, alpha=0.2)

    hourly = [i for i, iv in enumerate(mean_s.index) if iv.left % 3600 == 0]
    ax.set_xticks(hourly)
    ax.set_xticklabels([human_time(iv.left) for iv in mean_s.index][::int(3600/BIN_WIDTH)], rotation=45)

    ax.set_xlabel("Time of day (HH:MM)")
    ax.set_ylabel("Vehicles passed")
    ax.set_title(
        f"Vehicle Throughput over Time\n"
        f"(Scenario: {SCENARIO}, 10-min bins, 95% CI)"
    )
    ax.legend()
    plt.tight_layout()

    out = OUTPUT_DIR / f"throughput_over_time_{SCENARIO}_ci95.pdf"
    plt.savefig(out)
    print(f"✔ Saved {out}")
    plt.show()

if __name__ == "__main__":
    main()
