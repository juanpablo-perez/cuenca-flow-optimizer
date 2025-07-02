"""
plot_phase_distribution.py – Histogram of observed green durations.
-------------------------------------------------------------------
Run   python -m plotters.plot_phase_distribution path/to/experiments/<run_id>
"""
import sys
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt

if len(sys.argv) != 2:
    sys.exit("Provide one run directory.")
run_dir = Path(sys.argv[1])

# The file name depends on controller type
csv_candidates = list(run_dir.glob("data_tls_*.csv")) + list(run_dir.glob("datos_semaforos_*.csv"))
if not csv_candidates:
    sys.exit("No phase CSV found in run directory.")
csv_path = csv_candidates[0]

df = pd.read_csv(csv_path)
green = df[df.phase.isin([0, 2])]["green_duration"]  # col name identical in all logs

fig, ax = plt.subplots(figsize=(6,4))
ax.hist(green, bins=20, edgecolor="black")
ax.set_xlabel("Green duration [s]")
ax.set_ylabel("Frequency")
ax.set_title(f"Green-phase distribution – {run_dir.name}")
fig.tight_layout()
fig.savefig(run_dir / "green_hist.png", dpi=300)
print("✓ green_hist.png written")
