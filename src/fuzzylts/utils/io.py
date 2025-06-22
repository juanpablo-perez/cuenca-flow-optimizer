import pandas as pd
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict

# ── tripinfo parser robusto ────────────────────────────────────────────────
def tripinfo_xml_to_df(xml_file: Path) -> pd.DataFrame:
    root = ET.parse(xml_file).getroot()
    rows = []
    for tag in root.findall("tripinfo"):
        rows.append(tag.attrib)
    df = pd.DataFrame(rows)

    # Convertir numéricos columna a columna para evitar FutureWarning
    NUMERIC_COLS = [
        "depart", "arrival", "duration",
        "waitingTime", "waiting_time", "routeLength", "speed",
    ]
    for col in NUMERIC_COLS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


# ── stats parser súper-permisivo ──────────────────────────────────────────
def stats_xml_to_dict(xml_file: Path) -> Dict[str, float]:
    """
    Devuelve solo pares nombre → float de statistics.xml.
    ➊ Lee atributos numéricos de la raíz  <statistics …>
    ➋ Captura 'teleports' si viene como atributo o sub-tag
    """
    def _num(s: str) -> bool:
        try:
            float(s); return True
        except ValueError:
            return False

    root = ET.parse(xml_file).getroot()
    attrs: Dict[str, float] = {k: float(v) for k, v in root.attrib.items() if _num(v)}

    # teleports puede estar como atributo o como sub-tag
    if "teleports" in root.attrib and _num(root.attrib["teleports"]):
        attrs["teleports_total"] = float(root.attrib["teleports"])

    tele = root.find(".//teleports")
    if tele is not None:
        # atributo count
        if "count" in tele.attrib and _num(tele.attrib["count"]):
            attrs["teleports_total"] = float(tele.attrib["count"])
        # texto puro
        elif tele.text and _num(tele.text.strip()):
            attrs["teleports_total"] = float(tele.text.strip())
    
    step = root.find(".//step")
    if step is not None and _num(step.attrib.get("time", "0")):
        attrs["step"] = float(step.attrib["time"])

    return attrs

