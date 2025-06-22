#!/usr/bin/env python3
"""
run_experiment.py – Ejecuta UNA simulación SUMO y guarda resultados en
experiments/<run_id>/.
"""
from __future__ import annotations

import argparse
import json
import os
import time
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict

import logging 

from fuzzylts.sim.runner import run_sumo_once
from fuzzylts.utils.io import tripinfo_xml_to_df, stats_xml_to_dict
from fuzzylts.utils.log import get_logger

ROOT_DIR = Path(__file__).resolve().parents[3]      # .../FuzzyTLS
SUMO_DIR = ROOT_DIR / "sumo_files"
EXP_DIR  = ROOT_DIR / "experiments"
log = get_logger(__name__)


# ── helper: copia .sumocfg con overrides ───────────────────────────────────
def cfg_with_overrides(base_cfg: Path, overrides: Dict[str, str]) -> Path:
    tree = ET.parse(base_cfg)
    root = tree.getroot()
    input_tag = root.find("input") or ET.SubElement(root, "input")

    # route-files (elimino previos)
    for tag in input_tag.findall("route-files"):
        input_tag.remove(tag)
    ET.SubElement(input_tag, "route-files").set("value", overrides["route-files"])

    # seed
    seed_tag = root.find(".//seed")
    if seed_tag is None:
        seed_tag = ET.SubElement(input_tag, "seed")
    seed_tag.set("value", overrides["seed"])

    tmp_cfg = base_cfg.parent / f"_temp_{uuid.uuid4().hex[:6]}_{base_cfg.name}"
    tree.write(tmp_cfg, encoding="utf-8", xml_declaration=True)
    return tmp_cfg


def build_cli() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("-c", "--controller", required=True,
                   choices=["static", "actuated", "fuzzy"])
    p.add_argument("-s", "--scenario", required=True,
                   choices=["low", "medium", "high", "very_high"])
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--log-level", default=os.getenv("FUZZYLTS_LOG_LEVEL", "INFO"),
                   choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    return p.parse_args()


def main() -> None:
    args = build_cli()

    log.setLevel(args.log_level)
    logging.basicConfig(level=args.log_level,
                        format="%(asctime)s | %(levelname)-7s | %(name)s: %(message)s",
                        datefmt="%Y-%m-%d %H:%M:%S")

    routes_xml = SUMO_DIR / f"generated_routes_{args.scenario}.rou.xml"
    base_cfg   = SUMO_DIR / f"osm_{args.controller}.sumocfg"
    if not routes_xml.exists(): raise FileNotFoundError(routes_xml)
    if not base_cfg.exists():   raise FileNotFoundError(base_cfg)

    temp_cfg = cfg_with_overrides(base_cfg, {
        "route-files": str(routes_xml),
        "seed": str(args.seed),
    })

    run_id  = f"{args.controller}_{args.scenario}_{args.seed:02d}_{int(time.time())}"
    out_dir = EXP_DIR / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    os.environ["FUZZYLTS_RUN_DIR"] = str(out_dir)    # usado por actuated.py

    from fuzzylts.controllers import get_controller 
    trip_xml, stats_xml = run_sumo_once(
        controller=args.controller,
        routes_xml=routes_xml,
        sumocfg=temp_cfg,
        output_dir=out_dir,
        sim_seed=args.seed,
    )

    # limpieza del .sumocfg temporal
    if temp_cfg.name.startswith("_temp_") and temp_cfg.exists():
        temp_cfg.unlink(missing_ok=True)

    # ── métricas robustas ────────────────────────────────────────────────
    df    = tripinfo_xml_to_df(trip_xml)
    stats = stats_xml_to_dict(stats_xml)

    # columnas posibles
    wait_col = "waitingTime" if "waitingTime" in df else "waiting_time"
    speed_col = "speed"

    # ➊ avg_speed por respaldo
    if speed_col in df:
        avg_speed = df[speed_col].mean()
    elif {"routeLength", "duration"}.issubset(df.columns):
        avg_speed = (df["routeLength"] / df["duration"]).mean()
    else:
        avg_speed = None

    # ➋ sim_time robusto
    sim_time = (
        stats.get("time") or
        stats.get("end")  or
        stats.get("step") or
        df["arrival"].max() if "arrival" in df else 0
    )

    metrics = {
        "avg_wait":     df[wait_col].mean() if wait_col in df else None,
        "avg_duration": df["duration"].mean() if "duration" in df else None,
        "avg_speed":    avg_speed,
        "vehicles":     len(df),
        "inserted":     stats.get("inserted", len(df)),
        "ended":        stats.get("ended", len(df)),
        "teleports":    stats.get("teleports_total", 0),
        "sim_time":     sim_time,
    }


    (out_dir / "metrics.json").write_text(json.dumps(metrics, indent=2))
    (out_dir / "config.json").write_text(json.dumps(vars(args), indent=2))
    log.info("✅ Experimento completado: %s", run_id)


if __name__ == "__main__":
    main()
