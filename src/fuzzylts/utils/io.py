# src/fuzzylts/utils/io.py
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
I/O utilities for SUMO outputs and network XMLs.

This module provides:
- `load_xml_root`: transparent loading of plain `.xml` or gzip-compressed `.xml.gz`.
- `tripinfo_xml_to_df`: robust parser for `tripinfo.xml` into a typed `pandas.DataFrame`.
- `stats_xml_to_dict`: permissive parser for `statistics.xml` into a numeric dict.

Notes
-----
- Parsing is intentionally tolerant of minor schema variations across SUMO versions.
- Numeric coercion uses `errors="coerce"` for resilience; callers should handle NaNs.
"""

from __future__ import annotations

import gzip
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, Iterable, List

import pandas as pd


# ─────────────────────────────────────────────────────────────────────────────
# XML loader
# ─────────────────────────────────────────────────────────────────────────────

def load_xml_root(path: str | Path) -> ET.Element:
    """Open `.xml` or `.xml.gz` and return the XML root element.

    The compression check is based on the **suffix** (exact `.gz`) or the full
    joined suffix chain (e.g., `.net.xml.gz`).

    Parameters
    ----------
    path : str | Path
        Path to the XML file (optionally gzip-compressed).

    Returns
    -------
    xml.etree.ElementTree.Element
        Root element of the parsed XML document.
    """
    p = Path(path)
    is_gz = p.suffix == ".gz" or "".join(p.suffixes).endswith(".gz")
    if is_gz:
        with gzip.open(p, "rb") as f:
            return ET.parse(f).getroot()
    return ET.parse(str(p)).getroot()


# ─────────────────────────────────────────────────────────────────────────────
# tripinfo.xml → DataFrame
# ─────────────────────────────────────────────────────────────────────────────

def tripinfo_xml_to_df(xml_file: Path) -> pd.DataFrame:
    """Parse `tripinfo.xml` into a DataFrame with best-effort numeric typing.

    Behavior
    --------
    - Collects every `<tripinfo ...>` tag's attributes into rows.
    - Attempts numeric conversion for frequently used columns:
      `depart`, `arrival`, `duration`, `waitingTime`, `waiting_time`,
      `routeLength`, `speed`. Non-existing columns are ignored.

    Parameters
    ----------
    xml_file : Path
        Path to `tripinfo.xml` (plain or gzipped).

    Returns
    -------
    pandas.DataFrame
        One row per `<tripinfo>` with columns taken from attributes. Selected
        columns are coerced to numeric (`errors="coerce"`).
    """
    root = load_xml_root(path=xml_file)
    rows: List[Dict[str, str]] = [tag.attrib for tag in root.findall("tripinfo")]
    df = pd.DataFrame(rows)

    # Convert numeric columns one by one (avoids FutureWarning on mixed dtypes)
    NUMERIC_COLS: Iterable[str] = (
        "depart",
        "arrival",
        "duration",
        "waitingTime",
        "waiting_time",
        "routeLength",
        "speed",
    )
    for col in NUMERIC_COLS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    return df


# ─────────────────────────────────────────────────────────────────────────────
# statistics.xml → Dict[str, float]
# ─────────────────────────────────────────────────────────────────────────────

def stats_xml_to_dict(xml_file: Path) -> Dict[str, float]:
    """Parse `statistics.xml` into a numeric dictionary (permissive).

    Behavior
    --------
    1) Reads numeric attributes from the root `<statistics ...>`.
    2) Extracts **teleports** if present as:
       - root attribute `teleports`, or
       - `<teleports count="...">`, or
       - `<teleports>123</teleports>` textual content.
    3) Extracts the latest `<step time="...">` attribute (as `step`).

    Parameters
    ----------
    xml_file : Path
        Path to `statistics.xml` (plain or gzipped).

    Returns
    -------
    Dict[str, float]
        Mapping of metric name → numeric value (floats only).

    Notes
    -----
    - Keys used:
        * `teleports_total` for the consolidated teleports count.
        * `step` for the last reported simulation time (if available).
    """

    def _is_number(s: str) -> bool:
        try:
            float(s)
            return True
        except (TypeError, ValueError):
            return False

    root = load_xml_root(path=xml_file)

    # Numeric root attributes
    attrs: Dict[str, float] = {k: float(v) for k, v in root.attrib.items() if _is_number(v)}

    # Teleports (as root attribute)
    if "teleports" in root.attrib and _is_number(root.attrib["teleports"]):
        attrs["teleports_total"] = float(root.attrib["teleports"])

    # Teleports (as sub-tag, by attribute or text)
    tele = root.find(".//teleports")
    if tele is not None:
        if "count" in tele.attrib and _is_number(tele.attrib["count"]):
            attrs["teleports_total"] = float(tele.attrib["count"])
        elif tele.text and _is_number(tele.text.strip()):
            attrs["teleports_total"] = float(tele.text.strip())

    # Last step time (if present)
    step = root.find(".//step")
    if step is not None and _is_number(step.attrib.get("time", "0")):
        attrs["step"] = float(step.attrib["time"])

    return attrs


__all__ = ["load_xml_root", "tripinfo_xml_to_df", "stats_xml_to_dict"]
