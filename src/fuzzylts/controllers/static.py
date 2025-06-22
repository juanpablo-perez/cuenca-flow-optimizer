# src/fuzzylts/controllers/static.py

"""
controllers.static – Static signal control (no override)
───────────────────────────────────────────────────────────────
This “static” controller never intervenes in SUMO’s timing:
returning zero tells the runner to leave the phase duration as defined
in the network/.sumocfg file.
"""

from __future__ import annotations

def get_phase_duration(tls_id: str) -> int:
    """
    Called by the runner at each simulation step.

    Args:
        tls_id: Traffic-light system ID (unused in static mode).

    Returns:
        0, to signal no override of the current phase duration.
    """
    return 0
