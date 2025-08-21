# src/fuzzylts/utils/stats.py
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
stats.py — Parse and aggregate SUMO tripinfo.xml and emissions.xml across runs,
with CSV caching and ready-to-plot summaries (emissions vs. time).

Requirements
------------
- pandas, numpy, scipy (for the simple CI helper)

Expected runs layout
--------------------
experiments/<controller>_<scenario>_<seed>/
    ├─ tripinfo.xml          (optional)
    └─ emissions.xml[.gz]    (recommended SUMO period = 900 s for 15-min bins)

Outputs
-------
data/experiment_metrics.csv
data/tripinfo.csv
data/emissions_<pollutants>.csv   # wide by timestep: time, CO2, NOx, ...

Notes
-----
- The logic here is intentionally minimal/tolerant to support different SUMO
  versions and run layouts. CSVs are cached for reproducible plotting.
"""

from __future__ import annotations

import gzip
import json
import logging
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Tuple

import numpy as np
import pandas as pd
from scipy.stats import t  # used in ci()

# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

CONFIDENCE: float = 0.95

EXP_DIR: Path = Path("experiments")
DATA_DIR: Path = Path("data").resolve()
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Typical SUMO emissions set: ("CO2", "NOx", "PMx", "CO", "HC", "fuel")
POLLUTANTS_DEFAULT: Tuple[str, ...] = ("CO2",)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _open_maybe_gzip(path: Path):
    """Open a file that may be gzip-compressed.

    Returns:
        A binary file-like object.
    """
    name = path.name.lower()
    return gzip.open(path, "rb") if (name.endswith(".gz") or name.endswith(".gzip")) else open(path, "rb")


def _canonicalize_pollutants(pollutants: Iterable[str]) -> Tuple[str, ...]:
    """Normalize a pollutants iterable: trim, de-duplicate (stable), ensure non-empty."""
    seen: set[str] = set()
    ordered: List[str] = []
    for p in pollutants:
        s = str(p).strip()
        if not s or s in seen:
            continue
        seen.add(s)
        ordered.append(s)
    if not ordered:
        raise ValueError("Pollutant list must not be empty.")
    return tuple(ordered)


def _emissions_target_path(base_dir: Path, pollutants: Sequence[str]) -> Path:
    """Deterministic cache filename for a pollutant set (alphabetical suffix)."""
    suffix = "_".join(sorted({p.strip() for p in pollutants if p.strip()}))
    return base_dir / f"emissions_{suffix}.csv"


def _parse_run_folder_name(run_name: str) -> Tuple[str, str, str]:
    """Extract `(controller, scenario, seed)` from '<controller>_<scenario>_<seed>'.

    Special rules preserved:
      - 'gap' → 'gap_fuzzy' controller.
      - scenario heuristics for 'medium_extended' and 'very_high'.

    Args:
        run_name: Folder name e.g. 'static_low_01'.

    Returns:
        Tuple(controller, scenario, seed) as strings.
    """
    parts = run_name.split("_")
    controller = "gap_fuzzy" if (parts and parts[0] == "gap") else (parts[0] if parts else "unknown")
    seed = parts[-1] if parts else "0"

    # Scenario heuristics preserved from original logic
    if len(parts) >= 3 and parts[-3] == "medium":
        scenario = "medium_extended"
    elif len(parts) >= 3 and parts[-3] == "very":
        scenario = "very_high"
    else:
        scenario = parts[-2] if len(parts) >= 2 else "unknown"

    return controller, scenario, seed


def ci(series: pd.Series, confidence: float = CONFIDENCE) -> Tuple[float, float]:
    """Two-sided Student confidence interval (mean ± CI).

    If n < 2, returns (mean, mean).

    Args:
        series: Values for which to compute the interval.
        confidence: Confidence level (default 0.95).

    Returns:
        (low, high) bounds.
    """
    n = series.count()
    m = series.mean()
    if n < 2:
        return m, m
    sem = series.sem()
    half = sem * t.ppf((1 + confidence) / 2, df=n - 1)
    return m - half, m + half


# ─────────────────────────────────────────────────────────────────────────────
# Experiment metrics (metrics.json)
# ─────────────────────────────────────────────────────────────────────────────

def load_experiment_metrics(exp_dir: Path | str = EXP_DIR, force_reload: bool = False) -> pd.DataFrame:
    """Read/cache `metrics.json` from each run dir → `data/experiment_metrics.csv`.

    Returns:
        DataFrame with the original keys plus columns: ['controller', 'scenario', 'seed'].
    """
    exp_dir = Path(exp_dir)
    target = DATA_DIR / "experiment_metrics.csv"
    if target.exists() and not force_reload:
        return pd.read_csv(target, low_memory=False)

    rows: List[Dict[str, Any]] = []
    for run_dir in exp_dir.iterdir():
        if not run_dir.is_dir():
            continue
        f = run_dir / "metrics.json"
        if not f.exists():
            continue
        try:
            with f.open("r", encoding="utf-8") as fh:
                rec: Dict[str, Any] = json.load(fh)
        except Exception as exc:
            logger.warning("Failed to read %s: %s", f, exc)
            continue

        controller, scenario, seed = _parse_run_folder_name(run_dir.name)
        rec.update({"controller": controller, "scenario": scenario, "seed": seed})
        rows.append(rec)

    df = pd.DataFrame(rows)
    df.to_csv(target, index=False)
    return df


# ─────────────────────────────────────────────────────────────────────────────
# Tripinfo
# ─────────────────────────────────────────────────────────────────────────────

def parse_tripinfo(xml_path: Path) -> pd.DataFrame:
    """Parse `tripinfo.xml` → DataFrame with columns ['arrival', 'waitingTime'] per trip.

    Implementation details:
      - Uses `ElementTree.iterparse` for low memory overhead.
      - Accepts both 'waitingTime' and 'waiting_time' attribute variants.

    Args:
        xml_path: Path to the `tripinfo.xml` file.

    Returns:
        DataFrame with columns ['arrival', 'waitingTime'] (float32).
    """
    out: List[Dict[str, float]] = []
    with xml_path.open("rb") as fh:
        for _, elem in ET.iterparse(fh, events=("end",)):
            if elem.tag != "tripinfo":
                continue
            a = elem.attrib
            arrival = float(a.get("arrival", a.get("arriveTime", "0") or 0))
            waiting = float(a.get("waitingTime", a.get("waiting_time", "0") or 0))
            out.append({"arrival": arrival, "waitingTime": waiting})
            elem.clear()

    df = pd.DataFrame.from_records(out)
    if not df.empty:
        df["arrival"] = pd.to_numeric(df["arrival"], errors="coerce").astype("float32")
        df["waitingTime"] = pd.to_numeric(df["waitingTime"], errors="coerce").astype("float32")
    return df


def load_all_tripinfo(exp_dir: Path | str = EXP_DIR, force_reload: bool = False) -> pd.DataFrame:
    """Aggregate all runs' `tripinfo.xml` into `data/tripinfo.csv`.

    Output schema:
        ['controller', 'scenario', 'run', 'arrival', 'waitingTime']

    Notes:
        - `run` is an integer index derived from enumeration order.
    """
    exp_dir = Path(exp_dir)
    target = DATA_DIR / "tripinfo.csv"
    if target.exists() and not force_reload:
        return pd.read_csv(target, low_memory=False)

    frames: List[pd.DataFrame] = []
    for idx, run_dir in enumerate(sorted(p for p in exp_dir.iterdir() if p.is_dir())):
        xml_file = run_dir / "tripinfo.xml"
        if not xml_file.exists():
            continue
        try:
            df = parse_tripinfo(xml_file)
        except Exception as exc:
            logger.warning("Failed to parse %s: %s", xml_file, exc)
            continue
        if df.empty:
            continue

        controller, scenario, _seed = _parse_run_folder_name(run_dir.name)
        df["controller"] = controller
        df["scenario"] = scenario
        df["run"] = idx
        frames.append(df)

    full = (
        pd.concat(frames, ignore_index=True)
        if frames
        else pd.DataFrame(columns=["controller", "scenario", "run", "arrival", "waitingTime"])
    )

    # Dtypes
    if not full.empty:
        full["controller"] = full["controller"].astype("category")
        full["scenario"] = full["scenario"].astype("category")
        full["run"] = pd.to_numeric(full["run"], errors="coerce").astype("int32")

    full.to_csv(target, index=False)
    return full


# ─────────────────────────────────────────────────────────────────────────────
# Emissions (wide per timestep: time, <pollutants...>)
# ─────────────────────────────────────────────────────────────────────────────

def parse_emissions(xml_path: Path, pollutants: Sequence[str]) -> pd.DataFrame:
    """Parse `emissions.xml` (or `.gz`), summing vehicles per `<timestep>`.

    Returns a wide DataFrame:
        ['time', *pollutants]

    With SUMO `--device.emissions.period=900`, each 'time' is a 15-minute bin.

    Args:
        xml_path: Path to emissions file (`.xml` or `.xml.gz`).
        pollutants: Sequence of pollutant names to extract (e.g., ["CO2"]).

    Returns:
        DataFrame with float32 columns and one row per timestep.
    """
    pols = _canonicalize_pollutants(pollutants)

    # Accumulators: time (s) -> vector[pollutants]
    acc: Dict[float, np.ndarray] = {}

    with _open_maybe_gzip(xml_path) as fh:
        context = ET.iterparse(fh, events=("start", "end"))
        _, root = next(context)  # prime the iterator
        for event, elem in context:
            if event == "end" and elem.tag == "timestep":
                t_s = float(elem.attrib.get("time", "0") or 0)
                vec = acc.get(t_s)
                if vec is None:
                    vec = np.zeros(len(pols), dtype="float64")
                    acc[t_s] = vec

                # Sum all vehicles' pollutant attributes for this timestep
                for v in elem:
                    if v.tag != "vehicle":
                        continue
                    a = v.attrib
                    for i, pol in enumerate(pols):
                        val = a.get(pol)
                        if val is not None:
                            try:
                                vec[i] += float(val)
                            except ValueError:
                                pass

                elem.clear()
                root.clear()

    if not acc:
        return pd.DataFrame(columns=["time", *pols])

    times = sorted(acc.keys())
    data: Dict[str, List[float]] = {"time": times}
    for i, pol in enumerate(pols):
        data[pol] = [acc[t][i] for t in times]

    df = pd.DataFrame(data)
    # Compact dtypes
    df["time"] = pd.to_numeric(df["time"], errors="coerce").astype("float32")
    for pol in pols:
        df[pol] = pd.to_numeric(df[pol], errors="coerce").astype("float32")
    return df


def load_all_emissions(
    exp_dir: Path | str = EXP_DIR,
    pollutants: Sequence[str] | None = None,
    force_reload: bool = False,
) -> pd.DataFrame:
    """Walk all runs, parse emissions into a wide per-timestep DF, and append metadata.

    Caches to:
        data/emissions_<pollutants>.csv

    Output schema:
        ['time', *pollutants, 'controller', 'scenario', 'run']

    Notes:
        - `run` is kept as a string to preserve the exact folder token.
    """
    exp_dir = Path(exp_dir)
    pols = _canonicalize_pollutants(pollutants or POLLUTANTS_DEFAULT)

    target = _emissions_target_path(DATA_DIR, pols)
    if target.exists() and not force_reload:
        return pd.read_csv(target, low_memory=False)

    frames: List[pd.DataFrame] = []
    for run_dir in sorted(p for p in exp_dir.iterdir() if p.is_dir()):
        xml_file = run_dir / "emissions.xml"
        if not xml_file.exists():
            gz = run_dir / "emissions.xml.gz"
            if not gz.exists():
                continue
            xml_file = gz

        try:
            df = parse_emissions(xml_file, pollutants=pols)
        except Exception as exc:
            logger.warning("Failed to parse %s: %s", xml_file, exc)
            continue

        controller, scenario, seed = _parse_run_folder_name(run_dir.name)
        df["controller"] = controller
        df["scenario"] = scenario
        df["run"] = seed
        frames.append(df)

    out = (
        pd.concat(frames, ignore_index=True)
        if frames
        else pd.DataFrame(columns=["time", *pols, "controller", "scenario", "run"])
    )

    # Dtypes
    if not out.empty:
        out["controller"] = out["controller"].astype("category")
        out["scenario"] = out["scenario"].astype("category")
        out["run"] = out["run"].astype("string[python]")  # preserve token verbatim

    out.to_csv(target, index=False)
    return out


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    logger.info("== Caching experiment metrics ...")
    df_metrics = load_experiment_metrics(force_reload=True)
    logger.info("Saved %s (%d rows)", DATA_DIR / "experiment_metrics.csv", len(df_metrics))

    logger.info("== Caching all tripinfo ...")
    df_trip = load_all_tripinfo(force_reload=True)
    logger.info("Saved %s (%d rows)", DATA_DIR / "tripinfo.csv", len(df_trip))

    logger.info("== Loading all emissions (wide DF by timestep) ...")
    df_em_all = load_all_emissions(force_reload=True, pollutants=POLLUTANTS_DEFAULT)
    logger.info("Saved %s (%d rows)", "<data/emissions_*.csv>", len(df_em_all))