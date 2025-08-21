# src/fuzzylts/sim/runner.py
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SUMO Runner — single-simulation wrapper using TraCI.

Provides a uniform interface to run SUMO with different traffic-light controllers
(`static`, `actuated`, `fuzzy`, `gap_fuzzy`) and collect output files.

Pipeline
--------
1) Resolve SUMO binary and validate inputs.
2) Expose the network path to controllers via `TARGET_NET_XML` env var.
3) Lazily load the requested controller module (see `fuzzylts.controllers`).
4) Optionally preprocess the network (controller-specific, idempotent).
5) Start SUMO with CLI overrides for outputs and reproducibility.
6) In the main loop:
   - Let the controller compute a (possibly new) phase duration.
   - For fuzzy controllers, apply the duration **only when entering green**.
7) Close TraCI and return the output paths.

Returns
-------
A tuple `(tripinfo_xml, stats_xml)` with paths inside the provided output dir.
"""

from __future__ import annotations

import os
from pathlib import Path
from shutil import which
from typing import Tuple

import traci

from fuzzylts.controllers import get_controller  # lazy loader returns module
from fuzzylts.utils.log import get_logger

log = get_logger(__name__)

# Controllers read the network from this environment variable for reproducibility
_TARGET_NET_ENV = "TARGET_NET_XML"


# ─────────────────────────────────────────────────────────────────────────────
# Utilities
# ─────────────────────────────────────────────────────────────────────────────

def _resolve_sumo_binary(sumo_binary: str) -> str:
    """Resolve the SUMO executable from a given name ('sumo'/'sumo-gui') or path.

    Resolution order:
      1) If `sumo_binary` is a valid file path, return it.
      2) Search in PATH.
      3) Search in `$SUMO_HOME/bin`.

    Raises:
        FileNotFoundError if no executable is found.
    """
    # Absolute/relative path provided
    p = Path(sumo_binary)
    if p.exists():
        return str(p)

    # Try PATH
    found = which(sumo_binary)
    if found:
        return found

    # Try $SUMO_HOME/bin
    sumo_home = os.environ.get("SUMO_HOME")
    if sumo_home:
        candidate = Path(sumo_home) / "bin" / sumo_binary
        if candidate.exists():
            return str(candidate)

    raise FileNotFoundError(f"SUMO binary '{sumo_binary}' not found in PATH or $SUMO_HOME/bin")


def _ensure_file(path: Path, label: str) -> None:
    """Raise if `path` does not exist."""
    if not path.exists():
        raise FileNotFoundError(f"{label} not found: {path}")


def _phase_is_green(state: str) -> bool:
    """Heuristic: treat any 'g' or 'G' in the state string as a green phase."""
    return any(c in "gG" for c in state)


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def run_sumo_once(
    sumo_binary: str,
    controller_name: str,
    net_xml: Path,
    routes_xml: Path,
    sumocfg: Path,
    output_dir: Path,
    sim_seed: int = 0,
    step_length: float = 1.0,
) -> Tuple[Path, Path]:
    """Execute a single SUMO simulation and return the main output files.

    Parameters
    ----------
    sumo_binary : str
        'sumo' | 'sumo-gui' | absolute path to the executable.
    controller_name : str
        One of {'static', 'actuated', 'fuzzy', 'gap_fuzzy'}.
    net_xml : Path
        Network file (.net.xml[.gz]).
    routes_xml : Path
        Route definitions (.rou.xml).
    sumocfg : Path
        Base configuration (.sumocfg). CLI flags below will override it.
    output_dir : Path
        Directory to write tripinfo.xml, stats.xml, emissions.xml.
    sim_seed : int
        Random seed for reproducibility.
    step_length : float
        Simulation step length in seconds.

    Returns
    -------
    (tripinfo_xml, stats_xml) : tuple[Path, Path]
    """
    # Validate inputs early
    _ensure_file(net_xml, "Network XML")
    _ensure_file(routes_xml, "Routes XML")
    _ensure_file(sumocfg, "SUMO config")
    sumo_exec = _resolve_sumo_binary(sumo_binary)

    # Prepare outputs
    output_dir.mkdir(parents=True, exist_ok=True)
    tripinfo_xml = output_dir / "tripinfo.xml"
    stats_xml = output_dir / "stats.xml"
    emissions_xml = output_dir / "emissions.xml"

    # Make the network path available to controller configs (deterministic loading)
    os.environ[_TARGET_NET_ENV] = str(net_xml)

    # Lazily load controller module (must expose preprocess_network, initialize_tls, get_phase_duration)
    controller = get_controller(controller_name)

    # Controller-specific preprocessing (idempotent; no-op for some controllers)
    net_xml = controller.preprocess_network(net_xml, force=False)

    # Build SUMO command (CLI overrides sumocfg fields)
    sumo_cmd = [
        sumo_exec,
        "-c", str(sumocfg),
        "--net-file", str(net_xml),
        "--route-files", str(routes_xml),
        "--seed", str(sim_seed),
        "--step-length", str(step_length),

        # Outputs
        "--tripinfo-output", str(tripinfo_xml),
        "--statistic-output", str(stats_xml),
        "--emission-output", str(emissions_xml),

        # Run behavior
        "--start",
        "--quit-on-end",

        # Reactive, stable re-routing
        "--device.rerouting.probability", "0.7",
        "--device.rerouting.period", "30",
        "--device.rerouting.pre-period", "90",
        "--device.rerouting.adaptation-interval", "5",
        "--device.rerouting.adaptation-steps", "24",
        "--weights.random-factor", "1.15",  # diversify routes; improve routing performance

        "--max-depart-delay", "-1",

        # Teleports (debug: do not hide gridlock)
        "--time-to-teleport", "-1",
        "--time-to-teleport.disconnected", "300",
        "--time-to-teleport.bidi", "60",

        # Collisions: warn and continue
        "--collision.action", "warn",

        # Emissions every 15 min (900 s)
        "--device.emissions.period", "900",

        # IMPORTANT: adjust by network capacity if needed
        "--max-num-vehicles", "5000",
    ]

    log.info("Starting SUMO (%s) with controller=%s", sumo_binary, controller_name)
    log.debug("Command: %s", " ".join(sumo_cmd))

    # Start simulation
    traci.start(sumo_cmd)

    try:
        # TLS bootstrap
        tls_ids = list(traci.trafficlight.getIDList())
        is_fuzzy = controller_name in {"fuzzy", "gap_fuzzy"}
        controller.initialize_tls()

        # Track previous phase to detect green entries
        prev_phase = {tls: traci.trafficlight.getPhase(tls) for tls in tls_ids}

        # Main loop
        while traci.simulation.getMinExpectedNumber() > 0:
            # If you want to limit the simulated time for analysis experiments:
            # while traci.simulation.getTime() < 3600 * 4:
            traci.simulationStep()

            for tls in tls_ids:
                current_phase = traci.trafficlight.getPhase(tls)
                current_state = traci.trafficlight.getRedYellowGreenState(tls)

                # Always let the controller compute (and possibly log) the duration
                green_duration = controller.get_phase_duration(tls)

                # For fuzzy-family controllers, apply the duration only on green-phase entry
                if is_fuzzy and _phase_is_green(current_state) and current_phase != prev_phase[tls]:
                    if green_duration > 0:  # ignore zero
                        traci.trafficlight.setPhaseDuration(tls, green_duration)

                prev_phase[tls] = current_phase

    finally:
        # Ensure clean shutdown even on exceptions
        try:
            traci.close()
        except Exception as e:  # pragma: no cover (best-effort)
            log.warning("TraCI close raised: %s", e)

    # Best-effort cleanup of temp configs (if caller used a temp file)
    if sumocfg.name.startswith("_temp_") and sumocfg.exists():
        try:
            sumocfg.unlink()
            log.debug("Removed temporary config: %s", sumocfg)
        except OSError as e:
            log.warning("Failed to delete temp config %s: %s", sumocfg, e)

    log.info("Simulation finished. Outputs: %s, %s", tripinfo_xml, stats_xml)
    return tripinfo_xml, stats_xml


__all__ = ["run_sumo_once"]
