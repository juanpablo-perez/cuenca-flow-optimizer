"""
utils.fuzzy_system
──────────────────
Funciones auxiliares para construir sistemas difusos con scikit-fuzzy.
Porta directamente la lógica de tu antiguo `fuzzy_utils.py`.
"""
from __future__ import annotations
import numpy as np
import skfuzzy as fuzz
from skfuzzy import control as ctrl
from typing import Dict, List


def generar_membresias_fuzzy(funciones: Dict) -> Dict[str, ctrl.Antecedent | ctrl.Consequent]:
    vars_out: Dict[str, ctrl.Antecedent | ctrl.Consequent] = {}

    for nombre, defin in funciones.items():
        lmin, lmax = defin["lmin"], defin["lmax"]
        niveles: List[str] = defin["niveles"]
        n = len(niveles)
        universo = np.linspace(lmin, lmax, 1000)

        var = ctrl.Antecedent(universo, nombre) if nombre != "verde" else ctrl.Consequent(universo, nombre)
        paso = (lmax - lmin) / (n - 1)

        for i, nivel in enumerate(niveles):
            if i == 0:                                    # izquierda
                mf = fuzz.trapmf(universo, [lmin, lmin, lmin + paso, lmin + 2 * paso])
            elif i == n - 1:                              # derecha
                mf = fuzz.trapmf(universo, [lmax - 2 * paso, lmax - paso, lmax, lmax])
            else:                                         # intermedia
                a = lmin + paso * (i - 1)
                b = lmin + paso * i
                c = lmin + paso * (i + 1)
                mf = fuzz.trimf(universo, [a, b, c])
            var[nivel] = mf

        vars_out[nombre] = var
    return vars_out


def crear_reglas_desde_lista(
    reglas_def: List[List[str]],
    vehiculos: ctrl.Antecedent,
    llegada: ctrl.Antecedent,
    verde: ctrl.Consequent,
) -> List[ctrl.Rule]:
    reglas = []
    for v, l, z in reglas_def:
        reglas.append(ctrl.Rule(vehiculos[v] & llegada[l], verde[z]))
    return reglas
