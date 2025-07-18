# Cuenca Adaptive TLS

**Adaptive Traffic-Light Control to Optimise Urban Traffic Flow  
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

The historic centre of Cuenca suffers recurring congestion due to rising
motorisation, geometric constraints, and poorly coordinated signals.
We evaluate three control strategies in SUMO:

1. **Static** – fixed splits prescribed by municipal regulation.  
2. **Loop-Actuated** – SUMO’s off-the-shelf loop-detector logic.  
3. **Gap-Fuzzy (proposed)** – a Mamdani fuzzy core for green-time
   extension, wrapped by a *gap-out* overlay that cuts the phase when
   the queue has been empty for 2 s (min. green 2 s).

Four demand levels are simulated (low → very‑high).  
Across **N = 10 seeds** the Gap-Fuzzy controller lowers mean waiting time
by up to 13 % under light traffic and matches Loop‑Actuated under heavy
loads, while always outperforming the static baseline.

**Keywords**: traffic simulation · adaptive traffic lights · gap‑out
termination · fuzzy logic · Cuenca

---

## Quick Start

```bash
# 1 · Clone & set‑up
git clone https://github.com/juanpablo-perez/cuenca-flow-optimizer.git
cd cuenca-flow-optimizer
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install -e .

# 2 · Run a single experiment (medium demand, seed 0)
python -m fuzzylts.pipelines.run_experiment \
       --controller gap_fuzzy \
       --scenario   medium \
       --seed       0 \
       --log-level  INFO
```

Replace `--controller gap_fuzzy` with `static`, `actuated` or `fuzzy`
to compare all strategies.  
Results are written to  
`experiments/<controller>_<scenario>_<seed>/`.

---

## Project Structure

```
.
├── sumo_files/              ← network & routes (.sumocfg, .rou.xml)
├── src/fuzzylts/
│   ├── controllers/         ← static · actuated · gap_fuzzy
│   ├── sim/runner.py        ← SUMO + TraCI wrapper
│   ├── pipelines/           ← CLI entry-points
│   └── utils/               ← I/O, logging, fuzzy helpers
├── scripts/                 ← batch & plotting helpers
├── experiments/             ← auto-generated outputs
└── README.md
```

---

## Full Benchmark

```bash
bash scripts/run_full_benchmark.sh
```

Runs **10 seeds × 4 scenarios × 3 controllers = 120** simulations
(~2 h on a 6‑core laptop).

---

## Results & Visualisation

| Artifact                          | Produced by | Notes |
|-----------------------------------|-------------|-------|
| `tripinfo.xml`, `emissions.xml`   | SUMO        | One per experiment |
| `data_queue_fuzzy.csv`, `data_tls_gf.csv` | Controller | Queue & phase history |
| `plots/*.pdf`                     | `plotters/` | Bar charts, intraday curves |

Example figures appear in the **Results** section of the paper
(see `docs/paper.pdf`).

---

## Gap–Fuzzy Logic (bird’s‑eye view)

```text
┌──Queue detectors (TraCI)──────────┐
│ if queue empty ≥2 s and green ≥2 s│───Yes──▶ Immediate phase change
└─────────────────────────┬─────────┘
                          No
                    ┌──Mamdani FIS──┐
                    │ green-time Δ  │
                    └───────────────┘
```

*A full TikZ diagram lives in
`docs/figures/gap_fuzzy_block.tikz`.*

---

## How to Cite

```bibtex
@article{perez2025adaptive,
  title   = {  },
  author  = {Pérez Vargas, Juan Pablo and Zhangallimbay Coraizaca, Jorge Geovanny},
  journal = {},
  year    = {2025},
  url     = {https://github.com/juanpablo-perez/cuenca-flow-optimizer}
}
```

---

## License

[MIT](LICENSE) © 2025 Juan Pablo Pérez Vargas &  
Jorge Geovanny Zhangallimbay Coraizaca

