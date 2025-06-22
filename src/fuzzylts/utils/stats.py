"""Cálculo de métricas agregadas + IC 95 %."""
from __future__ import annotations
from pathlib import Path
from typing import Any, Dict, List, Tuple
import pandas as pd
from scipy.stats import t

_CONF = 0.95

def load_experiment_metrics() -> pd.DataFrame:
    """Carga todos los metrics.json dentro de experiments/*."""
    records: List[Dict[str, Any]] = []
    for run in Path("experiments").iterdir():
        mfile = run / "metrics.json"
        if mfile.exists():
            rec = pd.read_json(mfile, typ="series").to_dict()
            ctrl, scn, seed, *_ = run.name.split("_")
            rec.update(controller=ctrl, scenario=scn, seed=int(seed))
            records.append(rec)
    return pd.DataFrame(records)

def ci(series: pd.Series) -> Tuple[float, float]:
    n = len(series)
    mean, sem = series.mean(), series.sem()
    h = sem * t.ppf((1 + _CONF) / 2, n - 1)
    return mean - h, mean + h
