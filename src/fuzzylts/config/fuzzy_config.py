# src/fuzzylts/utils/fuzzy_config.py
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Typed loader for the **fuzzy** controller configuration.

This module reads the fuzzy controller knowledge base from
`configs/controller/fuzzy.yaml` (linguistic variables + rule base) and
enriches it with topology-derived metadata (TLS → phases → lanes) extracted
from the SUMO network.

Usage
-----
    from pathlib import Path
    from fuzzylts.utils.fuzzy_config import FuzzyConfig

    cfg = FuzzyConfig.load(net_path=Path("sumo_files/cuenca.net.xml.gz"))
    # cfg.tls, cfg.phase_lanes, cfg.functions, cfg.rules, ...

Notes
-----
- All numeric ranges (lmin/lmax) are floats (seconds or normalized units, per YAML).
- `functions` contains the fuzzy variable definitions (arrival, vehicles, green, ...).
- `rules` encodes the rule base as triplets: [vehicles_level, arrival_level, green_level].
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
class FunctionDef:
    """Definition of a fuzzy linguistic variable.

    Attributes:
        lmin: Universe minimum (crisp lower bound before fuzzification).
        lmax: Universe maximum (crisp upper bound before fuzzification).
        levels: Ordered list of linguistic labels (e.g., ['very_slow', 'slow', ...]).
    """
    lmin: float
    lmax: float
    levels: List[str]


@dataclass
class FuzzyConfig:
    """Configuration dataclass for the *fuzzy* controller.

    Attributes:
        NAME: Fixed controller identifier ("fuzzy").
        tls: List of traffic light system (TLS) IDs discovered in the network.
        phase_lanes: Mapping TLS_ID → { phase_index → [lane_id, ...] }.
        functions: Mapping variable name → `FunctionDef` (e.g., arrival/vehicles/green).
        rules: Fuzzy rule base as a list of triplets [vehicles_level, arrival_level, green_level].
        config_path: Path to the YAML file with fuzzy functions and rules.
    """

    # Fixed name for this controller family
    NAME: ClassVar[Literal["fuzzy"]] = "fuzzy"

    # Topology-derived metadata
    tls: List[str]
    phase_lanes: TLSPhaseLanes

    # Fuzzy KB
    functions: Dict[str, FunctionDef]
    rules: List[List[str]]

    # Repository-relative default location for the YAML config
    config_path: Path = Path(__file__).resolve().parents[3] / "configs" / "controller" / "fuzzy.yaml"

    # --------------------------------------------------------------------- #
    # Factory
    # --------------------------------------------------------------------- #
    @classmethod
    def load(cls, net_path: Path) -> "FuzzyConfig":
        """Load configuration from YAML and derive TLS/phase/lanes from the network.

        Args:
            net_path: Path to the SUMO network file (.net.xml or .net.xml.gz).

        Returns:
            An initialized `FuzzyConfig` instance.

        Raises:
            FileNotFoundError: If the YAML config file is missing.
            KeyError/ValueError: If required YAML keys are missing or invalid.
        """
        if not cls.config_path.exists():
            raise FileNotFoundError(f"Fuzzy config not found: {cls.config_path}")

        # Load fuzzy KB (functions + rules)
        raw = yaml.safe_load(cls.config_path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError(f"Invalid YAML structure in {cls.config_path}; expected a mapping at the top level.")

        # Parse functions
        raw_functions = raw.get("functions", {})
        if not isinstance(raw_functions, dict):
            raise ValueError("'functions' section must be a mapping of variable_name → spec.")

        funcs: Dict[str, FunctionDef] = {}
        for name, spec in raw_functions.items():
            if not isinstance(spec, dict):
                raise ValueError(f"Function spec for '{name}' must be a mapping.")
            missing = [k for k in ("lmin", "lmax", "levels") if k not in spec]
            if missing:
                raise KeyError(f"Missing keys in function '{name}': {', '.join(missing)}")

            funcs[name] = FunctionDef(
                lmin=float(spec["lmin"]),
                lmax=float(spec["lmax"]),
                levels=list(spec["levels"]),
            )

        # Parse rules
        if "rules" not in raw:
            raise KeyError("Missing 'rules' in fuzzy YAML.")
        if not isinstance(raw["rules"], list):
            raise ValueError("'rules' must be a list of triplets [vehicles_level, arrival_level, green_level].")
        rules: List[List[str]] = [list(r) for r in raw["rules"]]

        # Extract topology metadata once from the network
        phase_lanes: TLSPhaseLanes = extract_phase_lanes(
            net_path=net_path,
            max_depth=2,
            stop_at_tl=False,
        )
        # Ensure a concrete list (not dict_keys) for stable downstream usage
        tls: List[str] = list(phase_lanes.keys())

        return cls(
            tls=tls,
            phase_lanes=phase_lanes,
            functions=funcs,
            rules=rules,
        )
