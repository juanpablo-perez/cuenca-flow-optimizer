#!/usr/bin/env python3
"""
stats.py – Utilities to parse SUMO tripinfo.xml and emissions.xml files,
cache results as CSV, aggregate experiment metrics, and load all data across
controllers and scenarios.
"""
from pathlib import Path
from typing import Any, Dict, List, Tuple
import xml.etree.ElementTree as ET

import pandas as pd
import numpy as np
from scipy.stats import t

# Default confidence level for intervals (e.g. 95%)
CONFIDENCE = 0.95

# Directories
EXP_DIR = Path("experiments")
DATA_DIR = Path().resolve() / "data"
DATA_DIR.mkdir(exist_ok=True)


def load_experiment_metrics(exp_dir: Path = EXP_DIR) -> pd.DataFrame:
    """
    Load or cache aggregated metrics from metrics.json files in `exp_dir`.
    Returns a DataFrame with one row per run including all metrics and parsed
    controller, scenario, seed fields.
    """
    target = DATA_DIR / 'experiment_metrics.csv'
    if target.exists():
        return pd.read_csv(target)

    records: List[Dict[str, Any]] = []
    for run_dir in exp_dir.iterdir():
        if not run_dir.is_dir():
            continue
        metrics_file = run_dir / "metrics.json"
        if not metrics_file.exists():
            continue
        rec = pd.read_json(metrics_file, typ="series").to_dict()
        parts = run_dir.name.split("_")
        rec['controller'] = 'gap_fuzzy' if parts[0] == 'gap' else parts[0]
        scen = parts[-3]
        rec['scenario'] = ('medium_extended' if scen == 'medium'
                           else ('very_high' if scen == 'very' else parts[-2]))
        try:
            rec['seed'] = int(parts[-1])
        except ValueError:
            rec['seed'] = parts[-1]
        records.append(rec)

    df = pd.DataFrame(records)
    df.to_csv(target, index=False)
    return df


def ci(series: pd.Series, confidence: float = CONFIDENCE) -> Tuple[float, float]:
    """
    Compute two-sided confidence interval for a pandas Series.
    Returns (lower_bound, upper_bound). If insufficient data, returns (mean, mean).
    """
    n = series.count()
    m = series.mean()
    if n < 2:
        return m, m
    sem = series.sem()
    h = sem * t.ppf((1 + confidence) / 2, df=n - 1)
    return m - h, m + h


def parse_tripinfo(xml_path: Path) -> pd.DataFrame:
    """
    Parse a single tripinfo.xml and return DataFrame with ['time','waitingTime'] per trip.
    """
    records: List[Dict[str, float]] = []
    for _, elem in ET.iterparse(xml_path, events=("end",)):
        if elem.tag == 'tripinfo':
            time_arr = float(elem.attrib.get('arrival', elem.attrib.get('arriveTime', 0)))
            wait_t = float(elem.attrib.get('waitingTime', elem.attrib.get('waiting_time', 0)))
            records.append({'time': time_arr, 'waitingTime': wait_t})
            elem.clear()
    return pd.DataFrame.from_records(records)


def load_tripinfo(controller: str,
                  scenario: str,
                  exp_dir: Path = EXP_DIR,
                  force_reload: bool = False) -> pd.DataFrame:
    """
    Load or cache tripinfo data for a controller/scenario.
    Returns a DataFrame with columns ['time','waitingTime','run'].
    """
    csv_path = DATA_DIR / f"tripinfo_{controller}_{scenario}.csv"
    if csv_path.exists() and not force_reload:
        return pd.read_csv(csv_path)

    dfs: List[pd.DataFrame] = []
    for run_idx, run_dir in enumerate(exp_dir.glob(f"{controller}_{scenario}_*")):
        xml_file = run_dir / 'tripinfo.xml'
        if not xml_file.exists():
            continue
        df = parse_tripinfo(xml_file)
        df['run'] = run_idx
        dfs.append(df)

    result = pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()
    result.to_csv(csv_path, index=False)
    return result


def parse_emissions(xml_path: Path, pollutant: str) -> pd.DataFrame:
    """
    Parse a single emissions.xml and return DataFrame with ['time', pollutant] per timestep.
    """
    records: List[Dict[str, float]] = []
    for _, elem in ET.iterparse(xml_path, events=("end",)):
        if elem.tag == 'timestep':
            t_sec = float(elem.attrib.get('time', 0))
            total = sum(float(v.attrib.get(pollutant, 0)) for v in elem.iterfind('vehicle'))
            records.append({'time': t_sec, pollutant: total})
            elem.clear()
    return pd.DataFrame.from_records(records)


def load_emissions(controller: str,
                   scenario: str,
                   pollutant: str = 'CO2',
                   exp_dir: Path = EXP_DIR,
                   force_reload: bool = False) -> pd.DataFrame:
    """
    Load or cache emissions data for a controller/scenario and pollutant.
    Returns DataFrame with ['time', pollutant, 'run'].
    """
    csv_path = DATA_DIR / f"emissions_{pollutant.lower()}_{controller}_{scenario}.csv"
    if csv_path.exists() and not force_reload:
        return pd.read_csv(csv_path)

    dfs: List[pd.DataFrame] = []
    for run_idx, run_dir in enumerate(exp_dir.glob(f"{controller}_{scenario}_*")):
        xml_file = run_dir / 'emissions.xml'
        if not xml_file.exists():
            continue
        df = parse_emissions(xml_file, pollutant)
        df['run'] = run_idx
        dfs.append(df)

    result = pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()
    result.to_csv(csv_path, index=False)
    return result


def load_all_tripinfo(force_reload: bool = False) -> pd.DataFrame:
    """
    Load **all** tripinfo.xml runs under `experiments/`.  
    Returns a DataFrame with columns:
      ['controller','scenario','run','arrival','waitingTime']  
    Caches in data/all_tripinfo.csv (unless force_reload=True).
    """
    target = DATA_DIR / "tripinfo.csv"
    if target.exists() and not force_reload:
        return pd.read_csv(target)

    records: List[pd.DataFrame] = []
    for run_idx, run in enumerate(Path("experiments").glob("*_*_*")):
        xml_file = run / "tripinfo.xml"
        if not xml_file.exists():
            continue

        # parse with pandas
        df = pd.read_xml(xml_file, xpath="//tripinfo")
        if "waitingTime" not in df:
            df = df.rename(columns={"waiting_time": "waitingTime"})
        df = df[["arrival", "waitingTime"]].copy()

        # extract controller/scenario from folder name
        parts = run.name.split("_")
        controller = parts[0] if parts[0] != "gap" else "gap_fuzzy"
        scen = parts[-3]
        df['scenario'] = ('medium_extended' if scen == 'medium'
                           else ('very_high' if scen == 'very' else parts[-2]))
        df["controller"] = controller
        df["run"]        = run_idx

        records.append(df)

    if not records:
        full = pd.DataFrame(columns=["controller","scenario","run","arrival","waitingTime"])
    else:
        full = pd.concat(records, ignore_index=True)

    full.to_csv(target, index=False)
    return full


def load_all_emissions(pollutant: str = 'CO2',
                       exp_dir: Path = EXP_DIR,
                       force_reload: bool = False) -> pd.DataFrame:
    """
    Load or cache all emissions data across controllers and scenarios for a pollutant.
    Returns DataFrame with ['time', pollutant, 'controller','scenario','run_id'].
    """
    csv_path = DATA_DIR / f"emissions_{pollutant.lower()}.csv"
    if csv_path.exists() and not force_reload:
        return pd.read_csv(csv_path)

    records: List[pd.DataFrame] = []
    for run_dir in exp_dir.iterdir():
        xml_file = run_dir / 'emissions.xml'
        if not xml_file.exists():
            continue
        parts = run_dir.name.split("_")
        controller = 'gap_fuzzy' if parts[0] == 'gap' else parts[0]
        scen = parts[-3]
        scenario = ('medium_extended' if scen == 'medium'
                    else ('very_high' if scen == 'very' else parts[-2]))
        df = parse_emissions(xml_file, pollutant)
        df['controller'] = controller
        df['scenario'] = scenario
        df['run'] = int(run_dir.name.split("_")[-1])
        records.append(df)

    result = pd.concat(records, ignore_index=True) if records else pd.DataFrame()
    result.to_csv(csv_path, index=False)
    return result


# ----------------------------------------------------------------------------
# CLI to cache all CSVs at once
# ----------------------------------------------------------------------------
if __name__ == "__main__":
    print("Caching all metrics data...")
    df_metrics = load_experiment_metrics()
    print(f"Saved {DATA_DIR / 'experiment_metrics.csv'} with {len(df_metrics)} records \n")
    print("Caching all tripinfo data...")
    df_trip = load_all_tripinfo(force_reload=True)
    print(f"Saved {DATA_DIR / 'all_tripinfo.csv'} with {len(df_trip)} records \n")

    pollutants = ['CO2']  # extend list if needed
    for p in pollutants:
        print(f"Caching all emissions for pollutant {p}...")
        df_em = load_all_emissions(p, force_reload=True)
        print(f"Saved {DATA_DIR / f'all_emissions_{p.lower()}.csv'} with {len(df_em)} records")
