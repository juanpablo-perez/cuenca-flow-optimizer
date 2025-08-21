# Gap–Fuzzy Adaptive Signal Control (Cuenca Flow Optimizer)

**Repository for the methodology and artifacts used in the paper:**  
**“Gap–Fuzzy Adaptive Signal Control: Enhancing Urban Traffic Efficiency”**  
Authors: Juan Pérez¹, Jorge Zhangallimbay¹, Pablo Barbecho Bautista¹  
¹Universidad de Cuenca, Ecuador

> This repository contains the SUMO/TRaCI controllers, routing assets, experiment runner, data aggregation, and plotting code used to produce the results and figures in the paper.

---

## Table of Contents

- [Overview](#overview)
- [Repository Layout](#repository-layout)
- [Prerequisites](#prerequisites)
- [Quick Start (reproduce paper figures)](#quick-start-reproduce-paper-figures)
- [Scenarios, Controllers & Seeds](#scenarios-controllers--seeds)
- [Routing assets & route generation](#routing-assets--route-generation)
- [Running simulations](#running-simulations)
- [Aggregating results](#aggregating-results)
- [Plotting](#plotting)
- [Reproducibility notes](#reproducibility-notes)
- [Troubleshooting](#troubleshooting)
- [Citation](#citation)
- [License](#license)

---

## Overview

We evaluate urban traffic-signal control strategies on a real map of **Cuenca, Ecuador** using the **SUMO** microscopic traffic simulator and the **TRaCI** API. The repository includes:

- **Controllers**: `static`, `actuated`, **`fuzzy`**, and **`gap_fuzzy`** (gap-actuated + fuzzy).
- **Routing assets**: the Cuenca network and pre-generated routes at five demand levels.
- **Experiment pipeline**: a single-run launcher and a sweep script.
- **Post-processing**: robust parsers and aggregations for `tripinfo.xml` and `emissions.xml`.
- **Plotters**: IEEE-ready figures used in the paper (PDF).

All code is written in Python and organized as a source package (`src/fuzzylts`) with command-line entry points using `python -m ...`.

---

## Repository Layout

```
cuenca-flow-optimizer/
├── configs/
│   └── controller/
│       ├── actuated.yaml     # min/max/nominal green & yellow for actuated
│       ├── fuzzy.yaml        # membership functions + rule base
│       └── static.yaml       # fixed green/yellow
├── data/                     # cached CSVs used to draw figures (paper results)
│   ├── experiment_metrics.csv
│   ├── tripinfo.csv
│   └── emissions_CO2.csv
├── plotters/                 # scripts to generate PDFs in ./plots
│   ├── ieee_style.py
│   ├── plot_emissions_bar.py
│   ├── plot_emissions_over_time.py
│   ├── plot_waiting_time_bar.py
│   └── plot_waiting_time_over_time.py
├── scripts/
│   └── run_all.py            # convenience sweep (scenarios × seeds × controllers)
├── src/fuzzylts/
│   ├── controllers/
│   │   ├── static.py         # fixed-time controller & netconvert wrapper
│   │   ├── actuated.py       # actuated controller & netconvert wrapper
│   │   ├── fuzzy.py          # scikit‑fuzzy controller
│   │   └── gap_fuzzy.py      # gap‑out logic + fuzzy delegate
│   ├── config/               # YAML-backed config loaders
│   │   ├── static_config.py
│   │   ├── actuated_config.py
│   │   └── fuzzy_config.py
│   ├── pipelines/
│   │   └── run_experiment.py # single-run launcher
│   ├── routing/
│   │   └── generate_routes.py# dynamic route generation (SUMO randomTrips)
│   ├── sim/
│   │   └── runner.py         # SUMO/TraCI runner (outputs tripinfo/emissions/stats)
│   └── utils/
│       ├── extract_phase_lanes.py
│       ├── fuzzy_system.py
│       ├── io.py
│       ├── log.py
│       └── stats.py          # CSV aggregation/cache
├── sumo_files/               # network + pre-generated routes used in the paper
│   ├── cuenca.net.xml.gz
│   ├── osm.sumocfg
│   ├── generated_routes_low.rou.xml
│   ├── generated_routes_medium.rou.xml
│   ├── generated_routes_medium_extended.rou.xml
│   ├── generated_routes_high.rou.xml
│   └── generated_routes_very_high.rou.xml
├── experiments/              # (git‑ignored) per-run outputs written here
├── LICENSE                   # MIT
├── README.md
└── requirements.txt
```

> **Note:** `experiments/` is not tracked due to size. We **do** include pre-aggregated CSVs in `data/` and the exact routing/network assets in `sumo_files/` to ensure full figure reproducibility.

---

## Prerequisites

- **Python** ≥ 3.10  
- **SUMO** (Simulation of Urban MObility) with `sumo`, `sumo-gui`, `netconvert`, and `tools/randomTrips.py` available  
  - Ensure `SUMO_HOME` is set (e.g., `/opt/sumo`), and binaries are on your `PATH`.
- Python packages: install with
  ```bash
  pip install -r requirements.txt
  pip install -e .
  ```
- Add the source tree to your module path:
  ```bash
  # Linux/macOS
  export PYTHONPATH="$PWD/src:$PYTHONPATH"
  # Windows PowerShell
  setx PYTHONPATH "$pwd\src;%PYTHONPATH%"
  ```

### Verify your setup

```bash
sumo --version
python -c "import traci, sys; print('traci', traci.__version__); print('PYTHONPATH ok:', any('src' in p for p in sys.path))"
```

---

## Quick Start (reproduce paper figures)

The repository ships with **pre-aggregated CSVs** under `data/` generated from the 150-paper runs (5 scenarios × 3 controllers × 10 seeds). To build the PDFs:

```bash
# From the repo root (after installing requirements and setting PYTHONPATH)
python -m plotters.plot_emissions_bar
python -m plotters.plot_emissions_over_time
python -m plotters.plot_waiting_time_bar
python -m plotters.plot_waiting_time_over_time
```

PDFs will be written to `./plots`. These match the figures reported in the paper.

> If you want to regenerate the CSVs locally from your own simulations, see [Aggregating results](#aggregating-results).

---

## Scenarios, Controllers & Seeds

**Scenarios** (`--scenario`):
- `low`, `medium`, `high`, `very_high`, `medium_extended`

**Controllers** (`--controller`):
- `static` — fixed splits; parameters in `configs/controller/static.yaml`  
- `actuated` — min/max/nominal green + fixed yellow; see `configs/controller/actuated.yaml`  
- `fuzzy` — scikit‑fuzzy controller; membership & rules in `configs/controller/fuzzy.yaml`  
- `gap_fuzzy` — *gap‑out* on no-demand (after a minimum green), else delegate to **fuzzy**

**Seeds**: each (controller, scenario) is run **10 times** with seeds `1..10` for statistical analysis.

---

## Routing assets & route generation

### What the paper uses (pre-generated)

To ensure strict reproducibility, **all experiments in the paper use pre‑generated routes** stored in the repository:

- **Network**: `sumo_files/cuenca.net.xml.gz`  
- **Routes**: `sumo_files/generated_routes_<scenario>.rou.xml` for the five scenarios  
  (`low`, `medium`, `high`, `very_high`, `medium_extended`).

When you pass `--scenario` to the runner, it selects the matching `generated_routes_<scenario>.rou.xml` and couples it with the network you provide via `--net-file` (`cuenca.net.xml.gz`).

> You do **not** need to regenerate routes to reproduce the paper results.

### (Optional) Regenerating routes for new experiments

You have **two** options:

1) **Our dynamic tool** (recommended): `src/fuzzylts/routing/generate_routes.py`  
   It estimates a sensible demand level per scenario based on inbound lane capacity and signal density and then calls SUMO’s `randomTrips.py` under the hood. Example:

   ```bash
   # Recreate the five scenarios for a 2‑hour window, writing directly into sumo_files/
   python -m fuzzylts.routing.generate_routes \
     --net sumo_files/cuenca.net.xml.gz \
     --hours 2 \
     --out sumo_files \
     --seed 42 \
     --scenario all
   ```

   Key parameters (see the script for details):
   - Target v/c per scenario (`SCENARIO_VC`): low≈0.165, medium≈0.325, high≈0.62, very_high≈0.78 (clamped).  
   - Capacity heuristics: base per-lane capacity × signal-density factor.  
   - Safety clamps: max v/c, max counted inbound lanes per edge, absolute injection ceiling.

2) **Raw SUMO tools** (for full control):
   - Generate trips with `randomTrips.py`, then convert to routes with `duarouter`, e.g.:
     ```bash
     python $SUMO_HOME/tools/randomTrips.py \
       -n sumo_files/your_network.net.xml \
       -o sumo_files/your_trips.trips.xml \
       --seed 1 --period 1.2 --binomial 2 --remove-loops --fringe-factor 3.0

     duarouter \
       -n sumo_files/your_network.net.xml \
       -t sumo_files/your_trips.trips.xml \
       -o sumo_files/generated_routes_custom.rou.xml \
       --routing-algorithm dijkstra --ignore-errors
     ```

> After generating custom routes, run experiments by pointing `--net-file` to your network and `--scenario` to a config you map to those routes (or extend the runner to accept an explicit `--route-file` flag).

---

## Running simulations

### Single run

```bash
# Example: gap–fuzzy on the medium scenario, seed=1
python -m fuzzylts.pipelines.run_experiment \
  --controller gap_fuzzy \
  --scenario medium \
  --seed 1 \
  --net-file cuenca.net.xml.gz \
  --sumo-binary sumo  # or --sumo-binary sumo-gui
```

Outputs are written to `experiments/<controller>_<scenario>_<seed>/`:
- `tripinfo.xml`, `emissions.xml` (and optionally `.gz`), `stats.xml`
- `metrics.json` — quick summary metrics

> Internally the runner sets **`TARGET_NET_XML`** so controllers can (re)build/inspect the network deterministically. Controllers may call `netconvert` to rebuild TLS programs (static/actuated) before running.

### Full sweep (5×3×10 = 150 runs)

A convenience script is included:

```bash
# Edit controllers in scripts/sweep_experiments.py if desired
python scripts/sweep_experiments.py
```

This iterates scenarios × seeds and calls the same `run_experiment` module.

---

## Aggregating results

After your runs exist under `experiments/`, aggregate caches to `data/`:

```bash
python -m fuzzylts.utils.stats
```

This produces:
- `data/experiment_metrics.csv` — one row per run (`metrics.json` merged with metadata)
- `data/tripinfo.csv` — concatenated `tripinfo.xml` across runs
- `data/emissions_CO2.csv` — time series wide table (`time, CO2`) across runs

These CSVs drive the plotting scripts below.

---

## Plotting

All plotters write PDF to `./plots` and follow an IEEE-friendly aesthetic (`plotters/ieee_style.py`).

- **Total emissions per scenario (bar, ±95% CI)**  
  ```bash
  python -m plotters.plot_emissions_bar
  ```

- **Emissions over time (per scenario, ±95% CI)**  
  ```bash
  python -m plotters.plot_emissions_over_time
  ```

- **Mean waiting time per scenario (bar, ±95% CI)**  
  ```bash
  python -m plotters.plot_waiting_time_bar
  ```

- **Waiting time over time (per scenario, ±95% CI)**  
  ```bash
  python -m plotters.plot_waiting_time_over_time
  ```

---

## Reproducibility notes

- **Seeds**: each (controller, scenario) is evaluated with seeds **1–10**.
- **Emission period**: runs use `--device.emissions.period 900` (15‑min bins).  
- **Controllers**:
  - `static`: green/yellow from YAML; network is rebuilt via `netconvert --tls.default-type static`.
  - `actuated`: min/max/nominal green & fixed yellow from YAML; network is rebuilt via `netconvert --tls.default-type actuated` and programs are initialized via TRaCI.
  - `fuzzy`: scikit‑fuzzy system with inputs **vehicles** and **arrival**; output **green**; membership sets and rule base in `configs/controller/fuzzy.yaml`.
  - `gap_fuzzy`: if **no vehicles** are detected for a short window (after a **minimum green**), force a **gap‑out** (phase advance); otherwise use the fuzzy suggestion.
- **Data/plots in repo**: to keep the repo lightweight, we include only aggregated CSVs (`data/`) and the final figures (`plots/`, if provided). The raw per‑run folders under `experiments/` are not tracked.

---

## Troubleshooting

- **`ModuleNotFoundError: fuzzylts`** → Ensure `PYTHONPATH` includes the `src/` directory (see [Prerequisites](#prerequisites)).
- **`sumo`/`netconvert` not found** → Add SUMO binaries to your `PATH` and set `SUMO_HOME`.
- **`randomTrips.py` not found** → Ensure `SUMO_HOME/tools` exists; the route generator locates it automatically once `SUMO_HOME` is set.
- **Permissions / long paths on Windows** → Prefer running from a short path (e.g., `C:\dev\cuenca`) and use a non‑system Python.
- **Large experiments** → The sweep will generate many files; ensure you have several GB of free space and consider compressing `emissions.xml` to `.gz`.

---

## Citation

If you use this repository, please cite:

```
Juan Pérez, Jorge Zhangallimbay, Pablo Barbecho Bautista,
"Gap–Fuzzy Adaptive Signal Control: Enhancing Urban Traffic Efficiency,"
in IEEE PE‑WASUN, 2025.
```

*A BibTeX entry will be added upon final publication.*

---

## License

This project is released under the **MIT License** (see [`LICENSE`](LICENSE)).
