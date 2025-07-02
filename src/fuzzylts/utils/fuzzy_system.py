# src/fuzzylts/utils/fuzzy_system.py

from __future__ import annotations
import numpy as np
import skfuzzy as fuzz
from skfuzzy import control as ctrl
from typing import Dict, List

# we import your YAML-backed FunctionDef
from fuzzylts.config.fuzzy_config import FunctionDef

def generate_memberships(
    func_defs: Dict[str, FunctionDef]
) -> Dict[str, ctrl.Antecedent | ctrl.Consequent]:
    """
    Given a dict of FunctionDef (lmin, lmax, levels), build
    one Antecedent/Consequent per variable with equally spaced
    triangular/trapezoidal MFs.
    """
    memberships: Dict[str, ctrl.Antecedent | ctrl.Consequent] = {}

    for name, spec in func_defs.items():
        lmin, lmax = spec.lmin, spec.lmax
        levels: List[str] = spec.levels
        n = len(levels)

        # continuous universe
        universe = np.linspace(lmin, lmax, 1000)
        # fuzzy‐control var: inputs are Antecedent, output is Consequent
        if name == "green":
            var = ctrl.Consequent(universe, name)
        else:
            var = ctrl.Antecedent(universe, name)

        step = (lmax - lmin) / (n - 1)

        for i, lvl in enumerate(levels):
            if i == 0:
                # left‐shoulder trapezoid
                mf = fuzz.trapmf(universe, [lmin, lmin, lmin + step, lmin + 2*step])
            elif i == n - 1:
                # right‐shoulder trapezoid
                mf = fuzz.trapmf(universe, [lmax - 2*step, lmax - step, lmax, lmax])
            else:
                # symmetric triangle
                a = lmin + (i - 1)*step
                b = lmin + i*step
                c = lmin + (i + 1)*step
                mf = fuzz.trimf(universe, [a, b, c])

            var[lvl] = mf

        memberships[name] = var

    return memberships


def build_rules(
    rule_list: List[List[str]],
    veh_var: ctrl.Antecedent,
    arr_var: ctrl.Antecedent,
    grn_var: ctrl.Consequent,
) -> List[ctrl.Rule]:
    """
    Given a list of [veh_level, arrival_level, green_level], build
    a scikit-fuzzy Rule list.
    """
    rules: List[ctrl.Rule] = []
    for veh_l, arr_l, grn_l in rule_list:
        rules.append(ctrl.Rule(veh_var[veh_l] & arr_var[arr_l], grn_var[grn_l]))
    return rules
