"""Shared chart style for the project: one colour-blind-safe palette, light grid, no top/right spines."""
import matplotlib.pyplot as plt

BLUE, ORANGE, RED = "#2a78d6", "#eb6834", "#e34948"
GRAY, BAND, INK, INK2 = "#8a8985", "#dcdbd6", "#0b0b0b", "#52514e"
SURFACE = "#fcfcfb"

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.edgecolor": "#c9c8c2", "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
    "text.color": INK, "axes.grid": True, "grid.color": "#e8e7e3", "grid.linewidth": 0.6,
    "axes.spines.top": False, "axes.spines.right": False, "axes.titlesize": 12,
    "axes.titleweight": "bold", "axes.titlelocation": "left", "font.size": 10,
    "lines.linewidth": 1.6, "legend.frameon": False, "savefig.dpi": 150, "savefig.bbox": "tight",
})
