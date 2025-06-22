# src/fuzzylts/utils/fuzzy_system.py

"""
fuzzy_system – Helpers for building fuzzy inference systems with scikit-fuzzy
"""
from __future__ import annotations
from typing import Any, Dict, List, Union

import numpy as np
import skfuzzy as fuzz
from skfuzzy import control as ctrl


def generate_memberships(
    config: Dict[str, Dict[str, Any]]
) -> Dict[str, Union[ctrl.Antecedent, ctrl.Consequent]]:
    """
    Create fuzzy variables with membership functions based on the given configuration.

    Args:
        config: Mapping of variable names to definitions:
                {
                  "lmin": float,      # minimum universe value
                  "lmax": float,      # maximum universe value
                  "niveles": List[str]  # fuzzy labels
                }

    Returns:
        A dict mapping variable names to Antecedent or Consequent objects.
    """
    variables: Dict[str, Union[ctrl.Antecedent, ctrl.Consequent]] = {}

    for name, spec in config.items():
        lmin = spec["lmin"]
        lmax = spec["lmax"]
        levels: List[str] = spec["niveles"]
        universe = np.linspace(lmin, lmax, 1000)

        # Consequent (output) if "verde", otherwise Antecedent (input)
        var = (
            ctrl.Consequent(universe, name)
            if name == "verde"
            else ctrl.Antecedent(universe, name)
        )

        step = (lmax - lmin) / (len(levels) - 1)
        for i, level in enumerate(levels):
            if i == 0:
                mf = fuzz.trapmf(universe, [lmin, lmin, lmin + step, lmin + 2 * step])
            elif i == len(levels) - 1:
                mf = fuzz.trapmf(universe, [lmax - 2 * step, lmax - step, lmax, lmax])
            else:
                a = lmin + (i - 1) * step
                b = lmin + i * step
                c = lmin + (i + 1) * step
                mf = fuzz.trimf(universe, [a, b, c])
            var[level] = mf

        variables[name] = var

    return variables


def build_rules(
    rule_definitions: List[List[str]],
    veh_var: ctrl.Antecedent,
    arr_var: ctrl.Antecedent,
    green_var: ctrl.Consequent,
) -> List[ctrl.Rule]:
    """
    Construct fuzzy rules from definition tuples.

    Args:
        rule_definitions: List of [vehicle_label, arrival_label, green_label].
        veh_var: Antecedent for vehicle count.
        arr_var: Antecedent for arrival rate.
        green_var: Consequent for green time.

    Returns:
        List of skfuzzy.control.Rule objects.
    """
    rules: List[ctrl.Rule] = []
    for veh_label, arr_label, green_label in rule_definitions:
        rules.append(
            ctrl.Rule(veh_var[veh_label] & arr_var[arr_label], green_var[green_label])
        )
    return rules
