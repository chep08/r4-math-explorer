"""Regenerate fig4_real_datasets_absent.pdf: real-domain P(rho) is flat.

Reads two gold-standard JSONs:
  - code/lw_h1_rho.json            (real corpora P(rho): flat at 0.267)
  - code/report_stage1_synth.json  (synthetic-domain P(rho): the SAME curve used by
                                    Fig. 1, so the contrast line is not mis-stated)
and plots both so the contrast (valid-but-bounded) is visible. Data are read from
disk, never hard-coded. The synthetic curve MUST be the same P(rho) as Fig. 1
(report_stage1_synth.json), as the main text states this figure contrasts the flat
real curve "with the rising synthetic curve of Figure 1".
"""
import json
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator

HERE = os.path.dirname(os.path.abspath(__file__))
CODE = os.path.join(HERE, "..", "code")

with open(os.path.join(CODE, "lw_h1_rho.json"), encoding="utf-8") as f:
    real = json.load(f)
with open(os.path.join(CODE, "report_stage1_synth.json"), encoding="utf-8") as f:
    syn = json.load(f)

# real corpora: flat P(rho)
rho_r = [p["rho"] for p in real["points"]]
P_r = [p["P"] for p in real["points"]]
n_targets = real["targets"]
P0 = P_r[0]

# synthetic domain: rising P(rho) — the SAME curve as Figure 1 (H1 synthetic)
syn_pts = syn["density_points"]
rho_s = [p["rho"] for p in syn_pts]
P_s = [p["P"] for p in syn_pts]
rho_c = syn["rho_c_heuristic"]  # 0.9

plt.rcParams.update({
    "font.size": 11,
    "axes.linewidth": 1.0,
    # arXiv forbids Type 3 bitmap glyphs; emit TrueType (Type 42) subsets instead.
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
    "font.family": "serif",
})

fig, ax = plt.subplots(figsize=(6.0, 3.6))

ax.plot(rho_r, P_r, "o-", color="#c0392b", linewidth=2.2, markersize=7,
        label="Real corpora: $P(\\rho)$ (flat)")
ax.plot(rho_s, P_s, "--", color="#2c3e50", linewidth=1.8,
        label=f"Synthetic domain: $P(\\rho)$ (as in Fig. 1, "
              f"$\\rho_c\\!\\approx\\!{rho_c}$)")

ax.axhline(y=P0, color="#c0392b", linestyle=":", linewidth=1.0)
ax.annotate(f"flat at $P={P0:.3f}$: library density\nhas no effect on real targets",
            xy=(0.62, P0), xytext=(0.10, 0.55),
            fontsize=9, color="#c0392b",
            arrowprops=dict(arrowstyle="->", color="#c0392b", lw=1.0))

ax.set_xlabel("Library density $\\rho$")
ax.set_ylabel("Hold-out close probability $P(\\rho)$")
ax.set_title("Library-reuse phase transition is not observed on real data",
             fontsize=11, fontweight="bold")
ax.set_xlim(0.0, 1.03)
ax.set_ylim(0.0, 1.03)
ax.xaxis.set_major_locator(MaxNLocator(nbins=6))
ax.yaxis.set_major_locator(MaxNLocator(nbins=6))
ax.legend(frameon=False, loc="upper left", fontsize=9)
ax.grid(True, linestyle=":", alpha=0.35)

ax.text(0.99, 0.02,
        f"real: $n={n_targets}$ held-out targets, $P$ constant at {P0:.3f}",
        transform=ax.transAxes, ha="right", va="bottom", fontsize=8,
        color="#555555",
        bbox=dict(facecolor="white", alpha=0.7, edgecolor="none", pad=1.5))

out = os.path.join(HERE, "fig4_real_datasets_absent.pdf")
fig.savefig(out, format="pdf", bbox_inches="tight")
print("wrote", out)
