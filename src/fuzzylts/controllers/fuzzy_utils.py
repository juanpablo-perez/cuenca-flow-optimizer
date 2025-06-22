import numpy as np
import skfuzzy as fuzz
from skfuzzy import control as ctrl

def generar_membresias_fuzzy(funciones):
    entradas_salidas = {}

    for nombre, definicion in funciones.items():
        lmin = definicion["lmin"]
        lmax = definicion["lmax"]
        niveles = definicion["niveles"]
        n = len(niveles)

        universo = np.linspace(lmin, lmax, 1000)  # más suave que np.arange
        variable = ctrl.Antecedent(universo, nombre) if nombre != "verde" else ctrl.Consequent(universo, nombre)

        paso = (lmax - lmin) / (n - 1)

        for i, nivel in enumerate(niveles):
            if i == 0:
                a = lmin
                b = lmin
                c = lmin + paso
                d = lmin + paso * 2
                mf = fuzz.trapmf(universo, [a, b, c, d])
            elif i == n - 1:
                a = lmax - paso * 2
                b = lmax - paso
                c = lmax
                d = lmax
                mf = fuzz.trapmf(universo, [a, b, c, d])
            else:
                a = lmin + paso * (i - 1)
                b = lmin + paso * i
                c = lmin + paso * (i + 1)
                mf = fuzz.trimf(universo, [a, b, c])

            variable[nivel] = mf

        entradas_salidas[nombre] = variable

    return entradas_salidas

def generar_reglas_automaticas(vehiculos_var, llegada_var, verde_var,
                                niveles_vehiculos, niveles_llegada, niveles_verde):
    reglas = []

    for i, nivel_veh in enumerate(niveles_vehiculos):
        for j, nivel_lleg in enumerate(niveles_llegada):
            intensidad = int((i + j) / (len(niveles_vehiculos) + len(niveles_llegada) - 2) * (len(niveles_verde) - 1))
            nivel_verde = niveles_verde[intensidad]
            regla = ctrl.Rule(
                vehiculos_var[nivel_veh] & llegada_var[nivel_lleg],
                verde_var[nivel_verde]
            )
            reglas.append(regla)

    return reglas

def crear_reglas_desde_lista(reglas_definidas, vehiculos, llegada, verde):
    reglas = []
    for v, l, salida in reglas_definidas:
        regla = ctrl.Rule(vehiculos[v] & llegada[l], verde[salida])
        reglas.append(regla)
    return reglas
