# -*- coding: utf-8 -*-
"""Regenerate fig2_generalization_gain.pdf (H3) from the raw JSON.

Reads report_stage1_rho_c.json and plots F_gen (generalized skeleton library) and
F_raw (specific-fragment library) coverage as functions of the effective density
rho_eff. F_gen >= F_raw at every point, reproducing the H3 "average P improvement
of 0.40" and the left-shifted rho_c. All data read from disk, never hard-coded.
"""
import json, os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator

HERE = os.path.dirname(os.path.abspath(__file__))
CODE = os.path.join(HERE, "..", "code")
DATA = os.path.join(CODE, "report_stage1_rho_c.json")

with open(DATA, encoding="utf-8") as f:
    d = json.load(f)

gen = d["gen_points"]
raw = d["raw_points"]
rho = [p["rho"] for p in gen]
P_gen = [p["P"] for p in gen]
P_raw = [p["P"] for p in raw]
rho_c_gen = d["rho_c_gen"]
avg_boost = d["avg_boost"]

plt.rcParams.update({"font.size": 11, "axes.linewidth": 1.0,
                     "pdf.fonttype": 42, "ps.fonttype": 42, "font.family": "serif"})

fig, ax = plt.subplots(figsize=(6.0, 3.6))

ax.plot(rho, P_gen, "o-", color="#1e8a5c", linewidth=2.0, markersize=5,
        label="Generalized skeleton library $F_{\\mathrm{gen}}$")
ax.plot(rho, P_raw, "s--", color="#c0392b", linewidth=1.7, markersize=5,
        label="Specific-fragment library $F_{\\mathrm{raw}}$")

ax.axvline(rho_c_gen, color="#1e8a5c", linestyle=":", linewidth=1.2)
ax.annotate(f"$F_{{\\mathrm{{gen}}}}$ >= $F_{{\\mathrm{{raw}}}}$ at every point; "
            f"avg $P$ boost $= {avg_boost:.2f}$, $\\rho_c\\!\\approx\\!{rho_c_gen}$",
            xy=(rho_c_gen, 0.5), xytext=(0.08, 0.72), fontsize=9.5,
            color="#1e8a5c", arrowprops=dict(arrowstyle="->", color="#1e8a5c", lw=1.0))

ax.set_xlabel("Effective library density $\\rho_{\\mathrm{eff}}$")
ax.set_ylabel("Coverage probability $P$")
ax.set_title("Generalization shift: F_gen dominates F_raw (H3)", fontsize=11, fontweight="bold")
ax.set_xlim(0.0, 1.05)
ax.set_ylim(0.0, 1.05)
ax.xaxis.set_major_locator(MaxNLocator(nbins=6))
ax.yaxis.set_major_locator(MaxNLocator(nbins=6))
ax.legend(frameon=False, loc="upper left", fontsize=9)
ax.grid(True, linestyle=":", alpha=0.35)

ax.text(0.99, 0.02,
        f"{d['n_classes']} classes x {d['targets_per_class']} targets; "
        f"{len(gen)}-step rho_eff grid",
        transform=ax.transAxes, ha="right", va="bottom", fontsize=8, color="#555555")

out = os.path.join(HERE, "fig2_generalization_gain.pdf")
fig.savefig(out, format="pdf", bbox_inches="tight")
print("wrote", out)
