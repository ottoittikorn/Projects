"""Charts in one shared style.

Palette: the validated categorical order also used in Energy/US_Gas_Storage (passes CVD and
normal-vision separation checks). Three hues sit below 3:1 contrast on the light surface, so
every line chart is direct-labelled and every figure has a table behind it in the notebook.
Diverging maps (correlation, seasonality) use blue <-> red around a neutral grey.
"""
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm

from .config import COLORS, COMMODITIES, FIGURES_DIR, SHORT_NAMES

INK, INK2, MUTED = "#0b0b0b", "#52514e", "#8a8985"
SURFACE = "#fcfcfb"
DIVERGING = LinearSegmentedColormap.from_list("blue_grey_red", ["#2a78d6", "#f0efec", "#e34948"])

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.edgecolor": "#c9c8c2", "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
    "text.color": INK, "axes.grid": True, "grid.color": "#e8e7e3", "grid.linewidth": 0.6,
    "axes.spines.top": False, "axes.spines.right": False, "axes.titlesize": 12,
    "axes.titleweight": "bold", "axes.titlelocation": "left", "font.size": 10,
    "lines.linewidth": 1.6, "legend.frameon": False, "savefig.dpi": 150, "savefig.bbox": "tight",
})

GROUPS = {"Energy": ("energy",), "Metals": ("precious", "base")}


def save(fig, name):
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIGURES_DIR / f"{name}.png")


def _split_by_group(columns):
    return {title: [c for c in columns if COMMODITIES[c].group in groups] for title, groups in GROUPS.items()}


def _direct_label(ax, series_by_key, fmt):
    """Label each line at its right end, nudging labels apart so they don't overlap."""
    ends = sorted(((s.dropna().iloc[-1], k) for k, s in series_by_key.items()), key=lambda t: t[0])
    lo, hi = ax.get_ylim()
    min_gap = (hi - lo) * 0.045
    y_text = -np.inf
    for y, k in ends:
        y_text = max(y, y_text + min_gap)
        x = series_by_key[k].dropna().index[-1]
        ax.plot(x, y, "o", ms=4, color=COLORS[k])
        ax.annotate(f"{SHORT_NAMES[k]} {fmt(y)}", (x, y_text), xytext=(6, 0), textcoords="offset points",
                    va="center", fontsize=9, color=INK2, annotation_clip=False)


def _lines_by_group(df, title, ylabel, fmt, baseline=None):
    groups = _split_by_group(df.columns)
    fig, axes = plt.subplots(1, len(groups), figsize=(13, 4.6), sharey=True)
    for ax, (group, cols) in zip(axes, groups.items()):
        for c in cols:
            s = df[c].dropna()  # each line on its own trading calendar, so holidays don't break it
            ax.plot(s.index, s, color=COLORS[c], label=SHORT_NAMES[c])
        if baseline is not None:
            ax.axhline(baseline, color=MUTED, lw=0.8)
        ax.set_title(group)
        ax.legend(loc="upper left", fontsize=9)
        _direct_label(ax, {c: df[c] for c in cols}, fmt)
        ax.margins(x=0.02)
    axes[0].set_ylabel(ylabel)
    fig.suptitle(title, x=0.01, ha="left", fontweight="bold", fontsize=13)
    fig.tight_layout()
    return fig


def normalised_performance(prices, years=1):
    """Each commodity rebased to 100 at the start of the window."""
    window = prices[prices.index > prices.index.max() - np.timedelta64(365 * years, "D")].ffill()
    rebased = 100 * window / window.bfill().iloc[0]
    return _lines_by_group(rebased, f"Performance over the last {years} year{'s' * (years > 1)} (rebased to 100)",
                           "Index (start = 100)", lambda v: f"{v:.0f}", baseline=100)


def rolling_vol_chart(vol, years=5):
    window = vol[vol.index > vol.index.max() - np.timedelta64(365 * years, "D")]
    fig = _lines_by_group(100 * window, "Rolling 3-month annualised volatility", "Volatility (% a year)",
                          lambda v: f"{v:.0f}%")
    return fig


def _annotated_heatmap(ax, grid, norm, fmt, mark=None):
    im = ax.imshow(grid.values, cmap=DIVERGING, norm=norm, aspect="auto")
    for i in range(grid.shape[0]):
        for j in range(grid.shape[1]):
            v = grid.iat[i, j]
            if np.isnan(v):
                continue
            text = fmt(v) + ("*" if mark is not None and mark.iat[i, j] else "")
            ax.text(j, i, text, ha="center", va="center", fontsize=8.5, color=INK)
    ax.grid(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_visible(False)
    ax.tick_params(length=0)
    return im


def correlation_heatmap(corr, years=5):
    labels = [SHORT_NAMES[c] for c in corr.columns]
    fig, ax = plt.subplots(figsize=(7.2, 6))
    masked = corr.where(~np.triu(np.ones(corr.shape, bool), k=1))  # lower triangle: each pair once
    im = _annotated_heatmap(ax, masked, TwoSlopeNorm(0, -1, 1), lambda v: f"{v:.2f}")
    ax.set_xticks(range(len(labels)), labels, rotation=45, ha="right")
    ax.set_yticks(range(len(labels)), labels)
    fig.colorbar(im, ax=ax, shrink=0.75, label="Correlation of daily returns")
    ax.set_title(f"Daily return correlation, last {years} years")
    fig.tight_layout()
    return fig


def seasonality_heatmap(mean_grid, p_grid, start):
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    pct = 100 * mean_grid
    lim = np.nanmax(np.abs(pct.values))
    fig, ax = plt.subplots(figsize=(12, 4.8))
    im = _annotated_heatmap(ax, pct, TwoSlopeNorm(0, -lim, lim), lambda v: f"{v:+.1f}", mark=p_grid < 0.05)
    ax.set_xticks(range(12), months)
    ax.set_yticks(range(len(pct)), [SHORT_NAMES[c] for c in pct.index])
    fig.colorbar(im, ax=ax, shrink=0.8, label="Average monthly return (%)")
    ax.set_title(f"Average return by calendar month, {start}-present (World Bank monthly averages)   "
                 "* = p < 0.05")
    fig.tight_layout()
    return fig


def overlay(a, b, title, ylabel):
    """Two versions of the same price on one axis (same unit), plus their % difference below."""
    df = pd.concat([a, b], axis=1, join="inner", keys=["a", "b"])
    fig, (top, bottom) = plt.subplots(2, 1, figsize=(12, 6), sharex=True, gridspec_kw={"height_ratios": [2.2, 1]})
    top.plot(df.index, df.iloc[:, 0], color="#2a78d6", label=a.attrs.get("label", a.name))
    top.plot(df.index, df.iloc[:, 1], color="#eb6834", label=b.attrs.get("label", b.name), lw=1.2)
    top.set_ylabel(ylabel)
    top.set_title(title)
    top.legend(loc="upper left")
    diff = 100 * (df.iloc[:, 0] / df.iloc[:, 1] - 1)
    bottom.plot(diff.index, diff, color=INK2, lw=0.9)
    bottom.axhline(0, color=MUTED, lw=0.8)
    bottom.set_ylabel("Difference (%)")
    fig.tight_layout()
    return fig
