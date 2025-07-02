# src/fuzzylts/optimization/fuzzy_tuner.py

import subprocess
import yaml
from pathlib import Path
from itertools import product

import pandas as pd
from fuzzylts.utils.stats import load_experiment_metrics

# where to find your fuzzy controller config
FUZZY_CFG = Path(__file__).resolve().parents[3] / "configs" / "controller" / "fuzzy.yaml"

# the scenarios and seeds you want to test
SCENARIOS = ["low", "medium", "high", "very_high"]
SEEDS     = [0, 1, 2, 3, 4]

def run_all(controller: str, scenario: str, seed: int) -> None:
    """Invoke your run_experiment script."""
    cmd = [
        "python", "-m", "fuzzylts.pipelines.run_experiment",
        "--controller", controller,
        "--scenario",   scenario,
        "--seed",       str(seed),
    ]
    subprocess.run(cmd, check=True)

def tune_green_bounds(lmin_vals, lmax_vals):
    """
    Grid-search over pairs of (lmin, lmax) for the 'green' membership function.
    Returns a DataFrame of results.
    """
    results = []
    base = yaml.safe_load(FUZZY_CFG.read_text())

    for lmin, lmax in product(lmin_vals, lmax_vals):
        # skip invalid configs
        if lmin >= lmax:
            continue

        # patch config
        cfg = base.copy()
        cfg["functions"]["green"]["lmin"] = float(lmin)
        cfg["functions"]["green"]["lmax"] = float(lmax)
        # write it back
        FUZZY_CFG.write_text(yaml.safe_dump(cfg), encoding="utf-8")

        # run experiments
        for scenario in SCENARIOS:
            for seed in SEEDS:
                run_all("fuzzy", scenario, seed)

        # collect metrics
        df = load_experiment_metrics()
        # only take fuzzy runs
        df_fz = df[df.controller == "fuzzy"]

        # compute mean waiting time across all scenarios & seeds
        mean_wait = df_fz["avg_wait"].mean()
        results.append({
            "lmin": lmin,
            "lmax": lmax,
            "mean_wait": mean_wait
        })
        print(f"Tested green=[{lmin},{lmax}] → mean_wait={mean_wait:.2f}s")

    # restore original config
    FUZZY_CFG.write_text(yaml.safe_dump(base), encoding="utf-8")

    return pd.DataFrame(results)


if __name__ == "__main__":
    # define your search grid here
    lmin_grid = [10, 15, 20]
    lmax_grid = [40, 50, 60]

    df_results = tune_green_bounds(lmin_grid, lmax_grid)
    print("\n=== All results ===")
    print(df_results.sort_values("mean_wait").head(10))
    df_results.to_csv("fuzzy_tuning_results.csv", index=False)
    print("Saved detailed results to fuzzy_tuning_results.csv")
