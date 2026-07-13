"""Generate the RixsViewer application icon.

Depicts the Rowland circle geometry used in RIXS spectroscopy:
  - Incoming X-ray beam (white arrow, upper-left → sample)
  - Sample at origin (bright white dot)
  - Rowland circle arc (cyan)
  - Dispersed spectral emission lines (rainbow, sample → analyzer)
  - Analyzer crystal and detector on the Rowland circle

Run: python make_icon.py
Output: src/rixsviewer/assets/icon.png (256×256) and icon_32.png (32×32)
"""

import os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import Arc

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "src", "rixsviewer", "assets")


def _draw(ax, R=0.72):
    """Draw the icon on *ax*. R is the Rowland radius in axis units."""
    BG = "#0d1b2a"
    fig = ax.get_figure()
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(BG)
    ax.set_aspect("equal")
    ax.set_xlim(-1.35, 1.35)
    ax.set_ylim(-1.35, 1.35)
    ax.axis("off")

    # ── circular background ───────────────────────────────────────────────
    ax.add_patch(plt.Circle((0, 0), 1.28, color="#0d1b2a", zorder=1))
    ax.add_patch(plt.Circle((0, 0), 1.28, color="#1e4d8c", fill=False, linewidth=4, zorder=10))

    # ── Rowland circle ────────────────────────────────────────────────────
    # Center is at (0, R); sample sits at origin (bottom of the circle)
    rowland = Arc(
        (0, R), 2 * R, 2 * R,
        angle=0, theta1=190, theta2=350,
        color="#29b6f6", linewidth=3.5, zorder=5, alpha=0.95,
    )
    ax.add_patch(rowland)

    # ── analyzer crystal (on Rowland circle at ~235°) ─────────────────────
    ang_c = np.radians(235)
    cx, cy = R * np.cos(ang_c), R + R * np.sin(ang_c)
    # small rectangle oriented normal to the circle at that point
    rot = np.degrees(ang_c) + 90
    crystal = mpatches.FancyBboxPatch(
        (cx - 0.06, cy - 0.14), 0.12, 0.28,
        boxstyle="round,pad=0.02",
        facecolor="#b0bec5", edgecolor="white", linewidth=1.2,
        zorder=6,
        transform=ax.transData,
    )
    # rotate around crystal centre
    t = (
        matplotlib.transforms.Affine2D()
        .rotate_deg_around(cx, cy, rot - 90 + 90)
        + ax.transData
    )
    crystal.set_transform(t)
    ax.add_patch(crystal)

    # ── detector (on Rowland circle at ~305°) ────────────────────────────
    ang_d = np.radians(305)
    dx, dy = R * np.cos(ang_d), R + R * np.sin(ang_d)
    detector = mpatches.FancyBboxPatch(
        (dx - 0.055, dy - 0.20), 0.11, 0.40,
        boxstyle="round,pad=0.02",
        facecolor="#37474f", edgecolor="#90a4ae", linewidth=1.2,
        zorder=6,
    )
    ax.add_patch(detector)

    # ── incoming X-ray beam (upper-left → sample) ────────────────────────
    ax.annotate(
        "", xy=(0.02, 0.02), xytext=(-1.05, 0.82),
        arrowprops=dict(
            arrowstyle="-|>", color="#fff59d", lw=2.8,
            mutation_scale=18, shrinkA=0, shrinkB=4,
        ),
        zorder=7,
    )

    # ── sample dot with glow ─────────────────────────────────────────────
    ax.add_patch(plt.Circle((0, 0), 0.13, color="white", alpha=0.18, zorder=7))
    ax.add_patch(plt.Circle((0, 0), 0.08, color="white", zorder=8))

    # ── dispersed spectral emission lines (rainbow, sample → analyzer) ───
    # Fan of lines aimed roughly toward the analyzer/Rowland arc
    spectrum_colors = ["#ef5350", "#ff7043", "#ffca28", "#aed581", "#29b6f6", "#7986cb"]
    center_angle = np.radians(225)   # aim toward analyzer
    half_fan = np.radians(28)
    n = len(spectrum_colors)
    for i, color in enumerate(spectrum_colors):
        a = center_angle - half_fan + i * 2 * half_fan / (n - 1)
        length = 0.68 + 0.06 * np.sin(i * np.pi / (n - 1))
        ex, ey = length * np.cos(a), length * np.sin(a)
        ax.plot([0, ex], [0, ey], color=color, linewidth=2.2,
                alpha=0.85, zorder=6, solid_capstyle="round")

    # ── label "Rx" in bottom-right ───────────────────────────────────────
    ax.text(
        0.70, -0.90, "Rx",
        fontsize=18, fontweight="bold", color="#29b6f6",
        ha="center", va="center", zorder=9,
        fontfamily="DejaVu Sans",
    )


def make_icon(size_px=256, filename="icon.png"):
    dpi = 100
    fig, ax = plt.subplots(figsize=(size_px / dpi, size_px / dpi), dpi=dpi)
    _draw(ax)
    plt.subplots_adjust(left=0, right=1, top=1, bottom=0)
    out = os.path.join(OUTPUT_DIR, filename)
    fig.savefig(out, dpi=dpi, facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"Wrote {out}")


if __name__ == "__main__":
    make_icon(256, "icon.png")
    make_icon(64, "icon_64.png")
    make_icon(32, "icon_32.png")
