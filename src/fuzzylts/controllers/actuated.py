# src/fuzzylts/controllers/actuated.py
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Actuated TLS utilities for SUMO/TraCI.

This module provides:
- A deterministic conversion of fixed TLS phases into "actuated" phases
  (min/max/next) preserving binary state strings.
- A safe wrapper to rebuild a network with netconvert using
  `--tls.rebuild` + `--tls.default-type actuated`.
- Initialization of TLS logic in a live TraCI session.

Intended for reproducible experiments in scientific codebases.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from shutil import which
from typing import List, Optional

import traci
import traci.constants as tc
from traci import trafficlight as tl

# NOTE: keep the import path as in the original codebase.
# If your repo defines this in utils instead of config, adjust there (not here).
from fuzzylts.config.actuated_config import ActuatedConfig  # type: ignore
from fuzzylts.utils.log import get_logger  # type: ignore

LOGGER = get_logger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

ACTUATED_TYPE: int = tc.TRAFFICLIGHT_TYPE_ACTUATED  # TraCI constant
NET_ENV_VAR: str = "TARGET_NET_XML"                 # input .net.xml from env

# ─────────────────────────────────────────────────────────────────────────────
# Configuration (path injected via env for reproducibility)
# ─────────────────────────────────────────────────────────────────────────────

_net_path_env: Optional[str] = os.getenv(NET_ENV_VAR)
# ActuatedConfig must handle `None` sensibly if no env is provided.
cfg = ActuatedConfig.load(net_path=_net_path_env)  # type: ignore[arg-type]


# ─────────────────────────────────────────────────────────────────────────────
# Phase transformation helpers
# ─────────────────────────────────────────────────────────────────────────────

def _phase_is_yellow(state: str) -> bool:
    """Heuristic: treat any 'y' in the state string as a yellow/transition phase."""
    return "y" in state


def _make_actuated_phases(
    phases_in: List[tl.Phase],
    *,
    green_min: float,
    green_duration: float,
    green_max: float,
    yellow_fix: float,
) -> List[tl.Phase]:
    """Convert raw phases into actuated phases, preserving state strings.

    The `next` pointer is wired in ring order (i → i+1 mod N).

    Args:
        phases_in: Original phases from the base TLS logic.
        green_min: Minimum green duration (seconds).
        green_duration: Nominal green duration (seconds).
        green_max: Maximum green duration (seconds).
        yellow_fix: Fixed yellow (amber) duration (seconds).

    Returns:
        A list of `tl.Phase` configured as actuated (min/max/next).
    """
    out: List[tl.Phase] = []
    n = len(phases_in)
    for i, p in enumerate(phases_in):
        if _phase_is_yellow(p.state):
            duration = minDur = maxDur = float(yellow_fix)
        else:
            duration = float(green_duration)
            minDur = float(green_min)
            maxDur = float(green_max)

        next_tuple = ((i + 1) % n,)  # ring next
        out.append(
            tl.Phase(
                duration=duration,
                state=p.state,
                minDur=minDur,
                maxDur=maxDur,
                next=next_tuple,
            )
        )
    return out


def build_actuated_logic_from(
    base: tl.Logic,
    *,
    green_min: float,
    green_duration: float,
    green_max: float,
    yellow_fix: float,
) -> tl.Logic:
    """Build an actuated `tl.Logic` from a base logic, transforming phases only.

    Preserves:
    - programID
    - currentPhaseIndex
    - subParameter

    Args:
        base: Source logic to transform.
        green_min: Minimum green duration (seconds).
        green_duration: Nominal green duration (seconds).
        green_max: Maximum green duration (seconds).
        yellow_fix: Fixed yellow (amber) duration (seconds).

    Returns:
        An actuated-type (`ACTUATED_TYPE`) `tl.Logic` with transformed phases.
    """
    phases = getattr(base, "phases", [])
    new_phases = _make_actuated_phases(
        phases,
        green_min=green_min,
        green_duration=green_duration,
        green_max=green_max,
        yellow_fix=yellow_fix,
    )
    return tl.Logic(
        programID=getattr(base, "programID"),
        type=ACTUATED_TYPE,
        currentPhaseIndex=getattr(base, "currentPhaseIndex", 0),
        phases=new_phases,
        subParameter=getattr(base, "subParameter", {}),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Live TraCI initialization
# ─────────────────────────────────────────────────────────────────────────────

def initialize_tls() -> None:
    """Replace current TLS programs with an actuated variant for all IDs in `cfg.tls`.

    Requires:
        - An active TraCI connection.
        - TLS IDs in `cfg.tls` must exist in the network.
    """
    for tls_id in cfg.tls:
        current_prog = tl.getProgram(tls_id)
        logics = tl.getAllProgramLogics(tls_id)
        base = next((L for L in logics if getattr(L, "programID", None) == current_prog), logics[0])

        new_logic = build_actuated_logic_from(
            base,
            green_min=cfg.green_min,
            green_max=cfg.green_max,
            green_duration=cfg.green_duration,
            yellow_fix=cfg.yellow_fix,
        )
        tl.setProgramLogic(tls_id, new_logic)
        LOGGER.debug("TLS %s switched to actuated program '%s'", tls_id, new_logic.programID)

    LOGGER.info("Initialized %d TLS in actuated mode (type=%d).", len(cfg.tls), ACTUATED_TYPE)


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


def preprocess_network(path: Path, *, out_name: str | None = None, force: bool = False) -> Path:
    """Rebuild TLS programs as 'actuated' and write a new `.net.xml`.

    Parameters
    ----------
    path : Path
        Input network (`.net.xml` or `.net.xml.gz`) file.
    out_name : str | None
        Optional output file name. Defaults to `<stem>.actuated.net.xml`.
    force : bool
        Overwrite existing output file if True.

    Returns
    -------
    Path
        The output `.net.xml` path.

    Notes
    -----
    Requires `netconvert` with support for:
        --tls.rebuild
        --tls.default-type actuated
    """
    if not path.exists():
        raise FileNotFoundError(path)

    output = (path.parent / (out_name or f"{path.stem}.actuated.net.xml")).resolve()
    if output.exists() and not force:
        LOGGER.info("Using existing network: %s", output)
        return output

    netconvert = _resolve_netconvert()
    cmd = [
        netconvert,
        "-s",
        str(path),
        "--tls.rebuild",
        "true",
        "--tls.default-type",
        "actuated",
        "-o",
        str(output),
    ]

    LOGGER.info("Running netconvert to rebuild TLS as actuated.")
    LOGGER.debug("Command: %s", " ".join(cmd))

    try:
        proc = subprocess.run(cmd, check=True, capture_output=True, text=True)
        if proc.stdout:
            LOGGER.debug("netconvert stdout:\n%s", proc.stdout)
        if proc.stderr:
            # netconvert is chatty on stderr even on success; keep as debug
            LOGGER.debug("netconvert stderr:\n%s", proc.stderr)
    except subprocess.CalledProcessError as e:
        msg = f"netconvert failed (code {e.returncode}). Stderr:\n{e.stderr}"
        LOGGER.error(msg)
        raise NetworkBuildError(msg) from e

    LOGGER.info("Wrote actuated network: %s", output)
    return output


__all__ = [
    "initialize_tls",
    "get_phase_duration",
    "build_actuated_logic_from",
    "preprocess_network",
    "NetworkBuildError",
]
