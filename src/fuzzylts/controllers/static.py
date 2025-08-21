# src/fuzzylts/controllers/static.py
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Static TLS utilities for SUMO/TraCI.

This module provides:
- A deterministic conversion of fixed TLS phases into "static" phases
  (min/max preserved; state strings unchanged).
- A wrapper to rebuild a network with `netconvert` using
  `--tls.rebuild` + `--tls.default-type static`.
- Initialization of TLS logic in a live TraCI session.

Intended for reproducible experiments in scientific codebases.

Notes
-----
- Green phases are assigned a fixed duration (`green_fix`) and yellows use
  `yellow_fix`. Red time is optionally set equal to `green_fix` at build time.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass  # kept to avoid changing imports surface
from pathlib import Path
from shutil import which
from typing import List, Optional

import traci
import traci.constants as tc
from traci import trafficlight as tl

# Keep import path consistent with your codebase layout.
from fuzzylts.config.static_config import StaticConfig  # type: ignore
from fuzzylts.utils.log import get_logger  # type: ignore

log = get_logger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

STATIC_TYPE: int = tc.TRAFFICLIGHT_TYPE_STATIC  # TraCI constant
NET_ENV_VAR: str = "TARGET_NET_XML"             # input .net.xml from env (if used elsewhere)

# ─────────────────────────────────────────────────────────────────────────────
# Configuration (path injected via env for reproducibility)
# ─────────────────────────────────────────────────────────────────────────────

_net_path_env: Optional[str] = os.getenv(NET_ENV_VAR)
# StaticConfig must handle `None` sensibly if no env var is provided.
cfg = StaticConfig.load(net_path=_net_path_env)  # type: ignore[arg-type]


# ─────────────────────────────────────────────────────────────────────────────
# Phase transformation helpers
# ─────────────────────────────────────────────────────────────────────────────

def _phase_is_yellow(state: str) -> bool:
    """Heuristic: treat any 'y' in the state string as a yellow/transition phase."""
    return "y" in state


def _make_static_phases(
    phases_in: List[tl.Phase],
    *,
    green_fix: int,
    yellow_fix: int,
) -> List[tl.Phase]:
    """Convert raw phases into static phases, preserving state strings.

    Each **green** phase receives fixed duration/min/max = `green_fix`.
    Each **yellow** phase receives fixed duration/min/max = `yellow_fix`.

    Args:
        phases_in: Original phases from the base TLS logic.
        green_fix: Fixed green duration (seconds).
        yellow_fix: Fixed yellow duration (seconds).

    Returns:
        A list of `tl.Phase` with fixed durations.
    """
    out: List[tl.Phase] = []
    for p in phases_in:
        if _phase_is_yellow(p.state):
            duration = minDur = maxDur = int(yellow_fix)
        else:
            duration = minDur = maxDur = int(green_fix)

        out.append(
            tl.Phase(
                duration=duration,
                state=p.state,
                minDur=minDur,
                maxDur=maxDur,
            )
        )
    return out


def build_static_logic_from(
    base: tl.Logic,
    *,
    green_fix: int,
    yellow_fix: int,
) -> tl.Logic:
    """Build a static `tl.Logic` from a base logic, transforming phases only.

    Preserves:
    - programID
    - currentPhaseIndex
    - subParameter

    Args:
        base: Source logic to transform.
        green_fix: Fixed green duration (seconds).
        yellow_fix: Fixed yellow duration (seconds).

    Returns:
        A static-type (`STATIC_TYPE`) `tl.Logic` with transformed phases.
    """
    phases = getattr(base, "phases", [])
    new_phases = _make_static_phases(phases, green_fix=green_fix, yellow_fix=yellow_fix)
    return tl.Logic(
        programID=getattr(base, "programID"),
        type=STATIC_TYPE,
        currentPhaseIndex=getattr(base, "currentPhaseIndex", 0),
        phases=new_phases,
        subParameter=getattr(base, "subParameter", {}),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Live TraCI initialization
# ─────────────────────────────────────────────────────────────────────────────

def initialize_tls() -> None:
    """Replace current TLS programs with a static variant for all IDs in `cfg.tls`.

    Requires:
        - An active TraCI connection.
        - TLS IDs in `cfg.tls` must exist in the network.
    """
    for tls_id in cfg.tls:
        current_prog = tl.getProgram(tls_id)
        logics = tl.getAllProgramLogics(tls_id)
        base = next((L for L in logics if getattr(L, "programID", None) == current_prog), logics[0])

        new_logic = build_static_logic_from(
            base,
            green_fix=cfg.green_fix,
            yellow_fix=cfg.yellow_fix,
        )
        tl.setProgramLogic(tls_id, new_logic)
        log.debug("TLS %s switched to static program '%s'", tls_id, new_logic.programID)

    log.info("Initialized %d TLS in static mode (type=%d).", len(cfg.tls), STATIC_TYPE)


# ─────────────────────────────────────────────────────────────────────────────
# Public API example
# ─────────────────────────────────────────────────────────────────────────────

def get_phase_duration(tls_id: str) -> float:
    """Return the configured duration (seconds) of the current phase for `tls_id`."""
    return float(tl.getPhaseDuration(tls_id))


# ─────────────────────────────────────────────────────────────────────────────
# Network preprocessing (netconvert)
# ─────────────────────────────────────────────────────────────────────────────

class NetworkBuildError(RuntimeError):
    """Raised when `netconvert` fails to rebuild the network."""


def _resolve_netconvert() -> str:
    """Find a usable `netconvert` executable or raise `NetworkBuildError`."""
    exe = which("netconvert")
    if exe:
        return exe
    # Optionally fall back to $SUMO_HOME/bin/netconvert
    candidate = Path(os.environ.get("SUMO_HOME", "")) / "bin" / "netconvert"
    if candidate.exists():
        return str(candidate)
    raise NetworkBuildError("netconvert not found in PATH or $SUMO_HOME/bin")


def preprocess_network(
    path: Path,
    *,
    out_name: str | None = None,
    force: bool = False,
) -> Path:
    """Rebuild TLS programs as 'static' and write a new network file.

    Parameters
    ----------
    path : Path
        Input network (`.net.xml` or `.net.xml.gz`) file.
    out_name : str | None
        Optional output name. Defaults to `<stem>.static.xml`.
    force : bool
        Overwrite existing output file if True.

    Returns
    -------
    Path
        Path to the output network.

    Notes
    -----
    Requires `netconvert` with support for:
        --tls.rebuild
        --tls.default-type static
    """
    if not path.exists():
        raise FileNotFoundError(path)

    output = (path.parent / (out_name or f"{path.stem}.static.xml")).resolve()
    if output.exists() and not force:
        log.info("Using existing network: %s", output)
        return output

    netconvert = _resolve_netconvert()
    cmd = [
        netconvert,
        "-s",
        str(path),
        "--tls.rebuild",
        "true",
        "--tls.default-type",
        "static",
        "-o",
        str(output),
    ]

    # Append tls_* options according to cfg
    tls_options = {
        "green.time": cfg.green_fix,
        "yellow.time": cfg.yellow_fix,
        "red.time": cfg.green_fix,
    }
    for k, v in (tls_options or {}).items():
        cmd.extend([f"--tls.{k}", str(v)])

    log.info("Running netconvert to rebuild TLS as static.")
    log.debug("Command: %s", " ".join(cmd))

    try:
        proc = subprocess.run(cmd, check=True, capture_output=True, text=True)
        if proc.stdout:
            log.debug("netconvert stdout:\n%s", proc.stdout)
        if proc.stderr:
            # netconvert can output informational lines on stderr even on success
            log.debug("netconvert stderr:\n%s", proc.stderr)
    except subprocess.CalledProcessError as e:
        msg = f"netconvert failed (code {e.returncode}). Stderr:\n{e.stderr}"
        log.error(msg)
        raise NetworkBuildError(msg) from e

    log.info("Wrote static network: %s", output)
    return output


__all__ = [
    "initialize_tls",
    "get_phase_duration",
    "build_static_logic_from",
    "preprocess_network",
    "NetworkBuildError",
]
