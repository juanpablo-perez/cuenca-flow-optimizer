# src/fuzzylts/utils/fuzzy_config.py
from __future__ import annotations
import yaml
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, List, Tuple

@dataclass
class FunctionDef:
    lmin: float
    lmax: float
    levels: List[str]

@dataclass
class FuzzyConfig:
    sumo_cfg: str
    tls: List[str]
    phase_lanes: Dict[str, Dict[int, List[str]]]
    functions: Dict[str, FunctionDef]
    rules: List[List[str]]

    @classmethod
    def load(cls, path: Path) -> FuzzyConfig:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        # parse functions
        funcs: Dict[str, FunctionDef] = {}
        for name, spec in raw.get("functions", {}).items():
            funcs[name] = FunctionDef(
                lmin=spec["lmin"],
                lmax=spec["lmax"],
                levels=spec["levels"],
            )
        return cls(
            sumo_cfg=raw["sumo_cfg"],
            tls=raw["tls"],
            phase_lanes=raw["phase_lanes"],
            functions=funcs,
            rules=raw["rules"],
        )
