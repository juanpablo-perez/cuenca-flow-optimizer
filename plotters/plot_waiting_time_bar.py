#!/usr/bin/env python3
"""
plot_waiting_time_bar.py –
Grouped bar chart of average waiting time per scenario,
scenarios on x-axis, controllers as bar series (mean ± 95 % CI),
values annotated on top of each bar.
"""
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from scipy.stats import t

from fuzzylts.utils.stats import load_all_tripinfo
from plotters.ieee_style import set_ieee_style, new_figure, arch_color_intense

# ─── Configuration ────────────────────────────────────────────────────────
SCENARIOS    = ["low", "medium", "high", "very_high"]
CONTROLLERS  = ["static", "actuated", "gap_fuzzy"]
OUTPUT_DIR   = Path("plots")
OUTPUT_DIR.mkdir(exist_ok=True)

def main() -> None:
    set_ieee_style()
    fig, ax = new_figure(columns=2)

    # ── Carga de datos ────────────────────────────────────────────────────
    df_all = load_all_tripinfo()

    # Normaliza el identificador de corrida
    if "run_id" in df_all.columns and "run" not in df_all.columns:
        df_all = df_all.rename(columns={"run_id": "run"})

    n_scen  = len(SCENARIOS)
    n_ctrls = len(CONTROLLERS)
    means   = np.zeros((n_scen, n_ctrls))
    cis     = np.zeros((n_scen, n_ctrls))

    # ── Cálculo de medias e IC95 %  → [scenario, controller] ──────────────
    for i, scenario in enumerate(SCENARIOS):
        df_sc = df_all[df_all["scenario"] == scenario]
        for j, ctl in enumerate(CONTROLLERS):
            df_ctl     = df_sc[df_sc["controller"] == ctl]
            avg_by_run = df_ctl.groupby("run")["waitingTime"].mean()
            n          = avg_by_run.count()
            mean_val   = avg_by_run.mean() if n > 0 else 0.0
            sem_val    = avg_by_run.sem()  if n > 1 else 0.0
            t_crit     = t.ppf(0.975, df=n-1) if n > 1 else 0.0
            ci95       = sem_val * t_crit

            means[i, j] = mean_val
            cis[i, j]   = ci95

    # ── Plot ──────────────────────────────────────────────────────────────
    x           = np.arange(n_scen)
    total_width = 0.8
    bar_width   = total_width / n_ctrls
    offsets     = (np.arange(n_ctrls) - (n_ctrls - 1) / 2) * bar_width
    max_ci      = cis.max() if cis.size > 0 else 0.0

    for j, ctl in enumerate(CONTROLLERS):
        heights = means[:, j]
        errors  = cis[:, j]
        xpos    = x + offsets[j]

        bars = ax.bar(
            xpos,
            heights,
            width=bar_width,
            yerr=errors,
            capsize=5,
            label=ctl.replace("_", " ").capitalize(),
            color=arch_color_intense(j),
        )

        # Anota cada barra
        for bar in bars:
            h = bar.get_height()
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                h + max_ci * 0.75,
                f"{h:.1f}",
                ha="center",
                va="bottom",
                size=9,
            )

    # ── Etiquetas y estilo ────────────────────────────────────────────────
    ax.set_xticks(x)
    ax.set_xticklabels([s.replace("_", " ").capitalize() for s in SCENARIOS])
    ax.set_ylabel("Mean waiting time (s)")
    ax.set_xlabel("Scenarios")
    # ax.set_title(
    #     "Average Waiting Time by Scenario and Controller\n"
    #     "(mean ± 95 % CI)"
    # )
    ax.legend(
        title="Controller",
        loc="upper center",           # posición "arriba-centro" relativa al bbox
        bbox_to_anchor=(0.5, 1.20),   # x=0.5 (centro), y=1.10 (10% por encima del top)
        ncol=3,                       # número de columnas en la leyenda (ajusta según ítems)
        frameon=False                 # opcional: sin marco para un estilo más limpio
    )
    ax.grid(axis="y")

    plt.tight_layout()


    # ── Guardado ──────────────────────────────────────────────────────────
    out = OUTPUT_DIR / "waiting_time_bar_by_scenario.pdf"
    plt.savefig(out, bbox_inches="tight")
    print(f"✔ Saved {out}")
    plt.show()

if __name__ == "__main__":
    main()
