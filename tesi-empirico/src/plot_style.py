"""Shared matplotlib style for thesis figures (light mode, 300 dpi, EN labels).

Palette: validated reference categorical order (dataviz method) — slots are
assigned to entities once and never cycled:
  cyber_strict -> blue, cyber_broad -> orange, ict_generic -> aqua,
  groups: early -> blue, mid -> orange, late -> aqua, control -> yellow
  (yellow is sub-3:1 on light surface: figures using it carry direct labels).
Treatment marker: red vline. eForms cutover: muted dotted vline.
"""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"

BLUE = "#2a78d6"
ORANGE = "#eb6834"
AQUA = "#1baf7a"
YELLOW = "#eda100"
RED = "#e34948"

CAT_COLORS = {"cyber_strict": BLUE, "cyber_broad": ORANGE, "ict_generic": AQUA}
GROUP_COLORS = {"early": BLUE, "mid": ORANGE, "late": AQUA, "control": YELLOW}

EFORMS_MONTH = "2023-10"


def apply_style():
    plt.rcParams.update({
        "figure.dpi": 100,
        "savefig.dpi": 300,
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "savefig.facecolor": SURFACE,
        "text.color": INK,
        "axes.edgecolor": AXIS,
        "axes.labelcolor": INK2,
        "axes.titlecolor": INK,
        "xtick.color": MUTED,
        "ytick.color": MUTED,
        "axes.grid": True,
        "grid.color": GRID,
        "grid.linewidth": 0.6,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.linewidth": 0.8,
        "lines.linewidth": 1.8,
        "font.family": "sans-serif",
        "font.size": 9,
        "axes.titlesize": 10,
        "legend.frameon": False,
    })


def month_ticks(ax, months, every=6):
    idx = list(range(0, len(months), every))
    ax.set_xticks(idx)
    ax.set_xticklabels([months[i] for i in idx], rotation=45, ha="right",
                       fontsize=7)


def treatment_line(ax, months, treat_month, **kw):
    if treat_month and treat_month in months:
        ax.axvline(months.index(treat_month), color=RED, linestyle="--",
                   linewidth=1.0, **kw)


def eforms_line(ax, months):
    if EFORMS_MONTH in months:
        ax.axvline(months.index(EFORMS_MONTH), color=MUTED, linestyle=":",
                   linewidth=0.9)
