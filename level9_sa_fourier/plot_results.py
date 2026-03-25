"""
plot_results.py — Level 9 SA-PINN + Fourier Feature Sonuç Grafikleri
"""
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

RESULTS_DIR = Path("level9_sa_fourier/results")
PLOTS_DIR   = Path("level9_sa_fourier/results/plots")
PLOTS_DIR.mkdir(parents=True, exist_ok=True)

L1_REF = {"bayesian": 0.076, "nsga2": 0.252, "nsga3": 0.513}
L5_REF = {"bayesian": 0.030, "nsga2": 0.055, "nsga3": 0.259}

OPTS   = ["bayesian", "nsga2", "nsga3"]
OPT_LABELS = {"bayesian": "Bayesian", "nsga2": "NSGA-II", "nsga3": "NSGA-III"}


def load_result(variant: str, mode: str, opt: str) -> dict:
    p = RESULTS_DIR / variant / mode / opt / "result.json"
    if p.exists():
        with open(p) as f:
            return json.load(f)
    return None


# ─────────────────────────────────────────────────────────────
# Figure 1 — 2D L2 Comparison Bar Chart
# ─────────────────────────────────────────────────────────────

fig, ax = plt.subplots(figsize=(10, 5))

x    = np.arange(len(OPTS))
w    = 0.18
refs = [L1_REF, L5_REF]
ref_labels = ["Level 1", "Level 5"]
ref_colors = ["#d9534f", "#f0ad4e"]

bars_l1  = ax.bar(x - 2*w, [L1_REF[o] for o in OPTS], w, color=ref_colors[0], label="L1 Baseline", alpha=0.85)
bars_l5  = ax.bar(x - 1*w, [L5_REF[o] for o in OPTS], w, color=ref_colors[1], label="L5 (best prior)", alpha=0.85)

sa_l2 = []
fsa_l2 = []
for o in OPTS:
    r = load_result("sa_only", "2d", o)
    sa_l2.append(r["best_l2"] if r else float("nan"))
    r = load_result("sa_fourier", "2d", o)
    fsa_l2.append(r["best_l2"] if r else float("nan"))

bars_sa  = ax.bar(x,       sa_l2,  w, color="#5bc0de", label="L9 SA-only",       alpha=0.9)
bars_fsa = ax.bar(x + 1*w, fsa_l2, w, color="#428bca", label="L9 SA+Fourier",    alpha=0.9)

# Improvement arrows
for i, o in enumerate(OPTS):
    l5 = L5_REF[o]
    sa  = sa_l2[i]
    fsa = fsa_l2[i]
    best = min(sa, fsa)
    if best < l5:
        ax.annotate(f"↓{l5/best:.1f}×", xy=(x[i]+0.5*w, best), fontsize=7,
                    ha="center", va="top", color="#2e4057")

ax.set_xticks(x + 0.5*w)
ax.set_xticklabels([OPT_LABELS[o] for o in OPTS], fontsize=12)
ax.set_ylabel("L2 Relative Error", fontsize=12)
ax.set_title("Level 9: 2D Quenching — SA-PINN + Fourier vs Baselines", fontsize=13, fontweight="bold")
ax.legend(fontsize=10)
ax.set_ylim(0, 0.6)
ax.grid(axis="y", alpha=0.3)

plt.tight_layout()
plt.savefig(PLOTS_DIR / "l9_2d_comparison.png", dpi=150)
plt.close()
print("Saved l9_2d_comparison.png")


# ─────────────────────────────────────────────────────────────
# Figure 2 — 3D L2 Bar Chart
# ─────────────────────────────────────────────────────────────

fig, ax = plt.subplots(figsize=(9, 5))

sa3d_l2 = []
fsa3d_l2 = []
for o in OPTS:
    r = load_result("sa_only", "3d", o)
    sa3d_l2.append(r["best_l2"] if r else float("nan"))
    r = load_result("sa_fourier", "3d", o)
    fsa3d_l2.append(r["best_l2"] if r else float("nan"))

bars_sa3  = ax.bar(x - 0.5*w, sa3d_l2,  w*2, color="#5bc0de", label="L9 SA-only (3D)",    alpha=0.9)
bars_fsa3 = ax.bar(x + 1.5*w, fsa3d_l2, w*2, color="#428bca", label="L9 SA+Fourier (3D)", alpha=0.9)

# Fourier improvement label
for i, o in enumerate(OPTS):
    sa  = sa3d_l2[i]
    fsa = fsa3d_l2[i]
    if fsa < sa:
        ratio = sa / fsa
        ax.annotate(f"Fourier\n{ratio:.1f}×↓", xy=(x[i]+1.5*w, fsa + 0.02),
                    fontsize=7, ha="center", color="#2e4057")

ax.set_xticks(x + 0.5*w)
ax.set_xticklabels([OPT_LABELS[o] for o in OPTS], fontsize=12)
ax.set_ylabel("L2 Relative Error", fontsize=12)
ax.set_title("Level 9: 3D Quenching Generalization — SA-PINN + Fourier", fontsize=13, fontweight="bold")
ax.legend(fontsize=10)
ax.set_ylim(0, 1.1)
ax.axhline(1.0, color="gray", linestyle="--", alpha=0.5, label="Trivial (T=T_water)")
ax.grid(axis="y", alpha=0.3)

plt.tight_layout()
plt.savefig(PLOTS_DIR / "l9_3d_comparison.png", dpi=150)
plt.close()
print("Saved l9_3d_comparison.png")


# ─────────────────────────────────────────────────────────────
# Figure 3 — Summary Table
# ─────────────────────────────────────────────────────────────

fig, ax = plt.subplots(figsize=(12, 5))
ax.axis("off")

rows = []
for mode in ["2d", "3d"]:
    for opt in OPTS:
        r_sa  = load_result("sa_only",   mode, opt)
        r_fsa = load_result("sa_fourier", mode, opt)
        l5 = L5_REF.get(opt) if mode == "2d" else None
        rows.append([
            opt.upper(),
            mode.upper(),
            f"{l5:.3f}" if l5 else "N/A",
            f"{r_sa['best_l2']:.4f}"  if r_sa  else "—",
            f"{r_fsa['best_l2']:.4f}" if r_fsa else "—",
            f"{l5/min(r_sa['best_l2'],r_fsa['best_l2']):.1f}×" if (l5 and r_sa and r_fsa) else "—",
        ])

cols = ["Optimizer", "Mode", "L5 Ref", "SA-only L2", "SA+Fourier L2", "Best vs L5"]
table = ax.table(
    cellText=rows, colLabels=cols,
    cellLoc="center", loc="center"
)
table.auto_set_font_size(False)
table.set_fontsize(10)
table.scale(1.2, 1.8)

# Header style
for j in range(len(cols)):
    table[0, j].set_facecolor("#2e4057")
    table[0, j].set_text_props(color="white", fontweight="bold")

# Highlight best 2D results
for i, row in enumerate(rows, 1):
    if row[1] == "2D":
        table[i, 4].set_facecolor("#d4edda")  # SA+Fourier column green for 2D

ax.set_title("Level 9 — SA-PINN + Fourier Feature Results Summary", fontsize=14, fontweight="bold", pad=20)
plt.tight_layout()
plt.savefig(PLOTS_DIR / "l9_summary_table.png", dpi=150, bbox_inches="tight")
plt.close()
print("Saved l9_summary_table.png")


# ─────────────────────────────────────────────────────────────
# Figure 4 — Lambda evolution for best 2D run
# ─────────────────────────────────────────────────────────────

r_best = load_result("sa_only", "2d", "bayesian")
if r_best and r_best.get("val_history"):
    fig, axes = plt.subplots(1, 2, figsize=(12, 4))

    # L2 over training
    vh = r_best["val_history"]
    epochs = [v["epoch"] for v in vh]
    l2s    = [v["l2"]    for v in vh]
    axes[0].semilogy(epochs, l2s, color="#428bca", linewidth=2)
    axes[0].axhline(L5_REF["bayesian"], color="orange", linestyle="--", label=f"L5 ref = {L5_REF['bayesian']}")
    axes[0].axhline(L1_REF["bayesian"], color="red",    linestyle=":",  label=f"L1 ref = {L1_REF['bayesian']}")
    axes[0].set_xlabel("Epoch")
    axes[0].set_ylabel("L2 Error (log scale)")
    axes[0].set_title("SA-only Bayesian — L2 Convergence")
    axes[0].legend()
    axes[0].grid(True, alpha=0.3)

    # SA weights from training history (via summary)
    fw = r_best.get("final_weights", {})
    if fw:
        labels = ["λ_phys", "λ_bc", "λ_ic"]
        vals   = [fw.get("lambda_phys", 0), fw.get("lambda_bc", 0), fw.get("lambda_ic", 0)]
        inits  = [1.0, 10.0, 10.0]
        x_bar  = np.arange(3)
        axes[1].bar(x_bar - 0.2, inits, 0.35, label="Initial", color="#d9534f", alpha=0.7)
        axes[1].bar(x_bar + 0.2, vals,  0.35, label="Final",   color="#5cb85c", alpha=0.7)
        axes[1].set_xticks(x_bar); axes[1].set_xticklabels(labels, fontsize=12)
        axes[1].set_title("SA-only Bayesian — Self-Adaptive Weights")
        axes[1].set_ylabel("λ value")
        axes[1].legend()
        axes[1].grid(axis="y", alpha=0.3)

    plt.tight_layout()
    plt.savefig(PLOTS_DIR / "l9_training_curve.png", dpi=150)
    plt.close()
    print("Saved l9_training_curve.png")

print(f"\nAll plots saved to {PLOTS_DIR}/")
