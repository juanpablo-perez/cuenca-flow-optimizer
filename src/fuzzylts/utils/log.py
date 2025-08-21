# src/fuzzylts/utils/log.py
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Logging and reporting utilities for fuzzylts.

Provides:
    - `get_logger(name, level)`: standardized logger configuration
    - `print_phase_limits(phase_lanes, lane_limits)`: report per-TLS (phases 0 & 2)
      aggregations over lane metrics
    - `print_global_limits(lane_limits)`: report overall min/max metrics across lanes

Notes
-----
- Output of the *print_* helpers is intended for human-readable console reports.
- This module purposely mixes English docstrings with Spanish metric keys
  (e.g., `vehiculos_max`) to remain compatible with upstream data producers.
"""

from __future__ import annotations

import logging
import sys
from typing import Any, Dict, List

# ─────────────────────────────────────────────────────────────────────────────
# Log formatting
# ─────────────────────────────────────────────────────────────────────────────

_LOG_FORMAT: str = "%(asctime)s | %(levelname)-8s | %(name)s: %(message)s"
_DATE_FORMAT: str = "%Y-%m-%d %H:%M:%S"


def get_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """Return a configured `logging.Logger` with a consistent format.

    The logger:
      - Writes to `stdout` via a single `StreamHandler`.
      - Uses a unified timestamped format across the project.
      - Does not propagate to ancestor loggers (avoids duplicate lines).

    Args:
        name: Logger name to create/retrieve.
        level: Initial log level (e.g., `logging.INFO`).

    Returns:
        A configured `logging.Logger` instance.
    """
    logger = logging.getLogger(name)

    # If already configured, return as-is (prevents duplicate handlers).
    if logger.handlers:
        return logger

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT))

    logger.addHandler(handler)
    logger.setLevel(level)
    logger.propagate = False
    return logger


# ─────────────────────────────────────────────────────────────────────────────
# Console reporting helpers
# ─────────────────────────────────────────────────────────────────────────────

def print_phase_limits(
    phase_lanes: Dict[str, Dict[int, List[str]]],
    lane_limits: Dict[str, Dict[str, Any]],
) -> None:
    """Print summarized metrics for each traffic light and its green phases (0 & 2).

    Aggregation per (tls_id, phase):
      - Sum of vehicle/movement counts across mapped lanes.
      - Average of speed and arrival rate across mapped lanes.

    Args:
        phase_lanes: Mapping of `tls_id -> {phase_index -> [lane_id, ...]}`.
        lane_limits: Mapping of `lane_id -> metrics dict` with keys:
            'vehiculos_max', 'movimiento_max', 'detenidos_max',
            'velocidad_prom_max', 'tasa_llegada_max'.
    """
    print("=== PER-TRAFFIC-LIGHT PHASE LIMITS (sum counts, average speed & arrival rate) ===")
    for tls_id, phases in phase_lanes.items():
        print(f"\n Traffic light: {tls_id}")
        for phase in (0, 2):
            lanes = phases.get(phase, [])
            if not lanes:
                print(f"  Phase {phase}: no lanes defined.")
                continue

            totals = {
                "vehicles": 0,
                "moving": 0,
                "stopped": 0,
                "speed_sum": 0.0,
                "arrival_sum": 0.0,
                "count": 0,
            }

            for lane_id in lanes:
                limits = lane_limits.get(lane_id)
                if not limits:
                    continue
                # Keep original Spanish keys to preserve upstream schema.
                totals["vehicles"] += limits["vehiculos_max"]
                totals["moving"] += limits["movimiento_max"]
                totals["stopped"] += limits["detenidos_max"]
                totals["speed_sum"] += limits["velocidad_prom_max"]
                totals["arrival_sum"] += limits["tasa_llegada_max"]
                totals["count"] += 1

            if totals["count"] > 0:
                avg_speed = totals["speed_sum"] / totals["count"]
                avg_arrival = totals["arrival_sum"] / totals["count"]
            else:
                avg_speed = 0.0
                avg_arrival = 0.0

            print(f"  Phase {phase}:")
            print(f"    Vehicles     : {totals['vehicles']}")
            print(f"    Moving       : {totals['moving']}")
            print(f"    Stopped      : {totals['stopped']}")
            print(f"    Avg Speed    : {avg_speed:.2f} m/s")
            print(f"    Avg Arrival  : {avg_arrival:.3f} veh/s")


def print_global_limits(lane_limits: Dict[str, Dict[str, Any]]) -> None:
    """Print overall min/max metrics aggregated across all lanes.

    Expected keys in each lane's dict:
        'vehiculos_min', 'vehiculos_max',
        'movimiento_min', 'movimiento_max',
        'detenidos_min', 'detenidos_max',
        'velocidad_prom_min', 'velocidad_prom_max',
        'tasa_llegada_min', 'tasa_llegada_max'

    Args:
        lane_limits: Mapping of `lane_id -> metrics dict`.
    """
    metrics = {
        "veh_min": float("inf"),
        "veh_max": float("-inf"),
        "mov_min": float("inf"),
        "mov_max": float("-inf"),
        "stp_min": float("inf"),
        "stp_max": float("-inf"),
        "spd_min": float("inf"),
        "spd_max": float("-inf"),
        "arr_min": float("inf"),
        "arr_max": float("-inf"),
    }

    for limits in lane_limits.values():
        metrics["veh_min"] = min(metrics["veh_min"], limits["vehiculos_min"])
        metrics["veh_max"] = max(metrics["veh_max"], limits["vehiculos_max"])
        metrics["mov_min"] = min(metrics["mov_min"], limits["movimiento_min"])
        metrics["mov_max"] = max(metrics["mov_max"], limits["movimiento_max"])
        metrics["stp_min"] = min(metrics["stp_min"], limits["detenidos_min"])
        metrics["stp_max"] = max(metrics["stp_max"], limits["detenidos_max"])
        metrics["spd_min"] = min(metrics["spd_min"], limits["velocidad_prom_min"])
        metrics["spd_max"] = max(metrics["spd_max"], limits["velocidad_prom_max"])
        metrics["arr_min"] = min(metrics["arr_min"], limits["tasa_llegada_min"])
        metrics["arr_max"] = max(metrics["arr_max"], limits["tasa_llegada_max"])

    print("=== GLOBAL LIMITS ===")
    print(f"  Vehicles    : {metrics['veh_min']} → {metrics['veh_max']}")
    print(f"  Moving      : {metrics['mov_min']} → {metrics['mov_max']}")
    print(f"  Stopped     : {metrics['stp_min']} → {metrics['stp_max']}")
    print(f"  Avg Speed   : {metrics['spd_min']:.2f} → {metrics['spd_max']:.2f} m/s")
    print(f"  Avg Arrival : {metrics['arr_min']:.3f} → {metrics['arr_max']:.3f} veh/s")


__all__ = ["get_logger", "print_phase_limits", "print_global_limits"]
