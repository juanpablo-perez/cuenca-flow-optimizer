#!/usr/bin/env python3
"""
plot_emissions_bar.py –
Grouped bar chart of total CO₂ emissions per scenario,
scenarios on x-axis, controllers as bar series (mean ± 95 % CI),
values annotated en notación de ingeniería (p.ej. 1.23 Gg).
"""
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.ticker import EngFormatter
from scipy.stats import t

from fuzzylts.utils.stats import load_all_emissions
from plotters.ieee_style import set_ieee_style, new_figure, arch_color_intense

# ─── Configuration ────────────────────────────────────────────────────────
SCENARIOS    = ["low", "medium", "high", "very_high"]
CONTROLLERS  = ["static", "actuated", "gap_fuzzy"]
POLLUTANT    = "CO2"
OUTPUT_DIR   = Path("plots")
OUTPUT_DIR.mkdir(exist_ok=True)

def main() -> None:
    # Estilo IEEE
    set_ieee_style()
    fig, ax = new_figure(columns=2)

    # ── Carga y preprocesado ───────────────────────────────────────────────
    df_all = load_all_emissions(POLLUTANT)
    if "run" in df_all.columns and "run_id" not in df_all.columns:
        df_all = df_all.rename(columns={"run": "run_id"})

    n_scen  = len(SCENARIOS)
    n_ctrls = len(CONTROLLERS)
    means   = np.zeros((n_scen, n_ctrls))
    cis     = np.zeros((n_scen, n_ctrls))

    # ── Media e IC 95 %  → [scenario, controller] ──────────────────────────
    for i, scenario in enumerate(SCENARIOS):
        df_sc = df_all[df_all["scenario"] == scenario]
        for j, ctl in enumerate(CONTROLLERS):
            df_ctl       = df_sc[df_sc["controller"] == ctl]
            total_by_run = df_ctl.groupby("run_id")[POLLUTANT].sum()

            n        = total_by_run.count()
            mean_val = total_by_run.mean() if n > 0 else 0.0
            sem_val  = total_by_run.sem()  if n > 1 else 0.0
            t_crit   = t.ppf(0.975, df=n-1) if n > 1 else 0.0
            ci95     = sem_val * t_crit

            means[i, j] = mean_val
            cis[i, j]   = ci95

    # ── Plot ───────────────────────────────────────────────────────────────
    x           = np.arange(n_scen)
    total_width = 0.8
    bar_width   = total_width / n_ctrls
    offsets     = (np.arange(n_ctrls) - (n_ctrls - 1) / 2) * bar_width
    max_ci      = cis.max() if cis.size > 0 else 0.0

    eng_txt  = EngFormatter(unit="g", places=2)  # para las etiquetas de texto
    eng_axis = EngFormatter(unit="g")            # para el eje y

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
                h + max_ci * 0.07,
                eng_txt.format_eng(h),
                ha="left", va="bottom",
                rotation=60, rotation_mode="anchor",
                fontweight="normal",             # ← sin negrita
                fontsize=8,
            )


    # ── Etiquetas, formato, leyenda ───────────────────────────────────────
    ax.set_xticks(x)
    ax.set_xticklabels([s.replace("_", " ").capitalize() for s in SCENARIOS])
    ax.set_ylabel(f"Total {POLLUTANT} emitted")
    ax.set_xlabel(f"Scenarios")
    ax.yaxis.set_major_formatter(eng_axis)
    # ax.set_title(
    #     f"Total {POLLUTANT} Emissions by Scenario and Controller\n"
    #     "(mean ± 95 % CI)"
    # )
    ax.legend(title="Controller")
    ax.grid(axis="y")

    # ── Guardar y mostrar ─────────────────────────────────────────────────
    out = OUTPUT_DIR / f"{POLLUTANT.lower()}_bar_by_scenario.pdf"
    plt.savefig(out, bbox_inches="tight")
    print(f"✔ Saved {out}")
    plt.show()

if __name__ == "__main__":
    main()
