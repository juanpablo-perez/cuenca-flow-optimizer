from __future__ import annotations
import csv
import os
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import traci
from skfuzzy import control as ctrl

from fuzzylts.config.fuzzy_config import FuzzyConfig
from fuzzylts.utils.fuzzy_system import generate_memberships, build_rules
from fuzzylts.utils.log import get_logger

log = get_logger(__name__)

# ── Load YAML config ────────────────────────────────────────────────────
_cfg_path = os.getenv("FUZZYLTS_FUZZY_CONFIG")
if _cfg_path:
    cfg = FuzzyConfig.load(
        Path(_cfg_path)
        )
else:
    cfg = FuzzyConfig.load(
        Path(__file__).resolve().parents[3] / "configs/controller/fuzzy.yaml"
    )

# ── Build fuzzy system once ─────────────────────────────────────────────
_vars   = generate_memberships(cfg.functions)
_rules  = build_rules(cfg.rules,
                     _vars["vehicles"],
                     _vars["arrival"],
                     _vars["green"])
 
_fuzzy_system = ctrl.ControlSystem(_rules)
_sim = ctrl.ControlSystemSimulation(_fuzzy_system)
log.info("Fuzzy controller initialized with %d rules", len(_rules))

# ── CSV file setup ──────────────────────────────────────────────────────
RUN_DIR     = Path(os.getenv("FUZZYLTS_RUN_DIR", "."))
CSV_QUEUE   = RUN_DIR / "data_queue_fuzzy.csv"
CSV_PHASE   = RUN_DIR / "data_tls_fuzzy.csv"


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
    Arrival rate = Δ(count) / Δ(time).
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
            cnt = traci.lane.getLastStepVehicleNumber(lane)
            writer.writerow([now, lane, cnt])


def _log_phase(now: float, tls_id: str, phase: int,
               green_dur: int, total_vehicles: int) -> None:
    with CSV_PHASE.open("a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([now, tls_id, phase, green_dur, total_vehicles])

# ── Fuzzy inference core ────────────────────────────────────────────────
def _compute_green(vehicles: int, rate: float) -> int:
    if vehicles <= 3:
        # minimum bound
        return int(cfg.functions["green"].lmin)
    _sim.input["vehicles"] = vehicles
    _sim.input["arrival"] = rate
    _sim.compute()
    return int(_sim.output["green"])

# ── Public API ──────────────────────────────────────────────────────────
def get_phase_duration(tls_id: str) -> int:
    """
    Called each simulation step to record data and compute new green time
    when a green phase begins (phases 0 or 2). Returns 0 when no change.
    """
    phase = traci.trafficlight.getPhase(tls_id)
    # Only process green phases 0 & 2
    if phase not in (0, 2):
        return 0

    lanes = cfg.phase_lanes[tls_id][phase]
    total_vehicles = 0
    rates: List[float] = []
    for lane in lanes:
        q, r = _queue_and_rate(lane)
        total_vehicles += q
        if r > 0:
            rates.append(r)
    avg_rate = float(np.mean(rates)) if rates else 0.0

    # Compute new green duration
    green_dur = _compute_green(total_vehicles, avg_rate)

    now = traci.simulation.getTime()
    _log_queue(now, lanes)
    _log_phase(now, tls_id, phase, green_dur, total_vehicles)

    log.debug(
        "Fuzzy %s phase %d → vehicles=%d, rate=%.3f → green=%ds",
        tls_id, phase, total_vehicles, avg_rate, green_dur,
    )
    # print(
    #     f"Fuzzy {tls_id} phase {phase} → vehicles={total_vehicles}, rate={avg_rate} → green={green_dur}s"
    # )
    return green_dur
