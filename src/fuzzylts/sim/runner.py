"""Wrapper único para lanzar **una** simulación SUMO + TraCI."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import traci
import sumolib

from fuzzylts.controllers import get_controller
from fuzzylts.utils.log import get_logger

log = get_logger(__name__)


def run_sumo_once(
    controller: str,
    routes_xml: Path,
    sumocfg: Path,
    output_dir: Path,
    sim_seed: int = 0,
    step_length: float = 1.0,
) -> tuple[Path, Path]:
    """
    Corre SUMO hasta el final y devuelve `(tripinfo_xml, stats_xml)`.

    *Genera*:
        tripinfo.xml   – métricas vehículo-a-vehículo
        stats.xml      – resumen estadístico global de la simulación
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    tripinfo_xml = output_dir / "tripinfo.xml"
    stats_xml    = output_dir / "stats.xml"

    # Construir línea de comando SUMO
    sumo_cmd = [
        "sumo",
        "-c", str(sumocfg),
        "--seed", str(sim_seed),
        "--route-files", str(routes_xml),
        "--tripinfo-output", str(tripinfo_xml),
        "--statistic-output", str(stats_xml),
        "--step-length", str(step_length),
    ]
    log.info("Running SUMO: %s", " ".join(sumo_cmd))
    traci.start(sumo_cmd)

    # Importación perezosa del controlador
    ctl = get_controller(controller)
    tls_ids = traci.trafficlight.getIDList()
    is_fuzzy  = controller == "fuzzy"

    last_phase = {tls: traci.trafficlight.getPhase(tls) for tls in tls_ids}

    # Bucle principal de simulación
    while traci.simulation.getMinExpectedNumber() > 0:
        traci.simulationStep()
        for tls in tls_ids:
            phase_now = traci.trafficlight.getPhase(tls)
            dur = ctl(tls)                 # ➊ SIEMPRE se invoca ⇒ escribe CSV

            if is_fuzzy and phase_now in (0, 2) and phase_now != last_phase[tls]:
                traci.trafficlight.setPhaseDuration(tls, dur)

            last_phase[tls] = phase_now


    traci.close(False)
    
    # ── limpiar .sumocfg temporal ─────────────────────────────────────────
    if sumocfg.name.startswith("_temp_") and sumocfg.exists():
        try:
            sumocfg.unlink()
            log.debug("Temp cfg eliminado: %s", sumocfg)
        except OSError as e:
            log.warning("No se pudo borrar %s: %s", sumocfg, e)

    return tripinfo_xml, stats_xml
