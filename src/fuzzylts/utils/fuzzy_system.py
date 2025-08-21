# src/fuzzylts/utils/fuzzy_system.py
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fuzzy system builder utilities (membership functions + rule base).

This module turns YAML-driven fuzzy variable specs (`FunctionDef`) into
scikit-fuzzy `Antecedent`/`Consequent` variables with evenly spaced
triangular/trapezoidal membership functions, and compiles a list of rules
into a `skfuzzy.control.ControlSystem`-ready rule set.

Design
------
- For each variable with `n` linguistic levels (labels), we create:
  - Left shoulder trapezoid for the first label,
  - Right shoulder trapezoid for the last label,
  - Symmetric triangles for intermediate labels,
  evenly spaced in the `[lmin, lmax]` universe.
- The variable named **"green"** is treated as the **output** (`Consequent`);
  all other variables are **inputs** (`Antecedent`).

Typical usage
-------------
    from fuzzylts.config.fuzzy_config import FuzzyConfig
    from fuzzylts.utils.fuzzy_system import generate_memberships, build_rules
    from skfuzzy import control as ctrl

    cfg = FuzzyConfig.load(net_path="...")            # YAML + topology-derived metadata
    vars_ = generate_memberships(cfg.functions)       # dict[str, Antecedent|Consequent]
    rules = build_rules(cfg.rules, vars_["vehicles"], vars_["arrival"], vars_["green"])
    system = ctrl.ControlSystem(rules)
    sim = ctrl.ControlSystemSimulation(system)
"""

from __future__ import annotations

from typing import Dict, List, Mapping, MutableMapping, Sequence, Union

import numpy as np
import skfuzzy as fuzz
from skfuzzy import control as ctrl

# YAML-backed function spec (lmin, lmax, levels)
from fuzzylts.config.fuzzy_config import FunctionDef  # type: ignore

# Type alias for readability
FuzzyVar = Union[ctrl.Antecedent, ctrl.Consequent]


def generate_memberships(func_defs: Mapping[str, FunctionDef]) -> Dict[str, FuzzyVar]:
    """Create scikit-fuzzy variables (input/output) and attach membership functions.

    Variables:
      - Any variable **named "green"** becomes a `ctrl.Consequent` (output).
      - All other variables become `ctrl.Antecedent` (inputs).

    Membership functions:
      - Evenly spaced across the continuous universe `[lmin, lmax]` (1000 samples).
      - First label:  left-shoulder trapezoid
      - Last label:   right-shoulder trapezoid
      - Middle labels: symmetric triangles

    Args:
        func_defs: Mapping of variable name → `FunctionDef` (lmin, lmax, levels).

    Returns:
        Dict mapping variable name → `ctrl.Antecedent` or `ctrl.Consequent`.

    Raises:
        ValueError: If a variable has fewer than 2 levels or if `lmax <= lmin`.
    """
    memberships: Dict[str, FuzzyVar] = {}

    for name, spec in func_defs.items():
        lmin, lmax = float(spec.lmin), float(spec.lmax)
        levels: List[str] = list(spec.levels)
        n = len(levels)

        if n < 2:
            raise ValueError(f"Variable '{name}' must define at least 2 levels; got {n}.")
        if not np.isfinite(lmin) or not np.isfinite(lmax) or lmax <= lmin:
            raise ValueError(f"Invalid bounds for '{name}': lmin={lmin}, lmax={lmax}.")

        # Continuous universe
        universe = np.linspace(lmin, lmax, 1000)

        # Output is named 'green'; others are inputs
        var: FuzzyVar = ctrl.Consequent(universe, name) if name == "green" else ctrl.Antecedent(universe, name)

        step = (lmax - lmin) / (n - 1)

        for i, lvl in enumerate(levels):
            if i == 0:
                # Left-shoulder trapezoid
                mf = fuzz.trapmf(universe, [lmin, lmin, lmin + step, lmin + 2 * step])
            elif i == n - 1:
                # Right-shoulder trapezoid
                mf = fuzz.trapmf(universe, [lmax - 2 * step, lmax - step, lmax, lmax])
            else:
                # Symmetric triangle
                a = lmin + (i - 1) * step
                b = lmin + i * step
                c = lmin + (i + 1) * step
                mf = fuzz.trimf(universe, [a, b, c])

            # Attach MF under the linguistic label
            var[lvl] = mf  # type: ignore[index]

        memberships[name] = var

    return memberships


def build_rules(
    rule_list: Sequence[Sequence[str]],
    veh_var: ctrl.Antecedent,
    arr_var: ctrl.Antecedent,
    grn_var: ctrl.Consequent,
) -> List[ctrl.Rule]:
    """Compile the fuzzy rule base.

    Each rule is a triplet `[veh_level, arrival_level, green_level]`, producing:

        Rule( veh_var[veh_level] & arr_var[arrival_level]  ->  grn_var[green_level] )

    Args:
        rule_list: Iterable of triplets `[vehicles_level, arrival_level, green_level]`.
        veh_var: Antecedent for the number of vehicles.
        arr_var: Antecedent for the arrival rate.
        grn_var: Consequent for the green duration.

    Returns:
        A list of `ctrl.Rule` suitable for `ctrl.ControlSystem`.

    Notes:
        This function assumes the provided level labels exist in the corresponding
        variables; scikit-fuzzy will raise a `KeyError` if a label is missing.
    """
    rules: List[ctrl.Rule] = []
    for veh_l, arr_l, grn_l in rule_list:
        rules.append(ctrl.Rule(veh_var[veh_l] & arr_var[arr_l], grn_var[grn_l]))
    return rules


__all__ = ["generate_memberships", "build_rules", "FuzzyVar"]
