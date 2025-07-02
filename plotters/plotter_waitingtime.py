#!/usr/bin/env python3
"""
plotter_waitingtime.py –  
ECDF of individual vehicle waiting times for each controller in a scenario.
"""
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

from fuzzylts.utils.io import tripinfo_xml_to_df
from plotters.ieee_style import set_plot_style, arch_color, esc_marker

# ─── Configuration ───────────────────────────────────────────────────────
SCENARIO    = "medium"       # low / medium / high / very_high
CONTROLLERS = ["static", "actuated", "fuzzy"]
OUTPUT_DIR  = Path("plots")
OUTPUT_DIR.mkdir(exist_ok=True)

def load_waits(controller: str, scenario: str) -> np.ndarray:
    recs = []
    for run in Path("experiments").glob(f"{controller}_{scenario}_*"):
        xml = run / "tripinfo.xml"
        if xml.exists():
            df = tripinfo_xml_to_df(xml)
            recs.append(df["waitingTime"].to_numpy())
    return np.concatenate(recs) if recs else np.array([])

def main():
    set_plot_style()
    fig, ax = plt.subplots(figsize=(7, 3))

    for i, ctl in enumerate(CONTROLLERS):
        data = load_waits(ctl, SCENARIO)
        if data.size == 0:
            continue
        sorted_data = np.sort(data)
        ecdf = np.arange(1, len(sorted_data)+1) / len(sorted_data)
        ax.step(
            sorted_data, ecdf, where="post",
            label=ctl.capitalize(),
            color=arch_color(i),
            marker=esc_marker(i),
            markevery=len(sorted_data)//20
        )

    ax.set_xlabel("Waiting time (s)")
    ax.set_ylabel("Empirical CDF")
    ax.set_title(f"Waiting-time distribution ({SCENARIO.capitalize()})")
    ax.legend(loc="lower right")
    plt.tight_layout()

    out = OUTPUT_DIR / f"waiting_time_ecdf_{SCENARIO}.pdf"
    plt.savefig(out)
    print(f"✔ Saved {out}")
    plt.show()

if __name__ == "__main__":
    main()
