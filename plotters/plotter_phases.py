#!/usr/bin/env python3
"""
plotter_phases.py –  
Histogram of green‐phase durations observed under fuzzy control.
"""
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

from plotters.ieee_style import set_plot_style, arch_color

# ─── Configuration ───────────────────────────────────────────────────────
CSV_FILE    = Path("data_tls_fuzzy.csv")
OUTPUT_DIR  = Path("plots")
OUTPUT_DIR.mkdir(exist_ok=True)
PHASES      = {0: "Phase 0", 2: "Phase 2"}

def main():
    set_plot_style()
    df = pd.read_csv(CSV_FILE, header=0, names=[
        "time","traffic_light_id","phase","green_duration","vehicles_in_phase"
    ])

    fig, ax = plt.subplots(figsize=(7,3))
    for i,(pid,label) in enumerate(PHASES.items()):
        ax.hist(
            df[df.phase==pid]["green_duration"],
            bins=20,
            alpha=0.7,
            label=label,
            color=arch_color(i)
        )

    ax.set_xlabel("Green duration (s)")
    ax.set_ylabel("Frequency")
    ax.set_title("Green‐phase duration distribution")
    ax.legend()
    plt.tight_layout()

    out = OUTPUT_DIR / "green_phase_hist.pdf"
    plt.savefig(out)
    print(f"✔ Saved {out}")
    plt.show()

if __name__ == "__main__":
    main()
