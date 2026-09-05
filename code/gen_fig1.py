# -*- coding: utf-8 -*-
"""Regenerate fig1_phase_transition.pdf (H1) from the raw JSON.

Reads report_stage1_synth.json density_points and plots the synthetic-domain
close probability P(rho) and its susceptibility chi(rho), marking the heuristic
critical density rho_c (first rho with P>=0.5). All data read from disk.
"""
import json, os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator

HERE = os.path.dirname(os.path.abspath(__file__))
CODE = os.path.join(HERE, "..", "code")
DATA = os.path.join(CODE, "report_stage1_synth.json")

with open(DATA, encoding="utf-8") as f:
    d = json.load(f)

pts = d["density_points"]
rho = [p["rho"] for p in pts]
P = [p["P"] for p in pts]
chi = [p["chi"] for p in pts]
rho_c = d["rho_c_heuristic"]

plt.rcParams.update({"font.size": 11, "axes.linewidth": 1.0,
                     "pdf.fonttype": 42, "ps.fonttype": 42, "font.family": "serif"})

fig, ax = plt.subplots(figsize=(6.0, 3.6))

ax.plot(rho, P, "o-", color="#c0392b", linewidth=2.0, markersize=5.5,
        label="Close probability $P(\\rho)$")
ax.plot(rho, chi, "s--", color="#2c3e50", linewidth=1.6, markersize=5,
        label="Susceptibility $\\chi(\\rho)$")

ax.axvline(rho_c, color="#c0392b", linestyle=":", linewidth=1.2)
ax.annotate(f"heuristic $\\rho_c = {rho_c:.1f}$", xy=(rho_c, 0.62),
            xytext=(rho_c - 0.28, 0.5), fontsize=9, color="#c0392b",
            arrowprops=dict(arrowstyle="->", color="#c0392b", lw=1.0))

ax.set_xlabel("Library density $\\rho$")
ax.set_ylabel("Close probability / susceptibility")
ax.set_title("Synthetic-domain phase transition (H1)", fontsize=11, fontweight="bold")
ax.set_xlim(0.0, 1.05)
ax.set_ylim(0.0, 1.05)
ax.xaxis.set_major_locator(MaxNLocator(nbins=6))
ax.yaxis.set_major_locator(MaxNLocator(nbins=6))
ax.legend(frameon=False, loc="upper left", fontsize=9)
ax.grid(True, linestyle=":", alpha=0.35)

ax.text(0.99, 0.02, f"n={d['n_targets']} targets; k={d['k']}; {len(pts)}-step grid",
        transform=ax.transAxes, ha="right", va="bottom", fontsize=8, color="#555555")

out = os.path.join(HERE, "fig1_phase_transition.pdf")
fig.savefig(out, format="pdf", bbox_inches="tight")
print("wrote", out)
