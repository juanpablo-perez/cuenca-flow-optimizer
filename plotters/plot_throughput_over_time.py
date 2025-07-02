#!/usr/bin/env python3
"""
plot_throughput_over_time.py –
Vehicle throughput (vehicles finished) vs. simulation time (10-min bins).
"""
from __future__ import annotations
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt

from plotters.ieee_style import set_plot_style, arch_color_intense

# --- Configuración ------------------------------------------------------
SCENARIO     = "medium"                       # low / medium / high / very_high
CONTROLLERS  = ["static", "actuated", "fuzzy", "gap_actuated"]
BIN_WIDTH    = 300                            # segundos (10 min)
OUTPUT_DIR   = Path("plots")
OUTPUT_DIR.mkdir(exist_ok=True)

# --- Helpers ------------------------------------------------------------
def load_arrivals(controller: str, scenario: str) -> pd.DataFrame:
    """Devuelve un DataFrame con columna 'arrival' (segundos)."""
    dfs = []
    for run in Path("experiments").glob(f"{controller}_{scenario}_*"):
        xml = run / "tripinfo.xml"
        if not xml.exists():
            continue
        df = pd.read_xml(xml, xpath="//tripinfo")
        # Normalizar nombre de columna
        if "arrival" not in df:
            df = df.rename(columns={"arrivalTime": "arrival"})
        dfs.append(df[["arrival"]].astype(float))
    return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()


def hhmm(sec: int) -> str:
    h, m = divmod(sec, 3600)[0], (sec % 3600) // 60
    return f"{h:02d}:{m:02d}"

# --- Main ----------------------------------------------------------------
def main() -> None:
    set_plot_style()
    fig, ax = plt.subplots(figsize=(16, 9))

    for i, ctl in enumerate(CONTROLLERS):
        df = load_arrivals(ctl, SCENARIO)
        if df.empty:
            continue

        max_t = int(df["arrival"].max())
        bins = range(0, max_t + BIN_WIDTH, BIN_WIDTH)
        df["interval"] = pd.cut(df["arrival"], bins=bins, right=False)

        throughput = df.groupby("interval").size()         # veh/ventana
        smooth = throughput.rolling(3, center=True, min_periods=1).mean()

        x = [hhmm(iv.left) for iv in smooth.index]
        ax.plot(
            x, smooth.values,
            label=ctl.capitalize(), marker="o",
            color=arch_color_intense(i)
        )

    ax.set_xlabel("Time of day (HH:MM)", fontsize=20)
    ax.set_ylabel(f"Vehicles finished per {BIN_WIDTH//60} min", fontsize=20)
    ax.set_title("Vehicle throughput over simulation time", fontsize=22)
    ax.legend(fontsize=16)
    plt.xticks(rotation=45)
    plt.tight_layout()

    out = OUTPUT_DIR / f"throughput_over_time_{SCENARIO}.pdf"
    plt.savefig(out, dpi=300)
    print(f"✔ Saved {out}")
    plt.show()

if __name__ == "__main__":
    main()
