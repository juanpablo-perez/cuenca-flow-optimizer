#!/usr/bin/env python3
"""
Sweep controller x scenario x seed and aggregate metrics.
"""
import subprocess
from itertools import product
import pandas as pd
from fuzzylts.utils.stats import load_experiment_metrics, ci


# CONTROLLERS = ["static","actuated","fuzzy"]
CONTROLLERS = ["gap_actuated"]
SCENARIOS   = ["low"]
SEEDS       = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]

def run_one(ctrl, scn, seed):
    cmd = [
      "python","-m","fuzzylts.pipelines.run_experiment",
      "--controller", ctrl,
      "--scenario",   scn,
      "--seed",       str(seed),
    ]
    subprocess.check_call(cmd)

if __name__ == "__main__":
    for ctrl, scn, seed in product(CONTROLLERS, SCENARIOS, SEEDS):
        print(f"→ Running {ctrl} / {scn} / seed={seed}")
        run_one(ctrl, scn, seed)

    # Once all runs are done, load & summarize
    # df = load_experiment_metrics()
    # summary = (
    #   df
    #   .groupby(["controller","scenario"])
    #   .agg(
    #     avg_wait     = pd.NamedAgg("avg_wait",     "mean"),
    #     ci_wait_low  = pd.NamedAgg("avg_wait", lambda s: ci(s)[0]),
    #     ci_wait_high = pd.NamedAgg("avg_wait", lambda s: ci(s)[1]),
    #     avg_duration = pd.NamedAgg("avg_duration", "mean"),
    #     # … add more as you like
    #   )
    #   .reset_index()
    # )
    # summary.to_csv("experiments/summary.csv", index=False)
    # print("Done. Summary written to experiments/summary.csv")
