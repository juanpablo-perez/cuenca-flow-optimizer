"""
controllers.fuzzy – controlador difuso con CSV integrado
─────────────────────────────────────────────────────────
• Aplica las mismas reglas y membresías que tu script original.
• Calcula duración verde cada vez que una fase 0/2 entra en amarillo.
• Registra:
      datos_colas_fuzzy.csv
      datos_semaforos_fuzzy.csv
  en la carpeta del experimento (FUZZYLTS_RUN_DIR).
"""
from __future__ import annotations
import csv, os, statistics
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import traci
from skfuzzy import control as ctrl

from fuzzylts.utils.fuzzy_system import generar_membresias_fuzzy, crear_reglas_desde_lista
from fuzzylts.utils.log import get_logger
from . import fuzzy_defs as defs                     # fases_lanes_dict, funciones, reglas_definidas

log = get_logger(__name__)

# ── construir sistema difuso una única vez ────────────────────────────────
_vars = generar_membresias_fuzzy(defs.funciones)
ctrl_system = ctrl.ControlSystem(crear_reglas_desde_lista(
    defs.reglas_definidas, _vars["vehiculos"], _vars["llegada"], _vars["verde"]
))
SIM = ctrl.ControlSystemSimulation(ctrl_system)
log.info("Fuzzy controller ready with %d rules", len(defs.reglas_definidas))

# ── CSV paths ────────────────────────────────────────────────────────────
RUN_DIR = Path(os.environ.get("FUZZYLTS_RUN_DIR", "."))
CSV_COLAS     = RUN_DIR / "datos_colas_fuzzy.csv"
CSV_SEMAFOROS = RUN_DIR / "datos_semaforos_fuzzy.csv"
def _init_csv(path: Path, header: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(header + "\n", encoding="utf-8")

_init_csv(CSV_COLAS,     "tiempo,lane_id,vehiculos_en_cola")
_init_csv(CSV_SEMAFOROS, "tiempo,semaforo_id,num_vehiculos,fase,duracion_verde")

# ── estado lane → (t_prev, count_prev) para tasa de llegada ───────────────
_lane_state: Dict[str, Tuple[float, int]] = {}

def _cola_y_tasa(lane: str) -> Tuple[int, float]:
    """Devuelve (vehículos en cola, tasa llegada) y actualiza el estado."""
    now   = traci.simulation.getTime()
    count = traci.lane.getLastStepVehicleNumber(lane)
    t_prev, c_prev = _lane_state.get(lane, (now, count))
    tasa = (count - c_prev) / max(now - t_prev, 1e-3)
    _lane_state[lane] = (now, count)
    return count, max(tasa, 0.0)


# ── helpers CSV ────────────────────────────────────────────────────────────
def _log_colas(t: float, lane_ids: List[str]) -> int:
    total = 0
    with CSV_COLAS.open("a", newline="") as f:
        w = csv.writer(f)
        for lane in lane_ids:
            cnt = traci.lane.getLastStepVehicleNumber(lane)
            w.writerow([t, lane, cnt])
            total += cnt
    return total

def _log_semaforo(t: float, tls: str, fase: int, verde: int, vehs: int) -> None:
    with CSV_SEMAFOROS.open("a", newline="") as f:
        csv.writer(f).writerow([t, tls, vehs, fase, verde])

# ── núcleo difuso ──────────────────────────────────────────────────────────
def _inferir_verde(veh: int, tasa: float) -> int:
    if veh <= 3:
        return int(defs.funciones["verde"]["lmin"])
    SIM.input["vehiculos"] = veh
    SIM.input["llegada"]   = tasa
    SIM.compute()
    return int(SIM.output["verde"])

# ── API principal ─────────────────────────────────────────────────────────
def get_phase_duration(tls_id: str) -> int:
    fase = traci.trafficlight.getPhase(tls_id)
    if fase not in (0, 2):                           # amarillo o rojo
        return 0                                     # no cambiamos

    lanes = defs.fases_lanes_dict[tls_id][fase]
    vehs, tasas = 0, []
    for lane in lanes:
        cnt, rate = _cola_y_tasa(lane)
        vehs += cnt
        if rate > 0:
            tasas.append(rate)

    tasa_avg = float(np.mean(tasas)) if tasas else 0.0
    verde    = _inferir_verde(vehs, tasa_avg)

    now = traci.simulation.getTime()
    _log_colas(now, lanes)
    _log_semaforo(now, tls_id, fase, verde, vehs)
    log.debug("Fuzzy %s f%d → veh=%d tasa=%.3f → verde=%ds",
              tls_id, fase, vehs, tasa_avg, verde)
    return verde
