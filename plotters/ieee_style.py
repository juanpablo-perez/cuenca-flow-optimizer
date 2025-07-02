# plotters/ieee_style.py
import seaborn as sns
import matplotlib as mpl

def set_plot_style():
    """
    Configure a global, print-ready IEEE style for all figures.
    """
    sns.set_theme(
        context="paper",
        style="white",
        font="DejaVu Sans",
        palette="colorblind",
        rc={
            "axes.edgecolor": "#444444",
            "axes.linewidth": 0.7,
            "axes.grid": True,
            "grid.alpha": 0.18,
            "grid.linestyle": "--",
            "axes.titlesize": 16,
            "axes.titleweight": "bold",
            "axes.labelsize": 12,
            "xtick.labelsize": 11,
            "ytick.labelsize": 11,
            "legend.fontsize": 9,
            "legend.frameon": False,
            "lines.linewidth": 1.5,
            "lines.markersize": 4,
            "figure.dpi": 120,
        }
    )
    # turn off top/right spines
    mpl.rcParams["axes.spines.top"] = False
    mpl.rcParams["axes.spines.right"] = False

# Up to 8 distinct colors
PALETTE_ARCH = sns.color_palette("colorblind", 8)
MARKERS_ESC  = ["o", "s", "D", "^", "v", "P", "X", "d"]

# More intense palette (e.g. for bar charts)
INTENSE_ARCH_PALETTE = sns.color_palette("Set1", 8)
INTENSE_MARKERS_ESC  = MARKERS_ESC

def arch_color(idx: int):
    """Get a consistent color for the idx-th architecture."""
    return PALETTE_ARCH[idx % len(PALETTE_ARCH)]

def esc_marker(idx: int):
    """Get a consistent marker for the idx-th scenario."""
    return MARKERS_ESC[idx % len(MARKERS_ESC)]

def arch_color_intense(idx: int):
    """Get a more saturated color for bar charts or highlights."""
    return INTENSE_ARCH_PALETTE[idx % len(INTENSE_ARCH_PALETTE)]

def esc_marker_intense(idx: int):
    """Alternate marker set (unused by defaults, but available)."""
    return INTENSE_MARKERS_ESC[idx % len(INTENSE_MARKERS_ESC)]
