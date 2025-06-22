#!/usr/bin/env python3
"""
generate_routes.py  –  Generador de flujos SUMO para 4 horas y 4 escenarios
Autor: JP · Versión 2025-06-21

Escenarios:
  • low        – tráfico bajo
  • medium     – tráfico medio
  • high       – tráfico alto (sin teleports esperados)
  • very_high  – tráfico muy alto (probable teleports)

Uso rápido:
  $ python generate_routes.py
  # Crea ./sumo_files/generated_routes_{low,medium,high,very_high}.rou.xml
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple, Dict

# ╭──────────────────────────────────────────────────────────╮
# │ Configuración general                                   │
# ╰──────────────────────────────────────────────────────────╯

OUTPUT_DIR = Path("sumo_files")
OUTPUT_DIR.mkdir(exist_ok=True)

SIM_START: int = 0              # [s]  tiempo inicial (00:00)
SIM_HOURS: int = 4              # [h]  duración de la simulación
SECONDS_PER_HOUR: int = 3600
SIM_END: int = SIM_START + SIM_HOURS * SECONDS_PER_HOUR

# Tramos de 1 h con demanda base (vehs/h) – ajústalo a tu realidad
BASE_DEMAND: List[int] = [500, 700, 900, 700]  # len == SIM_HOURS

# Escenarios y multiplicadores
TRAFFIC_SCENARIOS: Dict[str, float] = {
    "low": 0.5,
    "medium": 1.0,
    "high": 1.3,        # alto ≈ 30 % sobre medio, sin teleports
    "very_high": 1.7,   # muy alto ≈ 70 % sobre medio, teleports probables
}

# Definición de rutas (from, to, multiplicador de densidad)
ROUTES: List[Tuple[str, str, float]] = [
    ("40668087#1", "542428845#0", 1),
    ("40668087#1", "337277957#0", 1),
    ("40668087#1", "1053072563", 1),
    ("40668087#1", "337277973#1", 1),
    ("40668087#1", "337277984#0", 1),
    ("40668087#1", "337277970#1", 1),
    ("40668087#1", "337277951#1", 1),
    ("49217102",   "337277951#3", 1),
    ("49217102",   "1053072563", 1),
    ("49217102",   "337277973#1", 1),
    ("49217102",   "337277984#0", 1),
    ("49217102",   "542428845#0", 1),
    ("42143912#5", "337277957#0", 1),
    ("42143912#5", "542428845#0", 1),
    ("42143912#5", "1053072563", 1),
    ("42143912#5", "337277973#1", 1),
    ("567060342#0","337277984#0", 1),
    ("567060342#0","542428845#0", 1),
    ("567060342#0","337277957#0", 1),
]

# ╭──────────────────────────────────────────────────────────╮
# │ Lógica de generación                                    │
# ╰──────────────────────────────────────────────────────────╯

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s",
)

@dataclass
class Flow:
    fid: str
    fr: str
    to: str
    begin: int
    end: int
    vph: int

    def to_xml(self) -> str:
        return (
            f'    <flow id="{self.fid}" from="{self.fr}" to="{self.to}" '
            f'type="car" begin="{self.begin}" end="{self.end}" vehsPerHour="{self.vph}"/>'
        )

def build_hour_intervals() -> List[Tuple[int, int, int]]:
    """Convierte BASE_DEMAND en tuplas (begin, end, demand)."""
    if len(BASE_DEMAND) != SIM_HOURS:
        raise ValueError("BASE_DEMAND debe tener SIM_HOURS elementos")
    intervals = []
    for h, demand in enumerate(BASE_DEMAND):
        b = SIM_START + h * SECONDS_PER_HOUR
        e = b + SECONDS_PER_HOUR
        intervals.append((b, e, demand))
    return intervals

def generate_flows(multiplier: float) -> List[Flow]:
    """Genera los flujos para un escenario dado."""
    flows: List[Flow] = []
    intervals = build_hour_intervals()
    fid = 1
    for start, end, base_vph in intervals:
        for fr, to, dens in ROUTES:
            vph = int(base_vph * dens * multiplier / len(ROUTES))
            flows.append(Flow(f"f{fid}", fr, to, start, end, vph))
            fid += 1
    return flows

def write_routes_file(scenario: str, flows: List[Flow]) -> None:
    """Escribe el archivo XML .rou para un escenario."""
    path = OUTPUT_DIR / f"generated_routes_{scenario}.rou.xml"
    logging.info("Creando %s", path)
    with path.open("w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n<routes>\n')
        f.write('    <vType id="car" accel="1.2" decel="3.0" sigma="0.5" '
                'length="4.2" maxSpeed="13.9"/>\n')
        for flow in sorted(flows, key=lambda x: x.begin):
            if flow.vph > 0:
                f.write(flow.to_xml() + "\n")
        f.write("</routes>\n")

def main() -> None:
    for scenario, mult in TRAFFIC_SCENARIOS.items():
        flows = generate_flows(mult)
        write_routes_file(scenario, flows)

if __name__ == "__main__":
    main()
