#!/usr/bin/env python3
"""
run_experiment.py –
Run a single SUMO simulation with the specified controller and scenario,
then save outputs and summary metrics in experiments/<run_id>/.
"""

from __future__ import annotations
import argparse
import json
import logging
import os
import time
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict

from fuzzylts.sim.runner import run_sumo_once
from fuzzylts.utils.io import tripinfo_xml_to_df, stats_xml_to_dict
from fuzzylts.utils.log import get_logger

# Base directories
ROOT_DIR = Path(__file__).resolve().parents[3]
SUMO_DIR = ROOT_DIR / "sumo_files"
EXP_DIR  = ROOT_DIR / "experiments"

log = get_logger(__name__)


def parse_args() -> argparse.Namespace:
    """
    Parse command-line arguments.

    Returns:
        An argparse.Namespace with controller, scenario, seed, and log_level.
    """
    parser = argparse.ArgumentParser(
        description="Run one SUMO simulation with a given controller and scenario."
    )
    parser.add_argument(
        "-c", "--controller", choices=["static", "actuated", "fuzzy"],
        required=True, help="Traffic-light controller to use."
    )
    parser.add_argument(
        "-s", "--scenario", choices=["low", "medium", "high", "very_high"],
        required=True, help="Traffic demand scenario."
    )
    parser.add_argument(
        "--seed", type=int, default=0,
        help="Random seed for SUMO (default: 0)."
    )
    parser.add_argument(
        "--log-level", default=os.getenv("FUZZYLTS_LOG_LEVEL", "INFO"),
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity level."
    )
    return parser.parse_args()


def override_sumocfg(base_cfg: Path, overrides: Dict[str, str]) -> Path:
    """
    Copy a SUMO config file and inject new route-files and seed values.

    Args:
        base_cfg: Path to the original .sumocfg file.
        overrides: Dict with keys 'route-files' and 'seed'.

    Returns:
        Path to the temporary .sumocfg file with overrides applied.
    """
    tree = ET.parse(base_cfg)
    root = tree.getroot()
    input_elem = root.find("input") or ET.SubElement(root, "input")

    # Remove existing <route-files> elements
    for elem in input_elem.findall("route-files"):
        input_elem.remove(elem)
    ET.SubElement(input_elem, "route-files").set("value", overrides["route-files"])

    # Update or add <seed>
    seed_elem = root.find(".//seed")
    if seed_elem is None:
        seed_elem = ET.SubElement(input_elem, "seed")
    seed_elem.set("value", overrides["seed"])

    temp_name = f"_temp_{uuid.uuid4().hex[:6]}_{base_cfg.name}"
    temp_cfg = base_cfg.parent / temp_name
    tree.write(temp_cfg, encoding="utf-8", xml_declaration=True)
    return temp_cfg


def main() -> None:
    args = parse_args()

    # Configure logging
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s | %(levelname)-7s | %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    log.setLevel(args.log_level)

    # Prepare input files
    routes_file = SUMO_DIR / f"generated_routes_{args.scenario}.rou.xml"
    cfg_file    = SUMO_DIR / f"osm_{args.controller}.sumocfg"
    if not routes_file.exists():
        log.error("Routes file not found: %s", routes_file)
        raise FileNotFoundError(routes_file)
    if not cfg_file.exists():
        log.error("Config file not found: %s", cfg_file)
        raise FileNotFoundError(cfg_file)

    # Generate temporary config with overridden routes and seed
    temp_cfg = override_sumocfg(cfg_file, {
        "route-files": str(routes_file),
        "seed": str(args.seed),
    })

    # Create unique run directory
    run_id = f"{args.controller}_{args.scenario}_{args.seed:02d}_{int(time.time())}"
    out_dir = EXP_DIR / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    os.environ["FUZZYLTS_RUN_DIR"] = str(out_dir)

    # Execute SUMO + controller
    trip_xml, stats_xml = run_sumo_once(
        controller=args.controller,
        routes_xml=routes_file,
        sumocfg=temp_cfg,
        output_dir=out_dir,
        sim_seed=args.seed,
    )

    # Clean up temporary config
    if temp_cfg.name.startswith("_temp_") and temp_cfg.exists():
        temp_cfg.unlink()
        log.debug("Removed temp config: %s", temp_cfg)

    # Post-process metrics
    df = tripinfo_xml_to_df(trip_xml)
    stats = stats_xml_to_dict(stats_xml)

    # Determine columns
    wait_col  = "waitingTime" if "waitingTime" in df.columns else "waiting_time"
    speed_col = "speed"

    # Compute average speed fallback
    if speed_col in df.columns:
        avg_speed = df[speed_col].mean()
    elif {"routeLength", "duration"}.issubset(df.columns):
        avg_speed = (df["routeLength"] / df["duration"]).mean()
    else:
        avg_speed = None

    # Determine simulation end time
    sim_time = (
        stats.get("time") or stats.get("end") or stats.get("step") or
        (df["arrival"].max() if "arrival" in df.columns else 0)
    )

    metrics = {
        "avg_wait":     df[wait_col].mean() if wait_col in df.columns else None,
        "avg_duration": df["duration"].mean()   if "duration" in df.columns else None,
        "avg_speed":    avg_speed,
        "vehicles":     len(df),
        "inserted":     stats.get("inserted", len(df)),
        "ended":        stats.get("ended", len(df)),
        "teleports":    stats.get("teleports_total", 0),
        "sim_time":     sim_time,
    }

    # Write outputs
    (out_dir / "metrics.json").write_text(json.dumps(metrics, indent=2))
    (out_dir / "config.json").write_text(json.dumps(vars(args), indent=2))

    log.info("✅ Experiment completed: %s", run_id)


if __name__ == "__main__":
    main()
