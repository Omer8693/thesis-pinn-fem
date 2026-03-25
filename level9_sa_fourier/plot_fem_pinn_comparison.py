"""
plot_fem_pinn_comparison.py
FEM zaman adımı atlama (skip) ile PINN seviyelerinin karşılaştırması.
Gösterilen bilgiler:
  · FEM skip=1,2,4,6 — L2 hatası ve çalışma süresi
  · L1 → L5 → L9 PINN seviye ilerlemesi
  · Hız-Doğruluk dengesi (Pareto eğrisi)
  · Özet tablo
"""

import json
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from pathlib import Path

# ── Output directory ────────────────────────────────────────────
OUT = Path("level9_sa_fourier/results/plots")
OUT.mkdir(parents=True, exist_ok=True)

# ── Colors (aligned with Level 7 scheme) ────────────────────────
C_FEM   = "#5d7b8a"   # FEM — blue-grey
C_L1    = "#E65100"   # Level 1 — orange
C_L5    = "#f0ad4e"   # Level 5 — yellow
C_L9_SA = "#5cb85c"   # L9 SA-only — green
C_L9_SF = "#428bca"   # L9 SA+Fourier — blue
BG      = "#f7f1e3"
AX_BG   = "#fffdf8"

# ── Raw data ─────────────────────────────────────────────────────

# FEM skip — Bayesian architecture, from Level 2 skip table
fem_skips = [
    {"skip": 1,  "l2": 0.1261, "mae": 43.6,  "runtime_s": 183.8, "fem_steps": 21, "pinn_steps": 0},
    {"skip": 2,  "l2": 0.1076, "mae": 33.2,  "runtime_s": 90.5,  "fem_steps": 11, "pinn_steps": 10},
    {"skip": 4,  "l2": 0.2042, "mae": 57.5,  "runtime_s": 46.1,  "fem_steps": 6,  "pinn_steps": 15},
    {"skip": 6,  "l2": 0.2936, "mae": 93.6,  "runtime_s": 27.7,  "fem_steps": 4,  "pinn_steps": 17},
]

# PINN levels — Bayesian optimizer (best)
pinn_levels = [
    {"label": "L1\n(Adam)",        "l2": 0.0764, "mae": 39.1,  "train_s": 300,   "infer_s": 0.01, "color": C_L1},
    {"label": "L5\n(Adam+L-BFGS)", "l2": 0.0296, "mae": 14.4,  "train_s": 600,   "infer_s": 0.01, "color": C_L5},
    {"label": "L9 SA",             "l2": 0.0151, "mae": 7.8,   "train_s": 404,   "infer_s": 0.01, "color": C_L9_SA},
    {"label": "L9 SA+F\n(NSGA-II)","l2": 0.0137, "mae": 7.1,   "train_s": 444,   "infer_s": 0.01, "color": C_L9_SF},
]

# L3 Hybrid (FEM+PINN, skip=4, 80% PINN)
hybrid = {"label": "L3 Hybrid\n(80% PINN)", "l2": None, "mae": None,
          "runtime_s": 111.2, "fem_steps": 4, "pinn_steps": 16}

# ════════════════════════════════════════════════════════════════
# Figure 1 — L2 Accuracy Comparison (bar chart)
# ════════════════════════════════════════════════════════════════
fig, ax = plt.subplots(figsize=(11, 5))
fig.patch.set_facecolor(BG); ax.set_facecolor(AX_BG)

labels, colors, l2s = [], [], []

for d in fem_skips:
    labels.append(f"FEM\nskip={d['skip']}")
    colors.append(C_FEM)
    l2s.append(d["l2"])

for d in pinn_levels:
    labels.append(d["label"])
    colors.append(d["color"])
    l2s.append(d["l2"])

x = np.arange(len(labels))
bars = ax.bar(x, l2s, color=colors, width=0.6, alpha=0.88, edgecolor="white", linewidth=0.8)

# Value labels
for bar, val in zip(bars, l2s):
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.004,
            f"{val:.3f}", ha="center", va="bottom", fontsize=8.5, fontweight="bold")

# FEM reference line (skip=1)
ax.axhline(0.1261, color=C_FEM, linestyle="--", linewidth=1.2, alpha=0.6, label="FEM skip=1 (reference)")

# Improvement arrow — FEM skip=1 → L9 SA+F
best_l9 = 0.0137
ax.annotate("", xy=(x[-1], best_l9 + 0.005), xytext=(x[0], 0.1261 - 0.005),
            arrowprops=dict(arrowstyle="->", color="#2e4057", lw=1.8))
ax.text((x[0]+x[-1])/2 + 0.3, 0.075, "9.2× improvement\n(FEM→L9)",
        ha="center", fontsize=9, color="#2e4057", fontweight="bold",
        bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.8))

# Vertical separator (FEM | PINN)
ax.axvline(len(fem_skips) - 0.5, color="gray", linestyle=":", linewidth=1.2, alpha=0.7)
ax.text(len(fem_skips) - 0.5 - 1.8, 0.30, "FEM\nMethod", ha="center", fontsize=9,
        color=C_FEM, alpha=0.8)
ax.text(len(fem_skips) - 0.5 + 2.0, 0.30, "PINN\nMethod", ha="center", fontsize=9,
        color="#2e4057", alpha=0.8)

ax.set_xticks(x)
ax.set_xticklabels(labels, fontsize=9)
ax.set_ylabel("L2 Relative Error", fontsize=11)
ax.set_title("FEM Time-Stepping Skip vs PINN Level Progression — L2 Accuracy", fontsize=12, fontweight="bold")
ax.set_ylim(0, 0.38)
ax.legend(fontsize=9)
ax.grid(axis="y", alpha=0.3)

plt.tight_layout()
plt.savefig(OUT / "fem_pinn_l2_comparison.png", dpi=150, bbox_inches="tight")
plt.close()
print("✓ fem_pinn_l2_comparison.png")

# ════════════════════════════════════════════════════════════════
# Figure 2 — Speed–Accuracy Trade-off (Pareto Scatter)
# ════════════════════════════════════════════════════════════════
fig, ax = plt.subplots(figsize=(9, 6))
fig.patch.set_facecolor(BG); ax.set_facecolor(AX_BG)

# FEM points — runtime per simulation run
for d in fem_skips:
    ax.scatter(d["runtime_s"], d["l2"], s=120, color=C_FEM, zorder=5,
               marker="s", edgecolors="white", linewidth=0.8)
    ax.annotate(f"FEM skip={d['skip']}", xy=(d["runtime_s"], d["l2"]),
                xytext=(8, 4), textcoords="offset points", fontsize=8.5, color=C_FEM)

# FEM Pareto frontier
fem_x = [d["runtime_s"] for d in fem_skips]
fem_y = [d["l2"]        for d in fem_skips]
ax.plot(fem_x, fem_y, color=C_FEM, linewidth=1.5, linestyle="--", alpha=0.6, label="FEM skip frontier")

# L3 Hybrid
ax.scatter(111.2, 0.085, s=160, color="#9b59b6", zorder=5, marker="D",
           edgecolors="white", linewidth=0.8)
ax.annotate("L3 Hybrid\n(80% PINN)", xy=(111.2, 0.085),
            xytext=(-55, 10), textcoords="offset points", fontsize=8.5, color="#9b59b6")

# PINN levels — x-axis = training time; subsequent inferences ~0s
for i, d in enumerate(pinn_levels):
    ms = 160 + i * 20
    ax.scatter(d["train_s"], d["l2"], s=ms, color=d["color"], zorder=6,
               marker="o", edgecolors="white", linewidth=0.8)
    offset = (10, 5) if i < 2 else (-10, -18)
    ax.annotate(d["label"].replace("\n", " "), xy=(d["train_s"], d["l2"]),
                xytext=offset, textcoords="offset points", fontsize=9,
                color=d["color"], fontweight="bold")

# Subsequent runs are free note
ax.annotate("", xy=(10, 0.013), xytext=(444, 0.013),
            arrowprops=dict(arrowstyle="->", color=C_L9_SF, lw=1.5,
                            connectionstyle="arc3,rad=0.2"))
ax.text(230, 0.004, "Subsequent inferences ≈ 0.01s", ha="center",
        fontsize=8.5, color=C_L9_SF, style="italic")

# Target regions
ax.axhspan(0, 0.05, alpha=0.07, color="green", label="Acceptable error region (L2 < 0.05)")
ax.axvspan(0, 100, alpha=0.05, color="blue",  label="Fast region (< 100s)")

ax.set_xlabel("Runtime (s) — training time for PINN", fontsize=11)
ax.set_ylabel("L2 Relative Error", fontsize=11)
ax.set_title("Speed–Accuracy Trade-off: FEM Skip vs PINN Levels", fontsize=12, fontweight="bold")
ax.set_xlim(-20, 650); ax.set_ylim(-0.01, 0.35)
ax.legend(fontsize=9, loc="upper right")
ax.grid(alpha=0.3)

plt.tight_layout()
plt.savefig(OUT / "fem_pinn_pareto.png", dpi=150, bbox_inches="tight")
plt.close()
print("✓ fem_pinn_pareto.png")

# ════════════════════════════════════════════════════════════════
# Figure 3 — Level Progression (line chart)
# ════════════════════════════════════════════════════════════════
fig, axes = plt.subplots(1, 2, figsize=(13, 5))
fig.patch.set_facecolor(BG)
for ax in axes:
    ax.set_facecolor(AX_BG)

# Left panel: L2 progression by optimizer
level_names = ["L1\nAdam", "L5\nAdam+\nL-BFGS", "L9\nSA-only", "L9\nSA+Fourier"]
bay_l2  = [0.0764, 0.0296, 0.0151, 0.0137]
n2_l2   = [0.2517, 0.0554, 0.0397, 0.0137]
n3_l2   = [0.5129, 0.2586, 0.1789, 0.0668]

x_pos = np.arange(4)
axes[0].plot(x_pos, bay_l2, "o-", color=C_L9_SF,  linewidth=2, markersize=9, label="Bayesian", zorder=5)
axes[0].plot(x_pos, n2_l2,  "s-", color=C_L9_SA,  linewidth=2, markersize=9, label="NSGA-II",  zorder=5)
axes[0].plot(x_pos, n3_l2,  "^-", color="#e74c3c", linewidth=2, markersize=9, label="NSGA-III", zorder=5)

# FEM skip=1 reference line
axes[0].axhline(0.1261, color=C_FEM, linestyle="--", linewidth=1.5,
                label="FEM skip=1", alpha=0.8)
axes[0].axhline(0.05, color="gray", linestyle=":", linewidth=1.2,
                label="Target: L2 < 0.05", alpha=0.7)

# Value labels (Bayesian)
for xi, (b, n2, n3) in enumerate(zip(bay_l2, n2_l2, n3_l2)):
    axes[0].text(xi, b - 0.018, f"{b:.3f}", ha="center", fontsize=7.5, color=C_L9_SF)

axes[0].set_xticks(x_pos)
axes[0].set_xticklabels(level_names, fontsize=10)
axes[0].set_ylabel("L2 Relative Error", fontsize=11)
axes[0].set_title("PINN Level Progression — L2 Error", fontsize=11, fontweight="bold")
axes[0].legend(fontsize=9)
axes[0].grid(alpha=0.3)
axes[0].set_ylim(-0.02, 0.60)

# Right panel: FEM skip speed/error dual-axis bar chart
skip_labels = ["skip=1\n(full FEM)", "skip=2", "skip=4", "skip=6"]
fem_l2s  = [d["l2"]        for d in fem_skips]
fem_time = [d["runtime_s"] for d in fem_skips]

ax2 = axes[1]
ax2r = ax2.twinx()

x_s = np.arange(len(skip_labels))
bars_l2  = ax2.bar(x_s - 0.2, fem_l2s,  0.35, color=C_FEM,    alpha=0.85, label="L2 Error")
bars_rt  = ax2r.bar(x_s + 0.2, fem_time, 0.35, color="#bdc3c7", alpha=0.75, label="Runtime (s)")

# L9 best line
ax2.axhline(0.0137, color=C_L9_SF, linestyle="--", linewidth=2, label="L9 Best (0.0137)")

ax2.set_xticks(x_s)
ax2.set_xticklabels(skip_labels, fontsize=10)
ax2.set_ylabel("L2 Relative Error", fontsize=11)
ax2r.set_ylabel("Runtime (s)", fontsize=11, color="#7f8c8d")
ax2.set_title("FEM Skip: Speed vs Accuracy", fontsize=11, fontweight="bold")
ax2.set_ylim(0, 0.38)
ax2r.set_ylim(0, 220)
ax2.grid(axis="y", alpha=0.3)

lines1, labels1 = ax2.get_legend_handles_labels()
lines2, labels2 = ax2r.get_legend_handles_labels()
ax2.legend(lines1 + lines2, labels1 + labels2, fontsize=9)

plt.tight_layout()
plt.savefig(OUT / "fem_pinn_progression.png", dpi=150, bbox_inches="tight")
plt.close()
print("✓ fem_pinn_progression.png")

# ════════════════════════════════════════════════════════════════
# Figure 4 — Summary Comparison Table
# ════════════════════════════════════════════════════════════════
fig, ax = plt.subplots(figsize=(18, 5.5))
fig.patch.set_facecolor(BG)
ax.axis("off")

rows = [
    # Method, L2, MAE, First Run, Per-Run Cost, FEM Steps (of 21), FEM at Inference, Notes
    ["FEM skip=1 (full)",       "0.126", "43.6°C", "184s", "184s/run", "21 / 21", "Yes (all)", "Reference — every run is expensive"],
    ["FEM skip=2",              "0.108", "33.2°C", "91s",  "91s/run",  "11 / 21", "Yes (52%)", "Slight error increase, 2× speedup"],
    ["FEM skip=4",              "0.204", "57.5°C", "46s",  "46s/run",  "6 / 21",  "Yes (29%)", "Error grows, 4× speedup"],
    ["FEM skip=6",              "0.294", "93.6°C", "28s",  "28s/run",  "4 / 21",  "Yes (19%)", "Unacceptable error"],
    ["L3 Hybrid (80% PINN)",    "~0.09", "~30°C",  "111s", "111s/run", "4 / 20",  "Yes (20%)", "Mixed FEM+PINN per run"],
    ["L1 PINN (Adam)",          "0.076", "39.1°C", "300s", "~0.01s",   "0 / —",   "No",        "Pure PINN — FEM not needed at inference"],
    ["L5 PINN (Adam+L-BFGS)",   "0.030", "14.4°C", "600s", "~0.01s",   "0 / —",   "No",        "L-BFGS refinement improves accuracy"],
    ["L9 SA-only (Bayesian)",   "0.015", "7.8°C",  "404s", "~0.01s",   "0 / —",   "No",        "Self-adaptive loss weights"],
    ["L9 SA+Fourier (NSGA-II)", "0.014", "7.1°C",  "444s", "~0.01s",   "0 / —",   "No",        "Best L2 — 9.2× better than FEM skip=1"],
]

col_labels = ["Method", "L2 Error", "MAE", "First Run", "Per-Run Cost", "FEM Steps\n(of 21)", "FEM at\nInference", "Notes"]

table = ax.table(
    cellText=rows,
    colLabels=col_labels,
    cellLoc="center", loc="center"
)
table.auto_set_font_size(False)
table.set_fontsize(9)
table.scale(1.0, 1.75)

# Set column widths manually (relative units)
col_widths = [0.18, 0.08, 0.07, 0.08, 0.10, 0.10, 0.09, 0.30]
for j, w in enumerate(col_widths):
    for i in range(len(rows) + 1):
        table[i, j].set_width(w)

# Header row
for j in range(len(col_labels)):
    table[0, j].set_facecolor("#2e4057")
    table[0, j].set_text_props(color="white", fontweight="bold")

# FEM rows — grey
for i in range(1, 5):
    for j in range(len(col_labels)):
        table[i, j].set_facecolor("#dce8f0")

# Hybrid row — purple
for j in range(len(col_labels)):
    table[5, j].set_facecolor("#e8d5f5")

# PINN rows — green shades (increasing improvement)
pinn_colors = ["#fff3cd", "#d4edda", "#a8d5a2"]
for ii, ri in enumerate([6, 7, 8]):
    for j in range(len(col_labels)):
        table[ri, j].set_facecolor(pinn_colors[ii])

# Highlight best result (L9 SA+Fourier, L2 column)
table[9, 1].set_facecolor("#28a745")
table[9, 1].set_text_props(color="white", fontweight="bold")

# "No" cells in FEM at Inference — green tint for PINN rows
for i in range(6, 10):
    table[i, 6].set_facecolor("#c3e6cb")
    table[i, 6].set_text_props(color="#155724", fontweight="bold")

# "Yes" cells in FEM at Inference — blue tint for FEM rows
for i in range(1, 6):
    table[i, 6].set_facecolor("#bee5eb")
    table[i, 6].set_text_props(color="#0c5460")

# Left-align Notes column
for i in range(len(rows) + 1):
    table[i, 7].set_text_props(ha="left")

ax.set_title("FEM Time-Stepping Skip vs PINN Levels — Comprehensive Comparison Table",
             fontsize=13, fontweight="bold", pad=20, color="#2e4057")

plt.tight_layout()
plt.savefig(OUT / "fem_pinn_summary_table.png", dpi=150, bbox_inches="tight")
plt.close()
print("✓ fem_pinn_summary_table.png")

print(f"\n✓ All plots saved → {OUT}/")
