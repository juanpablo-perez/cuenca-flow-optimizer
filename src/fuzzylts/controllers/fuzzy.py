# src/fuzzylts/controllers/fuzzy.py

"""
controllers.fuzzy – Mamdani fuzzy-controller with integrated CSV logging
─────────────────────────────────────────────────────────────────────────
Applies fuzzy inference to compute adaptive green durations. Logs per-lane
queue lengths and green-phase assignments into CSVs under the run directory.
"""

from __future__ import annotations
import csv
import os
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import traci
from skfuzzy import control as ctrl

from fuzzylts.utils.fuzzy_system import generate_memberships, build_rules
from fuzzylts.utils.log import get_logger
from . import fuzzy_defs as defs  # membership definitions, rule base, phase mapping

log = get_logger(__name__)

# ── Build fuzzy system once ─────────────────────────────────────────────
_vars = generate_memberships(defs.funciones)
_rules = build_rules(defs.reglas_definidas,
                                  _vars["vehiculos"],
                                  _vars["llegada"],
                                  _vars["verde"])
_fuzzy_system = ctrl.ControlSystem(_rules)
_simulator = ctrl.ControlSystemSimulation(_fuzzy_system)
log.info("Fuzzy controller initialized with %d rules", len(_rules))

# ── CSV file setup ──────────────────────────────────────────────────────
RUN_DIR = Path(os.getenv("FUZZYLTS_RUN_DIR", "."))
CSV_QUEUE = RUN_DIR / "data_queu_fuzzy.csv"
CSV_PHASE = RUN_DIR / "data_tls_fuzzy.csv"

def _ensure_csv(path: Path, header: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(header + "\n", encoding="utf-8")

_ensure_csv(CSV_QUEUE, "time,lane_id,queue_length")
_ensure_csv(CSV_PHASE, "time,traffic_light_id,phase,green_duration,vehicles_in_phase")

# ── Lane state for arrival-rate estimation ─────────────────────────────
_lane_state: Dict[str, Tuple[float, int]] = {}

def _queue_and_rate(lane: str) -> Tuple[int, float]:
    """
    Return (queue_length, arrival_rate) and update internal state.
    Arrival rate = delta(count) / delta(time).
    """
    now = traci.simulation.getTime()
    count = traci.lane.getLastStepVehicleNumber(lane)
    prev_time, prev_count = _lane_state.get(lane, (now, count))
    rate = (count - prev_count) / max(now - prev_time, 1e-3)
    _lane_state[lane] = (now, count)
    return count, max(rate, 0.0)

# ── Logging helpers ─────────────────────────────────────────────────────
def _log_queue(now: float, lanes: List[str]) -> None:
    with CSV_QUEUE.open("a", newline="") as f:
        writer = csv.writer(f)
        for lane in lanes:
            writer.writerow([now, lane, traci.lane.getLastStepVehicleNumber(lane)])

def _log_phase(now: float, tls_id: str, phase: int,
               green_dur: int, total_vehicles: int) -> None:
    with CSV_PHASE.open("a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([now, tls_id, phase, green_dur, total_vehicles])

# ── Fuzzy inference core ────────────────────────────────────────────────
def _compute_green(vehicles: int, rate: float) -> int:
    if vehicles <= 3:
        # minimum green bound
        return int(defs.funciones["verde"]["lmin"])
    _sim = _simulator
    _sim.input["vehiculos"] = vehicles
    _sim.input["llegada"] = rate
    _sim.compute()
    return int(_sim.output["verde"])

# ── Public API ──────────────────────────────────────────────────────────

def get_phase_duration(tls_id: str) -> int:
    """
    Called each simulation step to record data and compute new green time
    when a green phase begins (phases 0 or 2). Returns 0 when no change.
    """
    phase = traci.trafficlight.getPhase(tls_id)
    # Only process green phases
    if phase not in (0, 2):
        return 0

    # Gather lane metrics
    lanes = defs.fases_lanes_dict[tls_id][phase]
    total_vehicles = 0
    rates: List[float] = []
    for lane in lanes:
        q, r = _queue_and_rate(lane)
        total_vehicles += q
        if r > 0:
            rates.append(r)
    avg_rate = float(np.mean(rates)) if rates else 0.0

    # Compute green duration
    green_dur = _compute_green(total_vehicles, avg_rate)

    now = traci.simulation.getTime()
    _log_queue(now, lanes)
    _log_phase(now, tls_id, phase, green_dur, total_vehicles)

    log.debug(
        "Fuzzy %s phase %d → vehicles=%d, rate=%.3f → green=%ds",
        tls_id, phase, total_vehicles, avg_rate, green_dur,
    )
    return green_dur
