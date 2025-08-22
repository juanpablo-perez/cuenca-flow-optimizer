# Gap–Fuzzy Adaptive Signal Control
**Enhancing Urban Traffic Efficiency with Hybrid Gap-Out + Fuzzy Logic**

This repository contains the code, data-processing pipeline, and plotting scripts that accompany the paper:

> **Gap–Fuzzy Adaptive Signal Control: Enhancing Urban Traffic Efficiency**  
<!--> Camera-ready version included in `/paper/` (or see the PDF attached to the repository release).-->

The project evaluates a hybrid controller that (i) uses a Mamdani-type fuzzy system to propose green durations from queue length and arrival rate, and (ii) overlays a lightweight **gap‑out** mechanism to terminate green when no vehicles are detected after a short minimum time. We benchmark against a **Fixed-Time (Static)** baseline and SUMO’s **Loop‑Actuated** controller on a **city‑scale SUMO network of Cuenca, Ecuador**.

---

## ✅ Highlights
- **City-scale simulation** of Cuenca exported from OpenStreetMap (OSM) as `sumo_files/cuenca.net.xml.gz`.
- Four demand scenarios parameterized by **target volume-to-capacity** \(\phi = v/c\) (Low, Medium, High, Very High).
- End-to-end, reproducible pipeline: **route generation → batch experiments → CSV caching → IEEE‑style plots**.
- Cleanly separated controller implementations: `static`, `actuated`, `fuzzy`, and `gap_fuzzy`.
- Camera-ready figures (PDF) for **waiting time** and **CO₂ emissions** included under `plots/` once generated.

> ℹ️ **OSM attribution:** © OpenStreetMap contributors. Data used under the Open Database License (ODbL).

---

## ⚙️ Requirements
- **Python** ≥ 3.10
- **SUMO** ≥ 1.24 (tested with 1.24.x). Ensure `SUMO_HOME` is set:  
  - Linux/macOS: `export SUMO_HOME=/path/to/sumo`
  - Windows (PowerShell): `$env:SUMO_HOME="C:\Program Files (x86)\Eclipse\Sumo"`
- Python packages: see `requirements.txt`

Install Python dependencies in a virtual environment:
```bash
python -m venv .venv && source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

> Optional but recommended for CLI module usage:
```bash
pip install -e .
```
If you prefer not to install as a package, you can run modules by adding the source path:
```bash
export PYTHONPATH=$PWD/src  # Windows PowerShell: $env:PYTHONPATH="$PWD/src"
```

---

## 📂 Repository Layout
```
.
├── configs/
│   └── controller/            # YAML configs: static.yaml, actuated.yaml, fuzzy.yaml
├── data/                      # Cached CSVs (tripinfo, emissions, experiment metrics)
├── experiments/               # Per-run outputs (ignored by git; created by pipeline)
├── plotters/                  # Plot style (IEEE) and utilities
├── plots/                     # Generated figures (PDF)
├── scripts/
│   └── run_all.py             # 150-run batch: 3 controllers × 5 scenarios × 10 seeds
├── src/
│   └── fuzzylts/
│       ├── controllers/       # static, actuated, fuzzy, gap_fuzzy
│       ├── pipelines/         # run_experiment.py (single-run wrapper)
│       ├── sim/               # SUMO runner (TraCI)
│       ├── utils/             # IO, stats, logging, fuzzy system, net parsing
│       └── routint/           # generate_routes.py  (route generator)
├── sumo_files/                # Network and base SUMO config (osm.sumocfg, routes)
├── requirements.txt
└── README.md
```

---

## 🚦 Controllers
- **Static**: fixed timings per local ordinance (e.g., green 42 s, amber 3 s) applied as constant phase durations.
- **Actuated**: SUMO’s loop‑actuated program with practical bounds (e.g., min green 15 s).
- **Fuzzy**: Mamdani inference with five membership levels per variable; outputs are capped **15–36 s** (upper bound found via simulated‑annealing tuning).
- **Gap–Fuzzy**: Fuzzy + **gap‑out**; if the lane group is empty for \(T_\text{gap}=2\) s after \(T_\text{min}=2\) s of green, advance the phase.

Inputs (**queue length**, **arrival rate**) are computed over an **upstream corridor**: mapped lanes plus straight‑through connections up to two street changes (two links), ignoring internal edges and merging contiguous OSM splits along the same street base.

---

## 🗺️ Scenarios & Demand
Scenarios are parameterized by target \(\phi = v/c\). The route generator derives the insertion rate
\(
q_\text{target} = \phi \cdot n_\text{in} \cdot C_\ell
\)
(veh/h), where \(n_\text{in}\) is the effective inbound lane count and \(C_\ell\) an effective per‑lane capacity.

Typical defaults (code):  
Low 0.165, Medium 0.325, High 0.620, Very‑High 0.780. See the paper for the Medium‑Extended time‑of‑day profile used in temporal plots.

---

## ▶️ How to Run

### 1) Generate demand (routes)
Using the module (if installed):
```bash
python -m fuzzylts.routing.generate_routes --net sumo_files/cuenca.net.xml.gz --hours 4 --out sumo_files/routes --scenario all --seed 42
```
Or directly as a script:
```bash
python src/fuzzylts/routing/generate_routes.py --net sumo_files/cuenca.net.xml.gz --hours 4 --out sumo_files/routes --scenario all --seed 42
```

### 2) Single experiment
```bash
python -m fuzzylts.pipelines.run_experiment \
  --controller gap_fuzzy \
  --scenario medium \
  --net-file cuenca.net.xml.gz \
  --sumo-binary sumo \
  --seed 1
```
Outputs (per run) are written to `experiments/<controller>_<scenario>_<seed>/`:
```
tripinfo.xml, emissions.xml(.gz), stats.xml, metrics.json, config.json
```

### 3) Batch (150 runs)
```bash
python scripts/sweep_experiments.py
```
This iterates **3 controllers × 5 scenarios × 10 seeds**.

---

## 📊 Build CSVs & Make Figures

### Aggregate results to CSV
```bash
# writes: data/experiment_metrics.csv, data/tripinfo.csv, data/emissions_CO2.csv
python -m fuzzylts.utils.stats
```

### Plots (PDF)
```bash
# Waiting time: grouped bars across scenarios
python plotters/plot_waiting_time_bar.py

# Waiting time: evolution (Medium-Extended), 10-min bins
python plotters/plot_waiting_time_over_time.py

# CO2: grouped bars across scenarios
python plotters/plot_emissions_bar.py

# CO2: evolution (Medium-Extended), 15-min bins
python plotters/plot_emissions_over_time.py
```
Generated PDFs appear in `plots/`. The plotting scripts adopt an IEEE‑friendly style (tight layout, small caps, CI whiskers).

---

## 🔁 Reproducibility Notes
- SUMO step length: **1.0 s**; emissions period: **900 s**.
- Fuzzy output clamped to **15–36 s** (36 s selected via simulated‑annealing for best delay trade‑off).
- Gap‑out thresholds: \(T_\text{min}=2\) s, \(T_\text{gap}=2\) s.
- Batch experiments use **10 seeds** per scenario.
- The `experiments/` directory is intentionally **git‑ignored** due to size.

---

## 📝 Citation
If you use this code or data, please cite the paper and the repository:

<!-- ```bibtex
@inproceedings{gap-fuzzy-2025,
  title        = {Gap--Fuzzy Adaptive Signal Control: Enhancing Urban Traffic Efficiency},
  author       = {Juan Pérez, Jorge Zhangallimbay, Pablo Barbecho Bautista},
  booktitle    = {...},
  year         = {2025},
}
```
> A DOI for the repository (e.g., via Zenodo) can be added post‑publication. -->

---

## 📄 License
This project is distributed under the terms of the license in `LICENSE`.
Please respect OSM’s ODbL for underlying map data.

## 🐞 Issues
Please use **GitHub Issues** for bug reports and feature requests. Include your SUMO version, OS, and a minimal command to reproduce.
