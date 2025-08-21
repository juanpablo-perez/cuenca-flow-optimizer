#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/sweep_experiments.py

Run all experiments used in the paper: 3 controllers × 5 scenarios × 10 seeds = 150 runs.

This script executes the experiment runner module repeatedly, one run per
(controller, scenario, seed) triple, relying on **pre-generated routes**
(e.g., `generated_routes_<scenario>.rou.xml`) and the specified network file.

Usage
-----
    python scripts/sweep_experiments.py

Notes
-----
- The network file path is taken from the `NET` constant below.
- This script is intentionally sequential to preserve the original workflow.
- Any failure in a run will raise an exception and stop subsequent runs.
"""

from __future__ import annotations

import logging
import subprocess
import sys
from itertools import product
from typing import List

# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

# Experiment grid
CONTROLLERS: List[str] = ["static", "actuated", "gap_fuzzy"]
SCENARIOS: List[str] = ["low", "medium", "high", "very_high", "medium_extended"]
SEEDS: List[int] = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]

# Network file (assumed to be accessible from the 'sumo_files' directory)
NET: str = "cuenca.net.xml.gz"

# Entry point module
RUNNER_MODULE: str = "fuzzylts.pipelines.run_experiment"

# Logging
LOGGER = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Execution
# ─────────────────────────────────────────────────────────────────────────────
def run_one(ctrl: str, scn: str, seed: int) -> None:
    """Run a single experiment instance.

    Args:
        ctrl: Controller name (e.g., 'static', 'actuated', 'gap_fuzzy').
        scn: Scenario name (e.g., 'low', 'medium', 'high', 'very_high', 'medium_extended').
        seed: Integer seed (1..10 in the paper).

    Raises:
        subprocess.CalledProcessError: If the underlying runner exits non-zero.
    """
    cmd = [
        sys.executable,
        "-m",
        RUNNER_MODULE,
        "--controller",
        ctrl,
        "--scenario",
        scn,
        "--seed",
        str(seed),
        "--net-file",
        NET,
    ]
    LOGGER.info("Running: controller=%s | scenario=%s | seed=%s", ctrl, scn, seed)
    subprocess.check_call(cmd)


def main() -> None:
    """Execute the full grid of (controller, scenario, seed)."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    total = len(CONTROLLERS) * len(SCENARIOS) * len(SEEDS)
    LOGGER.info("Starting full sweep: %d runs (3x5x10)", total)

    for ctrl, scn, seed in product(CONTROLLERS, SCENARIOS, SEEDS):
        print(f"\n====> Running | controller={ctrl} | scenario={scn} | seed={seed}\n")
        run_one(ctrl, scn, seed)

    LOGGER.info("All runs completed successfully.")


if __name__ == "__main__":
    main()
