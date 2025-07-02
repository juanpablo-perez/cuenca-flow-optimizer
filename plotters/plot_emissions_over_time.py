#!/usr/bin/env python3
"""
plot_emissions_over_time.py –
Total CO₂ emitted vs. simulation time (10-min bins).
"""
from __future__ import annotations
from pathlib import Path
import xml.etree.ElementTree as ET

import pandas as pd
import matplotlib.pyplot as plt

from plotters.ieee_style import set_plot_style, arch_color_intense

# ─── Configuración ──────────────────────────────────────────────────────
SCENARIO     = "medium"                       # low / medium / high / very_high
CONTROLLERS  = ["static", "actuated", "fuzzy", "gap_actuated"]
POLLUTANT    = "CO2"                          # CO2, CO, NOx, PMx, fuel, …
BIN_WIDTH    = 600                            # segundos (10 min)
OUTPUT_DIR   = Path("plots")
OUTPUT_DIR.mkdir(exist_ok=True)


# ─── Helpers ────────────────────────────────────────────────────────────
def parse_emissions_xml(xml_path: Path, pollutant: str) -> pd.DataFrame:
    """
    Devuelve un DataFrame con columnas ['time', pollutant] donde cada fila es
    un timestep y el valor es la suma sobre todos los vehículos.
    """
    records: list[dict[str, float]] = []
    for event, elem in ET.iterparse(xml_path, events=("end",)):
        if elem.tag == "timestep":
            t = float(elem.attrib["time"])
            total = sum(float(veh.attrib[pollutant])
                        for veh in elem.iterfind("vehicle"))
            records.append({"time": t, pollutant: total})
            elem.clear()          # liberar memoria
    return pd.DataFrame.from_records(records)


def load_emissions(controller: str, scenario: str) -> pd.DataFrame:
    """Concatena los timesteps de todos los runs matching controlador/escenario."""
    dfs = []
    for run in Path("experiments").glob(f"{controller}_{scenario}_*"):
        xml = run / "emissions.xml"
        if xml.exists():
            dfs.append(parse_emissions_xml(xml, POLLUTANT))
    return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()


def human_time(sec: int) -> str:
    h, m = divmod(sec, 3600)[0], (sec % 3600) // 60
    return f"{h:02d}:{m:02d}"


# ─── Main ───────────────────────────────────────────────────────────────
def main() -> None:
    set_plot_style()
    fig, ax = plt.subplots(figsize=(16, 9))

    for i, ctl in enumerate(CONTROLLERS):
        df = load_emissions(ctl, SCENARIO)
        if df.empty:
            continue

        max_t = int(df["time"].max())
        bins = range(0, max_t + BIN_WIDTH, BIN_WIDTH)
        df["interval"] = pd.cut(df["time"], bins=bins, right=False)

        # gramos de CO₂ por intervalo
        grouped = df.groupby("interval")[POLLUTANT].sum()

        # Suavizar un poco para trazo (3-punto rolling)
        smooth = grouped.rolling(3, center=True, min_periods=1).mean()

        x = [human_time(iv.left) for iv in smooth.index]
        ax.plot(
            x, smooth.values,
            label=ctl.capitalize(), marker="o",
            color=arch_color_intense(i)
        )

    ax.set_xlabel("Time of day (HH:MM)", fontsize=20)
    ax.set_ylabel(f"Total {POLLUTANT} emitted (g)", fontsize=20)
    ax.set_title(f"{POLLUTANT} emissions over simulation time", fontsize=22)
    ax.legend(fontsize=16)
    plt.xticks(rotation=45)
    plt.tight_layout()

    out = OUTPUT_DIR / f"{POLLUTANT.lower()}_over_time_{SCENARIO}.pdf"
    plt.savefig(out, dpi=300)
    print(f"✔ Saved {out}")
    plt.show()


if __name__ == "__main__":
    main()
