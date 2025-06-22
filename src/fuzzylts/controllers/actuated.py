"""
controllers.actuated  –  modo *observer*
──────────────────────────────────────────
• NO modifica la duración de los semáforos.
• Registra fases 0 y 2 en CSV exactamente como tu script standalone.
• El CSV se guarda en FUZZYLTS_RUN_DIR/datos_semaforos_actuated.csv.
"""

from __future__ import annotations
import csv, statistics, os
from pathlib import Path
from typing import Dict, List
import traci
from fuzzylts.utils.log import get_logger

log = get_logger(__name__)

SEMAFOROS = [
    "2496228891",
    "cluster_12013799525_12013799526_2496228894",
    "cluster_12013799527_12013799528_2190601967",
    "cluster_12013799529_12013799530_473195061",
]

FASES_LANES: Dict[str, Dict[int, List[str]]] = {
    "2496228891": {
        0: ["337277951#3_0", "337277951#3_1", "337277951#1_0", "337277951#1_1", "337277951#4_0", "337277951#4_1", "337277951#2_0", "337277951#2_1", "49217102_0"], 
        2: ["567060342#1_0", "567060342#0_0"], 
    },
    "cluster_12013799525_12013799526_2496228894": {
        0: ["42143912#5_0", "42143912#3_0", "42143912#4_0"],
        2: ["337277973#1_0", "337277973#1_1", "337277973#0_1", "337277973#0_0", "567060342#1_0", "567060342#0_0"]
    },
    "cluster_12013799527_12013799528_2190601967": {
        0: ["40668087#1_0"],
        2: ["337277981#1_1", "337277981#1_0", "337277981#2_1", "337277981#2_0", "42143912#5_0", "42143912#3_0", "42143912#4_0"]
    },
    "cluster_12013799529_12013799530_473195061": {
        0: ["49217102_0"],
        2: ["337277970#1_0", "337277970#1_1", "40668087#1_0"]
    }
}

RUN_DIR  = Path(os.environ.get("FUZZYLTS_RUN_DIR", "."))
CSV_FILE = RUN_DIR / "datos_semaforos_actuated.csv"

_state: Dict[str, Dict[str, int]] = {tls: {"fase": -1, "inicio": 0} for tls in SEMAFOROS}
_hist = []
_min_green, _max_green = float("inf"), float("-inf")

def _log(fase: int, tls: str, dur: int, vehs: int, ini: int) -> None:
    global _min_green, _max_green
    _hist.append({
        "tiempo": traci.simulation.getTime() - dur,
        "semaforo_id": tls,
        "fase": fase,
        "duracion": dur,
        "vehiculos_en_carriles": vehs,
        "paso_inicio": ini,
    })
    _min_green = min(_min_green, dur)
    _max_green = max(_max_green, dur)

def get_phase_duration(tls_id: str) -> int:
    """
    Devuelve 0 para indicar que **no** se debe modificar la duración.
    Solo registra la fase que acaba de terminar.
    """
    now  = int(traci.simulation.getCurrentTime() / 1000)
    fase = traci.trafficlight.getPhase(tls_id)

    prev = _state[tls_id]
    if prev["fase"] in (0, 2):
        dur  = now - prev["inicio"]
        lanes = FASES_LANES[tls_id][prev["fase"]]
        vehs  = sum(traci.lane.getLastStepVehicleNumber(l) for l in lanes)
        _log(prev["fase"], tls_id, dur, vehs, prev["inicio"])

    prev.update({"fase": fase, "inicio": now})
    return 0  # <<– NUNCA se usará

# Guardar CSV al salir
import atexit
@atexit.register
def _dump():
    if not _hist:
        return
    CSV_FILE.parent.mkdir(parents=True, exist_ok=True)
    with CSV_FILE.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=_hist[0].keys())
        w.writeheader()
        w.writerows(_hist)

    verdes = [h["duracion"] for h in _hist]
    media  = statistics.mean(verdes)
    var    = statistics.variance(verdes) if len(verdes) > 1 else 0
    try: moda = statistics.mode(verdes)
    except statistics.StatisticsError: moda = "No única"
    log.info("Actuated-observer  min:%s max:%s mean:%.2f moda:%s var:%.2f",
             _min_green, _max_green, media, moda, var)
