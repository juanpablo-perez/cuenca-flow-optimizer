"""Controlador estático: no interviene en la programación de SUMO."""
from __future__ import annotations

def get_phase_duration(tls_id: str) -> int:
    """
    Dummy: el runner lo detecta y NO llama a setPhaseDuration, de modo que
    SUMO utiliza los tiempos fijos definidos en el .net/.sumocfg.
    """
    return 0   # valor irrelevante; nunca se usará
