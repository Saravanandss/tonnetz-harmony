"""
Draws the Tonnetz as a flat patch of the torus.

    python figures.py output/results.json output

fig1_tonnetz.png          pitch classes (dots), three edge types, the 24 triads as triangles
fig2_beatles_chords.png   same patch, triangles shaded by how much playing time each chord gets
                          (major-key passages, transposed so the tonic is C)
"""
import json
import math
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon

from tonnetz import NOTE_NAMES, triad_name

INK, GREY, LIGHT, BLUE = "#1f2328", "#8b949e", "#d0d7de", "#2f6fde"
ROMAN = ["I", "bII", "II", "bIII", "III", "IV", "#IV", "V", "bVI", "VI", "bVII", "VII"]
I_RANGE, J_RANGE = range(-2, 4), range(-1, 3)


def xy(i, j):
    return i + j / 2, j * math.sqrt(3) / 2


def pc(i, j):
    return (7 * i + 4 * j) % 12


def triangles():
    """(corner points, root, quality) for every triangle of the patch."""
    out = []
    rows = sorted(list(J_RANGE)[:-1], key=abs)      # middle row first, so each chord is shaded once there
    for j in rows:
        for i in list(I_RANGE)[:-1]:
            out.append(([(i, j), (i + 1, j), (i, j + 1)], pc(i, j), "maj"))
            out.append(([(i + 1, j), (i, j + 1), (i + 1, j + 1)], pc(i, j + 1), "min"))
    return out


def draw(path, shares=None):
    fig, ax = plt.subplots(figsize=(9.2, 4.9), dpi=200)
    edge_style = {"P5": dict(color=INK, lw=1.6, ls="-"),
                  "M3": dict(color=GREY, lw=1.3, ls="--"),
                  "m3": dict(color=GREY, lw=1.3, ls=":")}
    top = max(shares.values()) if shares else 1
    shaded = set()

    for corners, root, quality in triangles():
        pts = [xy(*c) for c in corners]
        cx, cy = sum(p[0] for p in pts) / 3, sum(p[1] for p in pts) / 3
        numeral = ROMAN[root] if quality == "maj" else ROMAN[root].lower()
        share = shares.get(numeral, 0) if shares else 0
        if shares and share >= 0.02 and (root, quality) not in shaded:
            shaded.add((root, quality))
            alpha = 0.15 + 0.75 * math.sqrt(share / top)
            ax.add_patch(Polygon(pts, closed=True, facecolor=BLUE, alpha=alpha, edgecolor="none", zorder=1))
            dark = alpha > 0.55
            ax.text(cx, cy + 0.06, triad_name(root, quality), ha="center", va="center", fontsize=9.5,
                    color="white" if dark else INK, fontweight="bold", zorder=4)
            ax.text(cx, cy - 0.11, f"{numeral} {share:.0%}", ha="center", va="center", fontsize=7,
                    color="white" if dark else INK, zorder=4)
        else:
            ax.text(cx, cy, triad_name(root, quality), ha="center", va="center", fontsize=8.5,
                    color=GREY if shares else INK, zorder=4)

    for j in J_RANGE:
        for i in I_RANGE:
            x, y = xy(i, j)
            for (di, dj), label in (((1, 0), "P5"), ((0, 1), "M3"), ((-1, 1), "m3")):
                if i + di in I_RANGE and j + dj in J_RANGE:
                    x2, y2 = xy(i + di, j + dj)
                    ax.plot([x, x2], [y, y2], zorder=2, **edge_style[label])
    for j in J_RANGE:
        for i in I_RANGE:
            x, y = xy(i, j)
            ax.scatter([x], [y], s=520, color="white", edgecolor=INK, linewidth=1.4, zorder=5)
            ax.text(x, y, NOTE_NAMES[pc(i, j)], ha="center", va="center", fontsize=10,
                    fontweight="bold", color=INK, zorder=6)

    handles = [plt.Line2D([], [], label=lab, **edge_style[key]) for key, lab in
               (("P5", "perfect fifth"), ("M3", "major third"), ("m3", "minor third"))]
    ax.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, -0.02), ncol=3,
              frameon=False, fontsize=9, handlelength=3)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_xlim(-3.0, 4.4)
    ax.set_ylim(-1.15, 2.0)
    fig.tight_layout()
    fig.savefig(path, facecolor="white")
    plt.close(fig)


if __name__ == "__main__":
    results = json.loads(Path(sys.argv[1]).read_text())
    out = Path(sys.argv[2])
    draw(out / "fig1_tonnetz.png")
    draw(out / "fig2_beatles_chords.png", dict(results["chord_time_shares_key_relative"]))
