# src/fuzzylts/sim/runner.py

"""
SUMO Runner – Single simulation wrapper using TraCI

Provides a uniform interface to run SUMO with different traffic-light controllers
(static, actuated, fuzzy) and collect output files.
"""
from __future__ import annotations
import os
from pathlib import Path

import traci

from fuzzylts.controllers import get_controller
from fuzzylts.utils.log import get_logger

log = get_logger(__name__)


def run_sumo_once(
    sumo_binary: str,
    controller: str,
    routes_xml: Path,
    sumocfg: Path,
    output_dir: Path,
    sim_seed: int = 0,
    step_length: float = 1.0,
) -> tuple[Path, Path]:
    """
    Execute a single SUMO simulation and return paths to the generated output.

    Args:
        controller: Name of the controller ('static', 'actuated', 'fuzzy').
        routes_xml: Path to the .rou.xml file with route definitions.
        sumocfg:    Path to the base .sumocfg file (will be overridden).
        output_dir: Directory where tripinfo.xml and stats.xml will be written.
        sim_seed:   Random seed for reproducibility.
        step_length: Simulation step length in seconds.

    Returns:
        A tuple (tripinfo_xml, stats_xml).
    """
    # Prepare output directory
    output_dir.mkdir(parents=True, exist_ok=True)
    tripinfo_xml = output_dir / "tripinfo.xml"
    stats_xml = output_dir / "stats.xml"
    emissions_xml = output_dir / "emissions.xml"

    # Build SUMO command
    sumo_cmd = [
        sumo_binary,
        "-c", str(sumocfg),
        "--seed", str(sim_seed),
        "--route-files", str(routes_xml),
        "--tripinfo-output", str(tripinfo_xml),
        "--statistic-output", str(stats_xml),
        "--emission-output", str(emissions_xml),
        "--step-length", str(step_length),
        "--start",
        "--quit-on-end",
    ]
    log.info("Starting SUMO: %s", " ".join(sumo_cmd))
    traci.start(sumo_cmd)

    # Lazy-load controller function
    controller_fn = get_controller(controller)
    tls_ids = traci.trafficlight.getIDList()
    is_fuzzy =  controller in  ["fuzzy", "gap_fuzzy"] 

    # Track previous phase to detect green-phase entry
    prev_phase: dict[str, int] = {tls: traci.trafficlight.getPhase(tls) for tls in tls_ids}

    # Simulation loop
    while traci.simulation.getMinExpectedNumber() > 0:
        traci.simulationStep()
        for tls in tls_ids:
            current_phase = traci.trafficlight.getPhase(tls)
            # Always invoke controller to allow logging side-effects
            green_duration = controller_fn(tls)

            # For fuzzy controller, override phase duration at green entry
            if is_fuzzy and current_phase in (0, 2) and current_phase != prev_phase[tls]:
                traci.trafficlight.setPhaseDuration(tls, green_duration)

            prev_phase[tls] = current_phase

    # Clean up TraCI
    traci.close(False)

    # Remove temporary sumocfg if generated
    if sumocfg.name.startswith("_temp_") and sumocfg.exists():
        try:
            sumocfg.unlink()
            log.debug("Removed temporary config: %s", sumocfg)
        except OSError as e:
            log.warning("Failed to delete temp config %s: %s", sumocfg, e)

    return tripinfo_xml, stats_xml
