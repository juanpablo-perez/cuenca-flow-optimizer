# src/fuzzylts/routint/generate_routes.py
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SUMO randomTrips generator (refactor 2025)

Purpose
-------
Generate **predefined demand scenarios** using SUMO's `randomTrips.py`.
With minimal inputs (`--net`, `--hours`), this script produces the 4 core
scenarios plus `medium_extended`, targeting approximate v/c (volume-to-capacity)
ratios via simple network-derived estimates and safety clamps.

Scenarios
---------
- low, medium, high, very_high, medium_extended

Design goals
------------
- `very_high` aims at ≈ 0.80 v/c **without collapsing** (safeguarded by clamps).
- Conservative estimates for urban networks.
- Reproducible outputs given `--seed`.

Example
-------
    python generate_routes.py --net path/to/network.net.xml.gz --hours 1
"""

from __future__ import annotations

import argparse
import os
import sys
import subprocess
from dataclasses import dataclass
from pathlib import Path
from shutil import which
from typing import Final, Dict, List

# ─────────────────────────────────────────────────────────────────────────────
# Tunables (adjust as needed)
# ─────────────────────────────────────────────────────────────────────────────

CAP_PER_LANE_BASE: Final[int] = 1600  # veh/h/ln (conservative urban baseline)

SCENARIO_VC: Dict[str, float] = {
    "low": 0.165,
    "medium": 0.325,
    "medium_extended": 0.325,
    "high": 0.62,
    "very_high": 0.78,  # target ≈ 0.8 v/c (bounded by MAX_VC_CLAMP)
}

MAX_VC_CLAMP: Final[float] = 0.85            # safety ceiling for v/c
LANES_PER_EDGE_CLAMP: Final[int] = 2         # max inbound lanes counted per border edge
INBOUND_LANES_ABS_MAX: Final[int] = 6        # global cap for inbound lanes
SANITY_MAX_VEH_PER_SEC: Final[float] = 3.5   # absolute injection ceiling

# randomTrips knobs
TRIP_ATTR: Final[str] = ' departLane="random" departSpeed="random" departPos="random_free"'
BINOMIAL: Final[int] = 4
MIN_DISTANCE: Final[float] = 0.0
ALLOW_FRINGE: Final[bool] = True
FRINGE_FACTOR: Final[float] = 1.6

OUT_DIR_DEFAULT: Final[str] = "routes"


# ─────────────────────────────────────────────────────────────────────────────
# sumolib loader
# ─────────────────────────────────────────────────────────────────────────────

def _load_sumolib():
    """Return `sumolib.net.readNet`, attempting `$SUMO_HOME/tools` if needed."""
    try:
        from sumolib.net import readNet  # type: ignore
        return readNet
    except Exception:
        sumo_home = os.environ.get("SUMO_HOME")
        if not sumo_home:
            raise RuntimeError(
                "Could not import sumolib and $SUMO_HOME is not defined. "
                "Install SUMO or export SUMO_HOME (…/sumo)."
            )
        tools = str(Path(sumo_home) / "tools")
        if tools not in sys.path:
            sys.path.append(tools)
        try:
            from sumolib.net import readNet  # type: ignore
            return readNet
        except Exception as e:
            raise RuntimeError(f"Failed to import sumolib from {tools}: {e}")


def _resolve_randomtrips() -> List[str]:
    """Resolve the randomTrips.py invocation `[python, randomTrips.py]`."""
    py = sys.executable or "python"
    rt = which("randomTrips.py")
    if not rt:
        home = os.environ.get("SUMO_HOME")
        cand = Path(home).joinpath("tools", "randomTrips.py") if home else None
        if cand and cand.exists():
            rt = str(cand)
    if not rt:
        raise FileNotFoundError("randomTrips.py not found in PATH or $SUMO_HOME/tools")
    return [py, rt]


def _run(cmd: List[str]) -> None:
    """Run a subprocess command and raise on non-zero exit."""
    proc = subprocess.run(cmd, text=True, capture_output=True)
    if proc.returncode != 0:
        raise RuntimeError(
            f"Command failed (exit {proc.returncode}): {' '.join(cmd)}\nSTDERR:\n{proc.stderr}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Network estimation
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class NetStats:
    """Network-derived estimates to scale demand."""
    inbound_lanes_eff: int
    signal_factor: float
    cap_per_lane_eff: float


def _estimate_net_stats(net_path: Path) -> NetStats:
    """Estimate effective inbound lanes and capacity modifiers for an urban net."""
    readNet = _load_sumolib()
    net = readNet(str(net_path), withInternal=True)

    # 1) Effective inbound lanes (border edges only; per-edge & global clamps)
    inbound_lanes = 0
    for e in net.getEdges():  # type: ignore[attr-defined]
        try:
            func = e.getFunction()
        except Exception:
            func = None
        if func in {"internal", "connector", "walkingarea", "crossing"}:
            continue
        if e.getLaneNumber() <= 0:
            continue

        # Border edge if fromNode has no incoming edges → entry to network
        try:
            if len(e.getFromNode().getIncoming()) != 0:
                continue
        except Exception:
            continue

        # Count vehicular lanes, prefer those allowing "passenger"
        try:
            lanes = [ln for ln in e.getLanes() if getattr(ln, "allows", None) and ln.allows("passenger")]
            if not lanes:
                lanes = e.getLanes()
        except Exception:
            lanes = e.getLanes()

        inbound_lanes += min(len(lanes), LANES_PER_EDGE_CLAMP)

    inbound_lanes_eff = max(1, min(inbound_lanes, INBOUND_LANES_ABS_MAX))

    # 2) Signal factor (reduce per-lane capacity based on signal density)
    signal_factor = 0.6
    try:
        num_nodes = len(net.getNodes())
        get_tls = getattr(net, "getTrafficLights", None)
        if callable(get_tls):
            num_tls = len(net.getTrafficLights())
        else:
            # Heuristic fallback
            num_tls = sum(1 for n in net.getNodes() if getattr(n, "getType", lambda: "")() == "traffic_light")
        dens = (num_tls / max(1, num_nodes))
        # Simple mapping: more signals → lower factor (0.55..0.70)
        signal_factor = max(0.55, min(0.70, 0.70 - 0.5 * dens))
    except Exception:
        signal_factor = 0.6

    cap_per_lane_eff = CAP_PER_LANE_BASE * signal_factor
    return NetStats(
        inbound_lanes_eff=inbound_lanes_eff,
        signal_factor=signal_factor,
        cap_per_lane_eff=cap_per_lane_eff,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Scenario demand planning
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class DemandPlan:
    scenario: str
    target_hour: int
    period_s: float
    vc_applied: float
    veh_per_sec: float


def _plan_for_scenario(stats: NetStats, scenario: str) -> DemandPlan:
    """Compute target hourly trips and inter-arrival period for a given scenario."""
    if scenario not in SCENARIO_VC:
        raise ValueError(f"Unknown scenario '{scenario}'. Valid: {', '.join(SCENARIO_VC)}")

    vc_target = SCENARIO_VC[scenario]
    vc_applied = min(vc_target, MAX_VC_CLAMP)

    target_hour = int(round(stats.inbound_lanes_eff * stats.cap_per_lane_eff * vc_applied))
    target_hour = max(1, target_hour)

    # Absolute sanity clamp on injection rate (veh/s)
    veh_per_sec = target_hour / 3600.0
    if veh_per_sec > SANITY_MAX_VEH_PER_SEC:
        scale = SANITY_MAX_VEH_PER_SEC / veh_per_sec
        new_target = max(1, int(round(target_hour * scale)))
        # Rescale reported v/c for logging
        vc_applied *= (new_target / max(1, target_hour))
        target_hour = new_target
        veh_per_sec = target_hour / 3600.0

    period_s = 3600.0 / float(target_hour)
    return DemandPlan(
        scenario=scenario,
        target_hour=target_hour,
        period_s=period_s,
        vc_applied=vc_applied,
        veh_per_sec=veh_per_sec,
    )


# ─────────────────────────────────────────────────────────────────────────────
# randomTrips runner
# ─────────────────────────────────────────────────────────────────────────────

def _build_routes(net: Path, hours: float, out_dir: Path, plan: DemandPlan, seed: int) -> Path:
    """Invoke `randomTrips.py` to generate routes for a single scenario."""
    duration = int(round(hours * 3600))
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"generated_routes_{plan.scenario}.rou.xml"

    cmd = (
        _resolve_randomtrips()
        + [
            "-n", str(net),
            "-r", str(out_path),
            "-b", "0",
            "-e", str(duration),
            "--period", f"{plan.period_s:.6f}",
            "--binomial", str(BINOMIAL),
            "--seed", str(seed),
            "--trip-attributes", TRIP_ATTR,
            "--min-distance", str(MIN_DISTANCE),
            "--prefix", f"{plan.scenario}_",
        ]
    )
    if ALLOW_FRINGE:
        cmd += ["--allow-fringe", "--fringe-factor", str(FRINGE_FACTOR)]

    _run(cmd)

    trips_total = int(plan.target_hour * hours)
    print(
        "[INFO] "
        f"scenario={plan.scenario} | hours={hours:.2f} | "
        f"inbound_lanes_eff={stats_cache.inbound_lanes_eff} | "
        f"cap_per_lane_eff={stats_cache.cap_per_lane_eff:.0f} "
        f"(base={CAP_PER_LANE_BASE}, signal_factor={stats_cache.signal_factor:.2f}) | "
        f"v/c_applied={plan.vc_applied:.2f} | target_hour={plan.target_hour} | "
        f"period={plan.period_s:.3f}s | rate={plan.veh_per_sec:.2f} veh/s | trips={trips_total}"
    )
    return out_path


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Generate randomTrips routes for predefined scenarios with capacity clamps."
    )
    p.add_argument("--net", type=Path, required=True, help="Network file .net.xml(.gz)")
    p.add_argument("--hours", type=float, required=True, help="Duration in hours")
    p.add_argument("--out", type=Path, default=Path(OUT_DIR_DEFAULT), help=f"Output folder (default: {OUT_DIR_DEFAULT})")
    p.add_argument("--seed", type=int, default=42, help="randomTrips seed (default: 42)")
    p.add_argument(
        "--scenario",
        choices=list(SCENARIO_VC.keys()) + ["all"],
        default="all",
        help="One scenario or 'all' (default: all)",
    )
    return p.parse_args()


# Simple module-level cache for logging (set in main()).
stats_cache: NetStats  # assigned in main()


def main() -> None:
    """CLI entry point."""
    global stats_cache
    args = parse_args()

    if not args.net.exists():
        raise FileNotFoundError(f"Network not found: {args.net}")

    stats_cache = _estimate_net_stats(args.net)
    scenarios = list(SCENARIO_VC.keys()) if args.scenario == "all" else [args.scenario]

    print(
        "[NET] "
        f"inbound_lanes_eff={stats_cache.inbound_lanes_eff} | "
        f"signal_factor={stats_cache.signal_factor:.2f} | "
        f"cap_per_lane_eff={stats_cache.cap_per_lane_eff:.0f} veh/h/ln "
        f"(base={CAP_PER_LANE_BASE})"
    )

    for sc in scenarios:
        plan = _plan_for_scenario(stats_cache, sc)
        path = _build_routes(args.net, args.hours, args.out, plan, args.seed)
        print(f"[OK] {sc:10s}  {path}")


if __name__ == "__main__":
    main()
