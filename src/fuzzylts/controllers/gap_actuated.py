"""Gap-Actuated + Fuzzy traffic-light controller.

Interrumpe la fase verde si:
  • ya se cumplió un verde mínimo (`MIN_GREEN`) y
  • no se detectan vehículos durante `NO_VEHICLE_LIMIT` segundos
Pasos clave:
  1. Leemos vehículos por carril y actualizamos contadores.
  2. Si hay *gap-out* ⇒ forzamos `setPhase` al siguiente estado.
  3. En caso contrario delegamos la extensión al controlador difuso.

La función pública `gap_controller` mantiene la misma signatura que
espera `runner.py`.
"""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import DefaultDict

import traci
import os

from fuzzylts.config.fuzzy_config import FuzzyConfig
from fuzzylts.controllers import fuzzy
from fuzzylts.utils.log import get_logger

log = get_logger(__name__)

# ── Parámetros “mercado” ───────────────────────────────────────────────
NO_VEHICLE_LIMIT: float = 2.0   # s sin cola para cortar la fase
MIN_GREEN:        float = 2.0   # s de verde mínimo
STEP_LENGTH:      float = 1.0   # s – debe coincidir con --step-length

# ── Cargar la misma config que el difuso ─────────────────────────────
_cfg_path = os.getenv("FUZZYLTS_FUZZY_CONFIG")
if _cfg_path:
    cfg = FuzzyConfig.load(
        Path(_cfg_path)
        )
else:
    cfg = FuzzyConfig.load(
        Path(__file__).resolve().parents[3] / "configs/controller/fuzzy.yaml"
    )


# ── Estado interno ───────────────────────────────────────────────────
_empty_time: DefaultDict[str, float] = defaultdict(float)
_green_time: DefaultDict[str, float] = defaultdict(float)


def gap_controller(tls_id: str) -> int:
    """Aplicar control gap-actuated + difuso y devolver extensión de verde."""
    phase = traci.trafficlight.getPhase(tls_id)
    # lanes = cfg.phase_lanes[tls_id][phase]
    lanes_cfg = cfg.phase_lanes[tls_id]
    if phase not in lanes_cfg:
        # Reinicia contadores cuando entras en amarillos/rojos
        _empty_time[tls_id] = 0.0
        _green_time[tls_id] = 0.0
        return 0

    lanes = lanes_cfg[phase]
    vehs = sum(traci.lane.getLastStepVehicleNumber(l) for l in lanes)

    # 1 · Actualizar contadores
    if vehs == 0:
        _empty_time[tls_id] += STEP_LENGTH
    else:
        _empty_time[tls_id] = 0.0
    _green_time[tls_id] += STEP_LENGTH


    # 2 · Evaluar gap-out
    if (_green_time[tls_id] >= MIN_GREEN and
            _empty_time[tls_id] >= NO_VEHICLE_LIMIT):
        # número total de fases del programa activo
        logic = traci.trafficlight.getCompleteRedYellowGreenDefinition(tls_id)[0]
        num_phases = len(logic.getPhases())
        next_phase = (phase + 1) % num_phases
        traci.trafficlight.setPhase(tls_id, next_phase)
        log.debug(
            "[%s] Gap-out: %d→%d | empty=%.1fs",
            tls_id, phase, next_phase, _empty_time[tls_id],
        )
        _green_time[tls_id] = _empty_time[tls_id] = 0.0
        return 0  # runner ignorará este valor fuera de la entrada de fase

    # 3 · Delegar a fuzzy cuando corresponde
    return fuzzy.get_phase_duration(tls_id) if phase in (0, 2) else 0

def get_phase_duration(tls_id: str) -> int:   # ← alias oficial
    """Wrapper requerido por fuzzylts.sim.runner."""
    return gap_controller(tls_id)
