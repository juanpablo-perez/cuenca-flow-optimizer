#!/usr/bin/env python3
"""
plot_wait_over_time.py –  
Average waiting time per vehicle vs. simulation time (10-min bins).
"""
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

from plotters.ieee_style import set_plot_style

# ─── Configuration ───────────────────────────────────────────────────────
SCENARIO     = "high"        # low / medium / high / very_high
CONTROLLERS  = ["static", "actuated", "fuzzy"]
BIN_WIDTH    = 600             # seconds
OUTPUT_DIR   = Path("plots")
OUTPUT_DIR.mkdir(exist_ok=True)

def load_tripinfo(controller: str, scenario: str) -> pd.DataFrame:
    dfs = []
    for run in Path("experiments").glob(f"{controller}_{scenario}_*"):
        xml = run / "tripinfo.xml"
        if xml.exists():
            df = pd.read_xml(xml, xpath="//tripinfo")
            # normalize column names
            if "waitingTime" not in df:
                df = df.rename(columns={"waiting_time":"waitingTime"})
            dfs.append(df[["arrival","waitingTime"]])
    return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()

def format_label(sec: int) -> str:
    h = sec//3600; m = (sec%3600)//60
    return f"{h:02d}:{m:02d}"

def main():
    set_plot_style()
    fig, ax = plt.subplots(figsize=(8, 3))

    for ctl in CONTROLLERS:
        df = load_tripinfo(ctl, SCENARIO)
        if df.empty:
            continue
        max_t = df["arrival"].max()
        bins = range(0, int(max_t)+BIN_WIDTH, BIN_WIDTH)
        df["interval"] = pd.cut(df["arrival"], bins=bins, right=False)
        grouped = df.groupby("interval")["waitingTime"].mean()
        smooth = grouped.rolling(3, center=True, min_periods=1).mean()
        x = [format_label(iv.left) for iv in smooth.index]
        ax.plot(x, smooth.values, label=ctl.capitalize(), marker="o")

    ax.set_xlabel("Time of day (HH:MM)")
    ax.set_ylabel("Mean waiting time (s)")
    ax.set_title("Avg waiting time vs. simulation time")
    ax.legend()
    plt.xticks(rotation=45)
    plt.tight_layout()

    out = OUTPUT_DIR / f"waiting_time_over_time_{SCENARIO}.pdf"
    plt.savefig(out)
    print(f"✔ Saved {out}")
    plt.show()

if __name__ == "__main__":
    main()
