# src/fuzzylts/controllers/gap_fuzzy.py
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gap–Actuated + Fuzzy traffic-light controller for SUMO/TraCI.

Logic
-----
Interrupt (gap-out) the current green phase if BOTH conditions hold:
  1) the green has lasted at least `MIN_GREEN` seconds, and
  2) no vehicles have been detected for `NO_VEHICLE_LIMIT` consecutive seconds.

Otherwise, delegate green extension to the fuzzy controller.

Public API (controller protocol)
--------------------------------
- get_phase_duration(tls_id): int
- initialize_tls(): None
- preprocess_network(path): Path

Notes
-----
- Green phases are detected from the binary state string: presence of 'g' or 'G'.
- This controller shares the **phase → lanes** mapping already loaded by the
  fuzzy controller configuration.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import DefaultDict, Final

import traci

# Keep imports aligned with your existing package layout.
from fuzzylts.controllers import fuzzy  # type: ignore
from fuzzylts.controllers import static  # type: ignore
from fuzzylts.utils.log import get_logger  # type: ignore

__all__ = ["get_phase_duration", "initialize_tls", "preprocess_network"]

log = get_logger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Type aliases
# ─────────────────────────────────────────────────────────────────────────────

TLSId = str

# ─────────────────────────────────────────────────────────────────────────────
# Tunables (seconds)
# ─────────────────────────────────────────────────────────────────────────────

MIN_GREEN: Final[float] = 2            # minimum green time before a potential gap-out
NO_VEHICLE_LIMIT: Final[float] = 2     # consecutive seconds with no vehicles to trigger gap-out

# ─────────────────────────────────────────────────────────────────────────────
# Internal state (per TLS)
# ─────────────────────────────────────────────────────────────────────────────
# Track dwell times since green started and since last vehicle was seen.
_empty_time: DefaultDict[TLSId, float] = defaultdict(float)  # seconds with zero vehicles
_green_time: DefaultDict[TLSId, float] = defaultdict(float)  # seconds since green started


def _reset_timers(tls_id: TLSId) -> None:
    """Reset per-TLS timers (green dwell and empty-lane dwell)."""
    _empty_time[tls_id] = 0.0
    _green_time[tls_id] = 0.0


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────
def _phase_is_green(state: str) -> bool:
    """Heuristic: treat any 'g' or 'G' in the state string as a green phase."""
    return any(c in "gG" for c in state)


def _gap_fuzzy(tls_id: TLSId) -> int:
    """Apply gap-out logic; otherwise delegate to the fuzzy controller.

    Returns the suggested green extension (seconds) when the TLS is in a **green**
    phase; returns 0 for non-green phases. The runner applies the duration only
    upon entering green phases (so returning 0 outside green is expected).
    """
    phase = traci.trafficlight.getPhase(tls_id)
    phase_state = traci.trafficlight.getRedYellowGreenState(tls_id)

    # Only operate on green phases; reset timers for others (yellow/red).
    if not _phase_is_green(state=phase_state):
        _reset_timers(tls_id)
        return 0

    # Lanes mapped to the current phase (shared mapping from fuzzy controller config).
    try:
        lanes = fuzzy.cfg.phase_lanes[tls_id][phase]
    except KeyError:
        # No mapping available → nothing to do here; reset for safety.
        _reset_timers(tls_id)
        return 0

    # Aggregate vehicle count across mapped lanes for the current step.
    vehs = sum(int(traci.lane.getLastStepVehicleNumber(l)) for l in lanes)

    # Advance timers using SUMO's deltaT (robust to non-1.0 step lengths).
    dt = float(traci.simulation.getDeltaT())
    _green_time[tls_id] += dt
    _empty_time[tls_id] = (_empty_time[tls_id] + dt) if vehs == 0 else 0.0

    # Gap-out: enough green elapsed AND no vehicles for a while.
    if _green_time[tls_id] >= MIN_GREEN and _empty_time[tls_id] >= NO_VEHICLE_LIMIT:
        try:
            num_phases = int(traci.trafficlight.getPhaseNumber(tls_id))
        except Exception:
            # Fallback: derive from the active program definition.
            logic = traci.trafficlight.getAllProgramLogics(tls_id)[0]
            num_phases = len(logic.getPhases())

        next_phase = (phase + 1) % num_phases
        traci.trafficlight.setPhase(tls_id, next_phase)

        log.debug(
            "[%s] Gap-out: %d → %d | empty=%.2fs green=%.2fs",
            tls_id, phase, next_phase, _empty_time[tls_id], _green_time[tls_id],
        )

        _reset_timers(tls_id)
        return 0  # Value ignored by runner outside green entry.

    # No gap-out: delegate the green-duration decision to the fuzzy controller.
    return fuzzy.get_phase_duration(tls_id)


# ─────────────────────────────────────────────────────────────────────────────
# Public API (controller protocol)
# ─────────────────────────────────────────────────────────────────────────────
def get_phase_duration(tls_id: TLSId) -> int:
    """Return the suggested green duration (seconds) for `tls_id`."""
    return _gap_fuzzy(tls_id)


def initialize_tls() -> None:
    """No TLS pre-initialization required (kept for protocol compatibility)."""
    return None  # no-op


def preprocess_network(path: Path, *, out_name: str | None = None, force: bool = False) -> Path:
    """Build (or reuse) the static-controller network (no special preprocessing needed)."""
    return static.preprocess_network(path=path, out_name=out_name, force=force)
