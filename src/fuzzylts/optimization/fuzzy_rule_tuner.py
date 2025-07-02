#!/usr/bin/env python3
#  src/fuzzylts/optimization/fuzzy_rule_tuner.py
"""
Simulated-Annealing tuner that mutates the **fuzzy rule-base in memory**.

No YAML rewrites and no subprocesses – much faster than spawning SUMO
for every candidate.  The neighbourhood is richer than a simple ±1
shift, and the schedule auto-reheats if the search stalls.

Example
-------
python -m fuzzylts.optimization.fuzzy_rule_tuner \
       --scenario medium --seed 0 --iters 100
"""
from __future__ import annotations

import argparse
import logging
import math
import random
from pathlib import Path
from typing import Dict, List, Tuple

import yaml
from tqdm import trange
import os

from fuzzylts.controllers import fuzzy as ctl
from fuzzylts.sim.runner   import run_sumo_once
from fuzzylts.utils.io     import tripinfo_xml_to_df

# ─────────────────── static paths & levels ──────────────────────────────
ROOT       = Path(__file__).resolve().parents[3]
SUMOCFG    = ROOT / "sumo_files" / "osm_fuzzy.sumocfg"
ROUTES_TPL = ROOT / "sumo_files" / "generated_routes_{scenario}.rou.xml"

GREEN_LEVELS = ["very_short", "short", "normal", "long", "very_long"]

LOG_FMT = "%(asctime)s | %(levelname)-8s | %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FMT, datefmt="%H:%M:%S")
log = logging.getLogger("rule-tuner")

# ───────────────────────── helpers  ─────────────────────────────────────
RuleKey   = Tuple[str, str]                    # (vehicles_level, arrival_level)
RuleMat   = Dict[RuleKey, str]                 # → green_level
RuleListT = List[List[str]]                    # [veh, arr, green]

def rules_to_matrix(rules: RuleListT) -> RuleMat:
    return {(v, a): g for v, a, g in rules}

def matrix_to_rules(mat: RuleMat) -> RuleListT:
    return [[v, a, g] for (v, a), g in mat.items()]

# -------------------------- neighbourhood -------------------------------

def shift_one_level(mat: RuleMat) -> RuleMat:
    """±1 step for a single rule (your original move)."""
    new = mat.copy()
    k   = random.choice(list(new))
    idx = GREEN_LEVELS.index(new[k]) + random.choice([-1, 1])
    new[k] = GREEN_LEVELS[max(0, min(len(GREEN_LEVELS) - 1, idx))]
    return new

def random_reassign(mat: RuleMat) -> RuleMat:
    new = mat.copy()
    k   = random.choice(list(new))
    new[k] = random.choice(GREEN_LEVELS)
    return new

def swap_two(mat: RuleMat) -> RuleMat:
    """Swap the outputs of two random cells."""
    new = mat.copy()
    k1, k2 = random.sample(list(new), 2)
    new[k1], new[k2] = new[k2], new[k1]
    return new

MOVES = (shift_one_level, random_reassign, swap_two)

# -------------------------- simulator -----------------------------------

def simulate(mat_rules: RuleMat, scenario: str,
             seed: int, out_dir: Path) -> float:
    """Run one SUMO sim and return mean waiting time."""
    ctl.cfg.rules = matrix_to_rules(mat_rules)          # hot-swap rule base
    routes = Path(str(ROUTES_TPL).format(scenario=scenario))
    os.environ['FUZZYLTS_RUN_DIR'] = str(out_dir)
    tripinfo_xml, _ = run_sumo_once(
        controller="fuzzy",
        routes_xml=routes,
        sumocfg=SUMOCFG,
        output_dir=out_dir,
        sim_seed=seed,
    )
    df = tripinfo_xml_to_df(tripinfo_xml)
    return float(df["waitingTime"].mean())

# ─────────────────────────── main loop ──────────────────────────────────
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", required=True,
                    choices=["low", "medium", "high", "very_high"])
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--iters", type=int, default=100)
    args = ap.parse_args()
    random.seed(args.seed)

    work = ROOT / "experiments" / "rule_tune" / args.scenario
    work.mkdir(parents=True, exist_ok=True)

    # baseline
    best_mat = rules_to_matrix(ctl.cfg.rules)
    best     = simulate(best_mat, args.scenario, args.seed, work / "run_00")
    log.info("[00] baseline avg_wait = %.3fs", best)

    # SA hyper-params
    T_init          = 2.0
    T_reheat        = 1.0          # temp when plateau detected
    stall_patience  = 10           # iterations without improvement → reheating
    early_stop      = 8            # stop if < tol improvement *early_stop* times
    tol             = 0.02         # 0.02 s improvement considered negligible

    no_improve = 0
    small_imp  = 0

    prog = trange(1, args.iters + 1, unit="iter")
    for i in prog:
        T = T_init * (1 - i / args.iters)

        # pick a move type at random
        neighbour_fn = random.choice(MOVES)
        cand_mat     = neighbour_fn(best_mat)
        score        = simulate(cand_mat, args.scenario,
                                args.seed + i, work / f"run_{i:03d}")

        delta   = score - best
        accept  = delta < 0 or random.random() < math.exp(-delta / max(T, 1e-6))

        if accept:
            best_mat = cand_mat
            if score < best:
                imp = best - score
                best = score
                (work / f"best_{best:.3f}.yaml").write_text(
                    yaml.safe_dump({"rules": matrix_to_rules(best_mat)},
                                   allow_unicode=True)
                )
                no_improve = 0
                small_imp  = 0 if imp > tol else small_imp + 1
            else:
                no_improve += 1
        else:
            no_improve += 1

        # plateau? → reheat
        if no_improve >= stall_patience:
            T_init = T_reheat
            no_improve = 0
            prog.write("↺  reheating temperature")

        prog.set_postfix(wait=f"{best:.3f}s", T=f"{T:.2f}")

        if small_imp >= early_stop:
            prog.write("Early-stop: improvements below tol")
            break

    log.info("✓ optimisation finished – best avg_wait = %.3fs", best)

if __name__ == "__main__":
    main()
