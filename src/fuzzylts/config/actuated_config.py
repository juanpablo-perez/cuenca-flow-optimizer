# src/fuzzylts/utils/actuated_config.py
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Typed loader for the **actuated** controller configuration.

This module reads the controller tunables from
`configs/controller/actuated.yaml` and enriches them with topology-derived
metadata (TLS → phases → lanes) extracted from the SUMO network.

Usage
-----
    from pathlib import Path
    from fuzzylts.utils.actuated_config import ActuatedConfig

    cfg = ActuatedConfig.load(net_path=Path("sumo_files/cuenca.net.xml.gz"))
    # cfg.tls, cfg.phase_lanes, cfg.green_min, ...

Notes
-----
- All durations are in **seconds**.
- `phase_lanes` maps: TLS_ID → { phase_index → [lane_id, ...] }.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar, Dict, List, Literal

import yaml

from fuzzylts.utils.extract_phase_lanes import extract_phase_lanes


# Type aliases for clarity
PhaseIndex = int
LaneId = str
PhaseLanesMap = Dict[PhaseIndex, List[LaneId]]
TLSPhaseLanes = Dict[str, PhaseLanesMap]


@dataclass
class ActuatedConfig:
    """Configuration dataclass for the *actuated* controller.

    Attributes:
        NAME: Fixed controller identifier ("actuated").
        tls: List of traffic light system (TLS) IDs discovered in the network.
        phase_lanes: Mapping TLS_ID → { phase_index → [lane_id, ...] }.
        green_min: Minimum green time (seconds).
        green_max: Maximum green time (seconds).
        green_duration: Nominal (initial) green time (seconds).
        yellow_fix: Fixed yellow (amber) interval between phases (seconds).
        config_path: Path to the YAML file with timing tunables.
    """

    # Fixed name for this controller family
    NAME: ClassVar[Literal["actuated"]] = "actuated"

    # Topology-derived metadata
    tls: List[str]
    phase_lanes: TLSPhaseLanes

    # Timing tunables (seconds)
    green_min: float
    green_max: float
    green_duration: float
    yellow_fix: float

    # Repository-relative default location for the YAML config
    config_path: Path = Path(__file__).resolve().parents[3] / "configs" / "controller" / "actuated.yaml"

    # --------------------------------------------------------------------- #
    # Factory
    # --------------------------------------------------------------------- #
    @classmethod
    def load(cls, net_path: Path) -> "ActuatedConfig":
        """Load configuration from YAML and derive TLS/phase/lanes from the network.

        Args:
            net_path: Path to the SUMO network file (.net.xml or .net.xml.gz).

        Returns:
            An initialized `ActuatedConfig` instance.

        Raises:
            FileNotFoundError: If the YAML config file is missing.
            KeyError/ValueError: If required YAML keys are missing or invalid.
        """
        if not cls.config_path.exists():
            raise FileNotFoundError(f"Actuated config not found: {cls.config_path}")

        # Load timing tunables from YAML (expects keys defined below).
        raw = yaml.safe_load(cls.config_path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError(f"Invalid YAML structure in {cls.config_path}; expected a mapping.")

        # Extract topology metadata once from the network
        phase_lanes: TLSPhaseLanes = extract_phase_lanes(
            net_path=net_path,
            max_depth=0,
            stop_at_tl=False,
        )
        # Ensure a concrete list (not dict_keys) for stable downstream usage
        tls: List[str] = list(phase_lanes.keys())

        # Required timing keys (all in seconds)
        required_keys = ("green_min", "green_max", "green_duration", "yellow_fix")
        missing = [k for k in required_keys if k not in raw]
        if missing:
            raise KeyError(f"Missing keys in {cls.config_path.name}: {', '.join(missing)}")

        return cls(
            tls=tls,
            phase_lanes=phase_lanes,
            green_min=float(raw["green_min"]),
            green_max=float(raw["green_max"]),
            green_duration=float(raw["green_duration"]),
            yellow_fix=float(raw["yellow_fix"]),
        )
