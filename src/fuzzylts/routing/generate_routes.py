#!/usr/bin/env python3
"""
generate_routes.py –
Generate SUMO route files for 4-hour simulations across multiple traffic-demand scenarios.
Each scenario (low, medium, high, very_high) scales a base demand profile.
"""

from __future__ import annotations
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple, Dict

# ── Configuration ───────────────────────────────────────────────────────
# Output directory for generated route files
OUTPUT_DIR = Path(__file__).resolve().parents[1] / "sumo_files"
OUTPUT_DIR.mkdir(exist_ok=True)

SIMULATION_DURATION_HOURS = 4
SECONDS_PER_HOUR = 3600
SIM_START = 0
SIM_END = SIM_START + SIMULATION_DURATION_HOURS * SECONDS_PER_HOUR

# Base vehicle-per-hour demand for each hour
BASE_DEMAND_VPH: List[int] = [500, 700, 900, 700]

# Scenario multipliers
SCENARIO_MULTIPLIERS: Dict[str, float] = {
    "low": 0.5,
    "medium": 1.0,
    "high": 2.0,
    "very_high": 3.0, # TELEPORTING WANTED
}

# Route definitions: (from_edge, to_edge, density_factor)
ROUTES: List[Tuple[str, str, float]] = [
    ("40668087#1", "542428845#0", 1.0),
    ("40668087#1", "337277957#0", 1.0),
    ("40668087#1", "1053072563", 1.0),
    ("40668087#1", "337277973#1", 1.0),
    ("40668087#1", "337277984#0", 1.0),
    ("40668087#1", "337277970#1", 1.0),
    ("40668087#1", "337277951#1", 1.0),
    ("49217102",   "337277951#3", 1.0),
    ("49217102",   "1053072563", 1.0),
    ("49217102",   "337277973#1", 1.0),
    ("49217102",   "337277984#0", 1.0),
    ("49217102",   "542428845#0", 1.0),
    ("42143912#5", "337277957#0", 1.0),
    ("42143912#5", "542428845#0", 1.0),
    ("42143912#5", "1053072563", 1.0),
    ("42143912#5", "337277973#1", 1.0),
    ("567060342#0","337277984#0", 1.0),
    ("567060342#0","542428845#0", 1.0),
    ("567060342#0","337277957#0", 1.0),
]

@dataclass(frozen=True)
class Flow:
    id: str
    from_edge: str
    to_edge: str
    begin: int
    end: int
    vph: int

    def to_xml(self) -> str:
        return (
            f'    <flow id="{self.id}" from="{self.from_edge}" to="{self.to_edge}" '
            f'type="car" begin="{self.begin}" end="{self.end}" vehsPerHour="{self.vph}"/>'
        )


def build_time_intervals() -> List[Tuple[int, int, int]]:
    """Generate hourly intervals with base demands."""
    if len(BASE_DEMAND_VPH) != SIMULATION_DURATION_HOURS:
        raise ValueError("BASE_DEMAND_VPH length must match simulation hours")
    intervals = []
    for hour_idx, demand in enumerate(BASE_DEMAND_VPH):
        start = SIM_START + hour_idx * SECONDS_PER_HOUR
        end = start + SECONDS_PER_HOUR
        intervals.append((start, end, demand))
    return intervals


def generate_flows_for_multiplier(mult: float) -> List[Flow]:
    """Create Flow objects for a given scenario multiplier."""
    intervals = build_time_intervals()
    flows: List[Flow] = []
    counter = 1
    total_routes = len(ROUTES)

    for start, end, base_vph in intervals:
        for fr, to, density in ROUTES:
            vph = int((base_vph * density * mult) / total_routes)
            if vph <= 0:
                continue
            flows.append(
                Flow(
                    id=f"flow_{counter}",
                    from_edge=fr,
                    to_edge=to,
                    begin=start,
                    end=end,
                    vph=vph
                )
            )
            counter += 1
    return flows


def write_routes_xml(scenario: str, flows: List[Flow]) -> None:
    """Write the .rou.xml file for a scenario."""
    file_path = OUTPUT_DIR / f"generated_routes_{scenario}.rou.xml"
    logging.info("Writing routes for '%s' → %s", scenario, file_path)

    header = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<routes>',
        '    <vType id="car" accel="1.2" decel="3.0" sigma="0.5" length="4.2" maxSpeed="13.9"/>'
    ]
    with file_path.open("w", encoding="utf-8") as f:
        f.write("\n".join(header) + "\n")
        for flow in sorted(flows, key=lambda f: f.begin):
            f.write(flow.to_xml() + "\n")
        f.write("</routes>\n")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
    for scenario, multiplier in SCENARIO_MULTIPLIERS.items():
        flows = generate_flows_for_multiplier(multiplier)
        write_routes_xml(scenario, flows)


if __name__ == "__main__":
    main()
