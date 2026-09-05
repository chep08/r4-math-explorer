# -*- coding: utf-8 -*-
"""Regenerate fig3_equal_compute_crossover.pdf (H5) from the raw JSON.

Reads report_stage1_h245.json H5 points (full 0.05-step sequence) and plots the
library route L vs the direct-sampling route D under a fixed compute budget. The
crossover marker is placed at the FIRST grid point where L>D (rho=0.85, per the
same definition stored in the JSON). A shaded band marks the [0.80,0.85] interval
where the true crossing lies, so the marker is not misread as an exact point.
All data read from disk; no hard-coded numbers.
"""
import json, os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator

HERE = os.path.dirname(os.path.abspath(__file__))
CODE = os.path.join(HERE, "..", "code")
DATA = os.path.join(CODE, "report_stage1_h245.json")

with open(DATA, encoding="utf-8") as f:
    d = json.load(f)

pts = d["H5"]
rho = [p["budget_share"] for p in pts]
L = [p["L"] for p in pts]
D = [p["D"] for p in pts]
cross = d["H5_cross_point"]  # first grid point where L>D (0.85)

plt.rcParams.update({"font.size": 11, "axes.linewidth": 1.0,
                     "pdf.fonttype": 42, "ps.fonttype": 42, "font.family": "serif"})

fig, ax = plt.subplots(figsize=(6.0, 3.6))

# D is constant 0.30 across the whole scan
ax.plot(rho, D, "--", color="#2c3e50", linewidth=1.8, label="D (direct sampling)")
# L rises as the library budget grows
ax.plot(rho, L, "o-", color="#c0392b", linewidth=2.0, markersize=5.5,
        label="L (library route)")

# crossover interval shading: the true crossing lies in [rho_before, cross]
rho_before = rho[rho.index(cross) - 1]
ax.axvspan(rho_before, cross, color="#c0392b", alpha=0.12)
ax.axvline(cross, color="#c0392b", linestyle=":", linewidth=1.4)
ax.annotate(
    f"first grid point where L>D: $\\rho={cross}$\n(crossing lies in "
    f"$[{rho_before:.2f}, {cross}]$)",
    xy=(cross, 0.35), xytext=(0.13, 0.62), fontsize=9, color="#c0392b",
    arrowprops=dict(arrowstyle="->", color="#c0392b", lw=1.0))

ax.set_xlabel("Budget share allocated to library (density)")
ax.set_ylabel("Success rate")
ax.set_title("Equal-compute library/direct crossover (H5)", fontsize=11, fontweight="bold")
ax.set_xlim(0.0, 1.05)
ax.set_ylim(0.0, 0.8)
ax.xaxis.set_major_locator(MaxNLocator(nbins=6))
ax.yaxis.set_major_locator(MaxNLocator(nbins=6))
ax.legend(frameon=False, loc="upper left", fontsize=9)
ax.grid(True, linestyle=":", alpha=0.35)

ax.text(0.99, 0.02, f"n={d['n_targets']} targets; 20-step grid; D constant at 0.30",
        transform=ax.transAxes, ha="right", va="bottom", fontsize=8, color="#555555")

out = os.path.join(HERE, "fig3_equal_compute_crossover.pdf")
fig.savefig(out, format="pdf", bbox_inches="tight")
print("wrote", out)
