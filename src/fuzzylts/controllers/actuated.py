# src/fuzzylts/controllers/actuated.py

"""
controllers.actuated – observer mode
──────────────────────────────────────────
Does not modify signal durations. Records green phases (0 & 2) to CSV
`datos_semaforos_actuated.csv` under the experiment run directory.
"""

from __future__ import annotations
import csv
import statistics
import os
import atexit
from pathlib import Path
from typing import Dict, List

import traci

from fuzzylts.utils.log import get_logger

log = get_logger(__name__)

# ── Configuration ─────────────────────────────────────────────────────────
TLS_IDS: List[str] = [
    "2496228891",
    "cluster_12013799525_12013799526_2496228894",
    "cluster_12013799527_12013799528_2190601967",
    "cluster_12013799529_12013799530_473195061",
]

PHASE_LANES_MAP: Dict[str, Dict[int, List[str]]] = {
    "2496228891": {
        0: [
            "337277951#3_0", "337277951#3_1", "337277951#1_0",
            "337277951#1_1", "337277951#4_0", "337277951#4_1",
            "337277951#2_0", "337277951#2_1", "49217102_0",
        ],
        2: ["567060342#1_0", "567060342#0_0"],
    },
    "cluster_12013799525_12013799526_2496228894": {
        0: ["42143912#5_0", "42143912#3_0", "42143912#4_0"],
        2: [
            "337277973#1_0", "337277973#1_1", "337277973#0_1",
            "337277973#0_0", "567060342#1_0", "567060342#0_0",
        ],
    },
    "cluster_12013799527_12013799528_2190601967": {
        0: ["40668087#1_0"],
        2: [
            "337277981#1_1", "337277981#1_0", "337277981#2_1",
            "337277981#2_0", "42143912#5_0", "42143912#3_0",
            "42143912#4_0",
        ],
    },
    "cluster_12013799529_12013799530_473195061": {
        0: ["49217102_0"],
        2: ["337277970#1_0", "337277970#1_1", "40668087#1_0"],
    },
}

RUN_DIR: Path = Path(os.getenv("FUZZYLTS_RUN_DIR", "."))
CSV_PATH: Path = RUN_DIR / "datos_semaforos_actuated.csv"

# ── Internal state ───────────────────────────────────────────────────────
_tls_state: Dict[str, Dict[str, int]] = {
    tls: {"phase": -1, "start_time": 0} for tls in TLS_IDS
}
_phase_records: List[Dict] = []
_min_green: int = float("inf")
_max_green: int = float("-inf")


def _record_phase(
    tls_id: str, phase: int, duration: int, vehicles: int, start_time: int
) -> None:
    """Append a completed green phase to the internal record."""
    global _min_green, _max_green
    entry = {
        "time": traci.simulation.getTime() - duration,
        "traffic_light_id": tls_id,
        "phase": phase,
        "duration": duration,
        "vehicle_count": vehicles,
        "start_step": start_time,
    }
    _phase_records.append(entry)
    _min_green = min(_min_green, duration)
    _max_green = max(_max_green, duration)


def get_phase_duration(tls_id: str) -> int:
    """
    Observer for SUMO-actuated mode. Always returns 0 (no modification).
    Records elapsed green-phase durations (phases 0 and 2).
    """
    current_step = int(traci.simulation.getCurrentTime() / 1000)
    phase = traci.trafficlight.getPhase(tls_id)
    prev = _tls_state[tls_id]

    # If previous phase was green (0 or 2), record it
    if prev["phase"] in (0, 2):
        duration = current_step - prev["start_time"]
        lanes = PHASE_LANES_MAP[tls_id][prev["phase"]]
        vehicle_count = sum(
            traci.lane.getLastStepVehicleNumber(l) for l in lanes
        )
        _record_phase(tls_id, prev["phase"], duration, vehicle_count, prev["start_time"])

    # Update state for the new phase
    prev["phase"] = phase
    prev["start_time"] = current_step

    return 0


@atexit.register
def _write_csv() -> None:
    """Write recorded green-phase data to CSV on program exit."""
    if not _phase_records:
        return

    CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CSV_PATH.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=_phase_records[0].keys())
        writer.writeheader()
        writer.writerows(_phase_records)

    durations = [r["duration"] for r in _phase_records]
    mean = statistics.mean(durations)
    var = statistics.variance(durations) if len(durations) > 1 else 0
    try:
        mode = statistics.mode(durations)
    except statistics.StatisticsError:
        mode = "No unique"

    log.info(
        "Actuated-observer summary – min:%ds, max:%ds, mean:%.2fs, mode:%s, var:%.2f",
        _min_green, _max_green, mean, mode, var
    )
