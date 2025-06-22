# Cuenca Adaptive TLS

**Adaptive Traffic-Light Control to Optimize Urban Traffic Flow:  
A Case Study in the City of Cuenca, Ecuador**

---

## Authors

- **Juan Pablo Pérez Vargas**  
  Facultad de Ingeniería, Universidad de Cuenca  
  Cuenca, Ecuador · jpablo.perezv@ucuenca.edu.ec

- **Jorge Geovanny Zhangallimbay Coraizaca**  
  Facultad de Ingeniería, Universidad de Cuenca  
  Cuenca, Ecuador · jorge.zhangallimbay@ucuenca.edu.ec

---

## Abstract

The city of Cuenca faces growing vehicular congestion due to an increasing number of vehicles, urban planning challenges, and unsynchronized traffic signals.  
To improve traffic flow in the downtown area, we propose and evaluate two traffic-light control schemes:

1. **Static** – fixed signal timings as defined in the network file.  
2. **Fuzzy** – adaptive green times via a Mamdani fuzzy inference system.  
3. **Actuated (SUMO)** – SUMO’s built-in actuated traffic-light logic, recorded for comparison.

We conducted SUMO simulations across four traffic-demand scenarios (low, medium, high, very high), running **N = 10 seeds** per scenario/controller.  
Results demonstrate that the fuzzy controller significantly reduces average waiting times and travel times compared to the static baseline, and XXXXXXXXX.

**Keywords**: vehicular congestion · adaptive traffic-light control · fuzzy logic · actuated traffic lights · traffic simulation · Cuenca

---

## Quick Start

```bash
# 1. Clone & setup
git clone https://github.com/juanpablo-perez/.git
cd <repo-name>
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install -e .

# 2. Run a simulation
python -m fuzzylts.pipelines.run_experiment        --controller fuzzy        --scenario   medium        --seed       0        --log-level  INFO
```

By replacing `--controller fuzzy` with `static` or `actuated`, you can compare all three modes.  
Results will be stored in `experiments/<controller>_<scenario>_<seed>_<timestamp>/`.

---

## Project Structure

```
.
├── sumo_files/              ← network & route definitions (.sumocfg, .rou.xml)
├── src/fuzzylts/            ← Python package (editable)
│   ├── controllers/         ← static, actuated, fuzzy controllers
│   ├── pipelines/           ← CLI entry-points
│   ├── sim/runner.py        ← SUMO+TraCI wrapper
│   └── utils/               ← I/O, logging, fuzzy-system helpers
├── experiments/             ← auto-generated outputs per run
├── scripts/                 ← helper scripts (benchmark, plotting)
└── README.md                ← this document
```

---

## Full Benchmark

```bash
bash scripts/run_full_benchmark.sh
```

By default it runs **10 seeds × 4 scenarios × 3 controllers** ≈ 120 simulations.

---

## Results & Visualization

- **Raw outputs**:  
  `tripinfo.xml`, `stats.xml`

- **Adaptive logs**:  
  `experiments/.../datos_colas_fuzzy.csv`  
  `experiments/.../datos_semaforos_fuzzy.csv`  
  `experiments/.../datos_semaforos_actuated.csv`

- **Summarized metrics**:  
  `metrics.json` (avg wait, travel time, speed, teleports)

Use the scripts under `scripts/` or the Jupyter notebooks under `notebooks/` to generate confidence-interval plots.

---

## Citation

If you use this work, please cite:

```bibtex
@article{perez2025adaptive,
  title   = {Adaptive Traffic-Light Control to Optimize Urban Traffic Flow: A Case Study in the City of Cuenca, Ecuador},
  author  = {Pérez Vargas, Juan Pablo and Zhangallimbay Coraizaca, Jorge Geovanny},
  journal = {Applied Simulation in Transportation},
  year    = {2025},
  url     = {https://github.com/<you>/<repo-name>}
}
```

---

## License

[MIT License](LICENSE) © 2025 Juan Pablo Pérez Vargas & Jorge Geovanny Zhangallimbay Coraizaca
