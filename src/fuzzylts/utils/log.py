from __future__ import annotations
import logging
import sys

_FMT = "%(asctime)s | %(levelname)-8s | %(name)s: %(message)s"
_DATEFMT = "%Y-%m-%d %H:%M:%S"

def get_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """Devuelve un logger con formateo homogéneo en todo el proyecto."""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger  # ya configurado
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(_FMT, datefmt=_DATEFMT))
    logger.addHandler(handler)
    logger.setLevel(level)
    logger.propagate = False
    return logger


def imprimir_limites_por_semaforo_y_fase(fases_lanes_dict, limites_globales_lanes):
    print("=== LÍMITES POR SEMÁFORO Y FASE (sumando cantidades, promediando velocidad y tasa) ===")

    for semaforo_id, fases in fases_lanes_dict.items():
        print(f"\n📍 Semáforo: {semaforo_id}")
        
        for fase_id in [0, 2]:  # Solo fase 0 y fase 2
            lanes = fases.get(fase_id, [])
            if not lanes:
                print(f"  Fase {fase_id}: Sin carriles definidos.")
                continue

            suma = {
                "vehiculos": 0,
                "movimiento": 0,
                "detenidos": 0,
                "velocidad_prom_sum": 0.0,
                "tasa_llegada_sum": 0.0,
                "n": 0  # Número de carriles con datos válidos
            }

            for lane_id in lanes:
                if lane_id in limites_globales_lanes:
                    lim = limites_globales_lanes[lane_id]
                    suma["vehiculos"] += lim["vehiculos_max"]
                    suma["movimiento"] += lim["movimiento_max"]
                    suma["detenidos"] += lim["detenidos_max"]
                    suma["velocidad_prom_sum"] += lim["velocidad_prom_max"]
                    suma["tasa_llegada_sum"] += lim["tasa_llegada_max"]
                    suma["n"] += 1

            if suma["n"] > 0:
                vel_prom = suma["velocidad_prom_sum"] / suma["n"]
                tasa_prom = suma["tasa_llegada_sum"] / suma["n"]
            else:
                vel_prom = 0.0
                tasa_prom = 0.0

            print(f"  Fase {fase_id}:")
            print(f"    Vehículos    : {suma['vehiculos']}")
            print(f"    Movimiento   : {suma['movimiento']}")
            print(f"    Detenidos    : {suma['detenidos']}")
            print(f"    Vel. Promedio: {vel_prom:.2f} m/s")
            print(f"    Tasa Llegada : {tasa_prom:.3f} veh/s")


def imprimir_limites_globales(limites_globales_lanes):
    globales = {
        "vehiculos_min": float('inf'),
        "vehiculos_max": float('-inf'),
        "movimiento_min": float('inf'),
        "movimiento_max": float('-inf'),
        "detenidos_min": float('inf'),
        "detenidos_max": float('-inf'),
        "velocidad_prom_min": float('inf'),
        "velocidad_prom_max": float('-inf'),
        "tasa_llegada_min": float('inf'),
        "tasa_llegada_max": float('-inf')
    }

    for lim in limites_globales_lanes.values():
        for k in globales:
            if "min" in k:
                globales[k] = min(globales[k], lim[k])
            else:
                globales[k] = max(globales[k], lim[k])

    print("=== LÍMITES GENERALES ===")
    print(f"  Vehículos    : {globales['vehiculos_min']} → {globales['vehiculos_max']}")
    print(f"  Movimiento   : {globales['movimiento_min']} → {globales['movimiento_max']}")
    print(f"  Detenidos    : {globales['detenidos_min']} → {globales['detenidos_max']}")
    print(f"  Vel. Promedio: {globales['velocidad_prom_min']:.2f} → {globales['velocidad_prom_max']:.2f}")
    print(f"  Tasa Llegada : {globales['tasa_llegada_min']:.3f} → {globales['tasa_llegada_max']:.3f}")

