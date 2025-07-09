# plotters/ieee_style.py
"""
Centralized, IEEE-compliant plotting style definitions.

Use `set_ieee_style()` at the top of each script to apply:
  – Times New Roman fonts
  – IEEE-recommended font sizes (8–10 pt)
  – Single-column / double-column figure widths
  – 300 dpi output
  – Clean grid, inward ticks, no top/right spines
  – Consistent color & marker palettes

Example:
    from plotters.ieee_style import set_ieee_style, new_figure
    set_ieee_style()
    fig, ax = new_figure(columns=1)   # single-column width
    ax.plot(x, y, label="…")
    …
"""
import matplotlib as mpl
import matplotlib.pyplot as plt

# ── IEEE figure dimensions (in inches) ───────────────────────────────────
COLUMN_WIDTH        = 3.5   # single-column width in IEEE journals
DOUBLE_COLUMN_WIDTH = 7.16  # double-column width
ASPECT_RATIO        = 0.66  # height = width * aspect_ratio

# ── Font families & sizes (in points) ────────────────────────────────────
BASE_FONT_SIZE    = 11     # default tick & text
TITLE_SIZE        = 14    # axis titles
LABEL_SIZE        = 12     # axis labels
LEGEND_FONT_SIZE  = 11     # legend text
LEGEND_TITLE_SIZE = 12     # if using legend titles

# ── Line & marker defaults ───────────────────────────────────────────────
LINE_WIDTH   = 0.5
MARKER_SIZE  = 2.0
GRID_STYLE   = "--"
GRID_COLOR   = "0.5"
GRID_ALPHA   = 0.3

# ── Color & marker palettes ──────────────────────────────────────────────
# Up to eight distinct colors for architectures/controllers:
ARCH_COLORS        = mpl.rcParams["axes.prop_cycle"].by_key()["color"][:8]
INTENSE_ARCH_COLORS = mpl.cm.tab10.colors[:8]  # more saturated variant
MARKERS            = ["o", "s", "D", "^", "v", "P", "X", "d"]

def set_ieee_style() -> None:
    """
    Apply global IEEE-style settings to matplotlib.rcParams.
    """
    mpl.rcParams.update({
        # Fonts
        "font.size":          BASE_FONT_SIZE,
        # Axes
        "axes.titlesize":     TITLE_SIZE,
        "axes.titleweight":   "bold",
        "axes.labelsize":     LABEL_SIZE,
        "axes.linewidth":     LINE_WIDTH,
        "axes.edgecolor":     "black",
        # Ticks
        "xtick.labelsize":    BASE_FONT_SIZE,
        "ytick.labelsize":    BASE_FONT_SIZE,
        "xtick.direction":    "in",
        "ytick.direction":    "in",
        # Grid
        "axes.grid":          True,
        "grid.linestyle":     GRID_STYLE,
        "grid.color":         GRID_COLOR,
        "grid.alpha":         GRID_ALPHA,
        # Lines & markers
        "lines.linewidth":    LINE_WIDTH,
        "lines.markersize":   MARKER_SIZE,
        # Legend
        "legend.fontsize":    LEGEND_FONT_SIZE,
        "legend.title_fontsize": LEGEND_TITLE_SIZE,
        "legend.frameon":     False,
        # Figure
        "figure.dpi":         300,
        "figure.autolayout":  True,
    })
    # disable top/right spines
    mpl.rcParams["axes.spines.top"] = False
    mpl.rcParams["axes.spines.right"] = False

def new_figure(columns: int = 1,
               aspect_ratio: float = ASPECT_RATIO):
    """
    Convenience: create a new figure+axis at IEEE column width.
    Args:
      columns: 1 for single-column, 2 for double-column.
      aspect_ratio: height/width ratio.
    Returns:
      (fig, ax) tuple.
    """
    width = COLUMN_WIDTH if columns == 1 else DOUBLE_COLUMN_WIDTH
    height = width * aspect_ratio
    fig, ax = plt.subplots(figsize=(width, height))
    return fig, ax

def arch_color(idx: int) -> str:
    """Consistent color for the idx-th architecture/controller."""
    return ARCH_COLORS[idx % len(ARCH_COLORS)]

def arch_color_intense(idx: int) -> str:
    """More saturated color for highlights or bars."""
    return INTENSE_ARCH_COLORS[idx % len(INTENSE_ARCH_COLORS)]

def esc_marker(idx: int) -> str:
    """Consistent marker for the idx-th scenario."""
    return MARKERS[idx % len(MARKERS)]

def esc_marker_intense(idx: int) -> str:
    """Alternate marker set (currently same as esc_marker)."""
    return MARKERS[idx % len(MARKERS)]
