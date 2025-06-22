# src/fuzzylts/utils/log.py

"""
Logging and reporting utilities for fuzzylts.

Provides:
  - get_logger: standardized logger configuration
  - print_phase_limits: report per-traffic-light and phase metrics
  - print_global_limits: report overall min/max metrics across all lanes
"""
from __future__ import annotations
import logging
import sys
from typing import Dict, List, Any

# Log format constants
_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s: %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def get_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """
    Return a configured Logger with a consistent format across the project.

    Args:
        name: Logger name.
        level: Logging level (e.g., logging.INFO).

    Returns:
        Configured Logger instance.
    """
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(level)
    logger.propagate = False
    return logger


def print_phase_limits(
    phase_lanes: Dict[str, Dict[int, List[str]]],
    lane_limits: Dict[str, Dict[str, Any]]
) -> None:
    """
    Print summarized metrics for each traffic light and its green phases (0 & 2).

    Args:
        phase_lanes: Mapping of tls_id to its phase-to-lanes mapping.
        lane_limits: Mapping of lane_id to its recorded min/max metrics.
    """
    print("=== PER-TRAFFIC-LIGHT PHASE LIMITS (sum counts, average speed & arrival rate) ===")
    for tls_id, phases in phase_lanes.items():
        print(f"\n📍 Traffic light: {tls_id}")
        for phase in (0, 2):
            lanes = phases.get(phase, [])
            if not lanes:
                print(f"  Phase {phase}: no lanes defined.")
                continue

            total = {
                "vehicles": 0,
                "moving": 0,
                "stopped": 0,
                "speed_sum": 0.0,
                "arrival_sum": 0.0,
                "count": 0
            }
            for lane_id in lanes:
                limits = lane_limits.get(lane_id)
                if not limits:
                    continue
                total["vehicles"] += limits["vehiculos_max"]
                total["moving"]   += limits["movimiento_max"]
                total["stopped"]  += limits["detenidos_max"]
                total["speed_sum"]   += limits["velocidad_prom_max"]
                total["arrival_sum"] += limits["tasa_llegada_max"]
                total["count"] += 1

            if total["count"] > 0:
                avg_speed = total["speed_sum"] / total["count"]
                avg_arrival = total["arrival_sum"] / total["count"]
            else:
                avg_speed = avg_arrival = 0.0

            print(f"  Phase {phase}:")
            print(f"    Vehicles     : {total['vehicles']}")
            print(f"    Moving       : {total['moving']}")
            print(f"    Stopped      : {total['stopped']}")
            print(f"    Avg Speed    : {avg_speed:.2f} m/s")
            print(f"    Avg Arrival  : {avg_arrival:.3f} veh/s")


def print_global_limits(lane_limits: Dict[str, Dict[str, Any]]) -> None:
    """
    Print overall min/max metrics aggregated across all lanes.

    Args:
        lane_limits: Mapping of lane_id to its recorded min/max metrics.
    """
    metrics = {
        "veh_min": float('inf'),
        "veh_max": float('-inf'),
        "mov_min": float('inf'),
        "mov_max": float('-inf'),
        "stp_min": float('inf'),
        "stp_max": float('-inf'),
        "spd_min": float('inf'),
        "spd_max": float('-inf'),
        "arr_min": float('inf'),
        "arr_max": float('-inf')
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
    print(f"  Avg Speed   : {metrics['spd_min']:.2f} → {metrics['spd_max']:.2f}")
    print(f"  Avg Arrival : {metrics['arr_min']:.3f} → {metrics['arr_max']:.3f}")
