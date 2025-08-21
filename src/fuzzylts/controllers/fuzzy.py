# src/fuzzylts/controllers/fuzzy.py
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fuzzy TLS Controller utilities for SUMO/TraCI.

Builds a scikit-fuzzy control system once and exposes a minimal controller API:

- `get_phase_duration(tls_id)`:
    Returns the suggested green time (seconds) when the TLS is in a **green** phase.
    (By convention, green phases are those whose state string contains 'g' or 'G'.)
- `initialize_tls()`:
    No-op (provided for interface compatibility with other controllers).
- `preprocess_network(path)`:
    Delegates to the static controller's network preprocessor (no-op for topology).

Fuzzy system I/O
----------------
Inputs:
  - **vehicles**: number of vehicles across lanes mapped to the active phase.
  - **arrival** : estimated arrival rate (veh/s) via finite differencing.
Output:
  - **green**   : suggested green duration (seconds).

Notes
-----
- Green phases are detected when the phase state string contains `'g'` or `'G'`.
- This module assumes the **network → lanes per phase** mapping is available
  via the fuzzy configuration (derived from the SUMO network).
"""

from __future__ import annotations

import os
from math import isfinite
from pathlib import Path
from typing import Final, Dict, Tuple

import numpy as np
import traci
from skfuzzy import control as ctrl

# Keep imports consistent with the existing codebase layout.
from fuzzylts.config.fuzzy_config import FuzzyConfig  # type: ignore
from fuzzylts.utils.fuzzy_system import generate_memberships, build_rules  # type: ignore
from fuzzylts.controllers import static  # type: ignore
from fuzzylts.utils.log import get_logger  # type: ignore

log = get_logger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Type aliases
# ─────────────────────────────────────────────────────────────────────────────

TLSId = str
LaneId = str

# ─────────────────────────────────────────────────────────────────────────────
# Constants / configuration
# ─────────────────────────────────────────────────────────────────────────────

NET_ENV_VAR: Final[str] = "TARGET_NET_XML"  # injected by the runner
RUN_DIR: Final[Path] = Path(os.getenv("FUZZYLTS_RUN_DIR", ".")).resolve()

# Numerics
EPS_TIME: Final[float] = 1e-3          # protect against Δt → 0
SMALL_QUEUE_THRESHOLD: Final[int] = 3  # use lower bound when queue is small

# ─────────────────────────────────────────────────────────────────────────────
# Load configuration (membership functions + rules + phase→lanes mapping)
# ─────────────────────────────────────────────────────────────────────────────

_net_path_env: str | None = os.getenv(NET_ENV_VAR)
# The config loader is expected to handle None or string paths accordingly.
cfg = FuzzyConfig.load(net_path=_net_path_env)  # type: ignore[arg-type]

# Validate required membership sets exist
for required in ("vehicles", "arrival", "green"):
    if required not in cfg.functions:
        raise KeyError(f"Missing fuzzy membership set '{required}' in config")

# ─────────────────────────────────────────────────────────────────────────────
# Build fuzzy system (one-time)
# ─────────────────────────────────────────────────────────────────────────────

_vars = generate_memberships(cfg.functions)
_rules = build_rules(cfg.rules, _vars["vehicles"], _vars["arrival"], _vars["green"])
_fuzzy_system = ctrl.ControlSystem(_rules)
_sim = ctrl.ControlSystemSimulation(_fuzzy_system)

# Cache green bounds for clamping
_green_lo = float(cfg.functions["green"].lmin)
_green_hi = float(getattr(cfg.functions["green"], "lmax", _green_lo))

log.info("Fuzzy controller initialized with %d rules", len(_rules))

# ─────────────────────────────────────────────────────────────────────────────
# Per-lane state for arrival-rate estimation
# lane_id -> (last_time, last_count)
# ─────────────────────────────────────────────────────────────────────────────

_lane_state: Dict[LaneId, Tuple[float, int]] = {}


def _queue_and_rate(lane: LaneId) -> Tuple[int, float]:
    """Return (queue_length, arrival_rate) and update internal state.

    The arrival rate is computed as Δ(count) / Δ(time) with Δ(time) clamped
    below by EPS_TIME to avoid division by zero.
    """
    now = traci.simulation.getTime()
    count = int(traci.lane.getLastStepVehicleNumber(lane))
    prev_time, prev_count = _lane_state.get(lane, (now, count))
    dt = max(now - prev_time, EPS_TIME)
    rate = (count - prev_count) / dt
    _lane_state[lane] = (now, count)
    return count, max(float(rate), 0.0)


# ─────────────────────────────────────────────────────────────────────────────
# Fuzzy inference core
# ─────────────────────────────────────────────────────────────────────────────

def _clamp(v: float, lo: float, hi: float) -> float:
    """Clamp value `v` to the closed interval [lo, hi]."""
    return hi if v > hi else lo if v < lo else v


def _compute_green(vehicles: int, rate: float) -> int:
    """Evaluate the fuzzy system to produce a green duration (seconds).

    Logic:
    - Apply a conservative lower bound when the queue is small.
    - Reset the scikit-fuzzy simulation to avoid residual state between steps.
    - Clamp the result to configured bounds and round to the nearest integer.
    """
    if vehicles <= SMALL_QUEUE_THRESHOLD:
        return int(_green_lo)

    _sim.reset()
    _sim.input["vehicles"] = float(vehicles)
    _sim.input["arrival"] = float(rate)

    try:
        _sim.compute()
        value = float(_sim.output["green"])
    except Exception as e:  # scikit-fuzzy may raise on invalid inputs/rules
        log.error("Fuzzy inference failed (vehicles=%s, rate=%.3f): %s", vehicles, rate, e)
        value = _green_lo

    value = _clamp(value if isfinite(value) else _green_lo, _green_lo, _green_hi)
    return int(round(value))


# ─────────────────────────────────────────────────────────────────────────────
# Helpers: phase classification
# ─────────────────────────────────────────────────────────────────────────────

def _phase_is_green(state: str) -> bool:
    """Heuristic: green phases contain at least one of 'g' or 'G' in `state`."""
    return any(c in "gG" for c in state)


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def get_phase_duration(tls_id: TLSId) -> int:
    """Return a suggested green duration (seconds) for the current phase.

    Called on every simulation step. If the TLS is **not** in a green phase,
    return 0 (ignored by the runner).

    Args:
        tls_id: Traffic light system identifier from the SUMO network.

    Returns:
        Integer green duration in seconds (0 if not in green).
    """
    phase = traci.trafficlight.getPhase(tls_id)
    phase_state = traci.trafficlight.getRedYellowGreenState(tls_id)
    if not _phase_is_green(state=phase_state):
        return 0

    # Fetch lanes mapped to the current phase; handle missing mappings gracefully.
    try:
        lanes = cfg.phase_lanes[tls_id][phase]
    except KeyError:
        # log.warning("No lanes mapped for tls='%s' phase=%d; returning 0", tls_id, phase)
        return 0

    total_vehicles = 0
    rates: list[float] = []
    for lane in lanes:
        q, r = _queue_and_rate(lane)
        total_vehicles += q
        if r > 0:
            rates.append(r)

    avg_rate = float(np.mean(rates)) if rates else 0.0
    green_dur = _compute_green(total_vehicles, avg_rate)

    # Keep the following line for parity with the original code path (time capture).
    _ = traci.simulation.getTime()

    log.debug(
        "Fuzzy %s phase=%d | vehicles=%d, rate=%.3f -> green=%ds",
        tls_id, phase, total_vehicles, avg_rate, green_dur,
    )
    return green_dur


def initialize_tls() -> None:
    """No TLS pre-initialization needed for the fuzzy controller (no-op)."""
    return None  # explicit no-op for interface compatibility


def preprocess_network(path: Path, *, out_name: str | None = None, force: bool = False) -> Path:
    """Delegate to the static controller's network preprocessor (no topology changes)."""
    return static.preprocess_network(path=path, out_name=out_name, force=force)


__all__ = [
    "get_phase_duration",
    "initialize_tls",
    "preprocess_network",
]
