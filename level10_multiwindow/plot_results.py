"""
plot_results.py — Level 10 MSWP Result Plots
=============================================
Four panels:
  Fig 1 — Cooling curve: T_mean(t) — PINN_WIDE vs FEM reference
  Fig 2 — Per-segment MAE: error in each time window
  Fig 3 — Cross-level MAE comparison: L2, L5, L10
  Fig 4 — MSWP vs Sequential PINN: improvement % vs k_skip

Usage:
    python level10_multiwindow/plot_results.py
    python level10_multiwindow/plot_results.py --k 3
    python level10_multiwindow/plot_results.py --k 3 --end_sup
"""

import argparse
import json
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

# ── Style ───────────────────────────────────────────────────────────────────
plt.rcParams.update({
    "font.family":       "DejaVu Sans",
    "font.size":         11,
    "axes.spines.top":   False,
    "axes.spines.right": False,
    "axes.grid":         True,
    "grid.alpha":        0.3,
    "grid.linestyle":    "--",
    "figure.dpi":        150,
})

ROOT    = Path(__file__).parent.parent
L10_DIR = Path(__file__).parent
RESULTS = L10_DIR / "results"

COLORS = {
    "fem":  "#2196F3",   # blue  — FEM reference
    "mswp": "#4CAF50",   # green — MSWP
    "seq":  "#FF5722",   # red   — sequential PINN
    "l2":   "#00BCD4",   # cyan  — Level 2
    "l5":   "#8BC34A",   # light green — Level 5
    "l10":  "#F44336",   # red   — Level 10
}


# ── Data loaders ────────────────────────────────────────────────────────────

def load_l10(k: int, end_sup: bool) -> dict:
    path = RESULTS / f"full_series_k{k}_endsup{int(end_sup)}.json"
    # Fallback: legacy filename without end_sup suffix
    if not path.exists():
        path = RESULTS / f"full_series_k{k}.json"
    return json.load(open(path)) if path.exists() else None


def load_l2_skip_table() -> dict:
    path = ROOT / "level2_timestepper" / "results" / "skip_table.json"
    return json.load(open(path)) if path.exists() else {}


def load_l5_comparison() -> dict:
    out = {}
    for arch in ["bayesian", "nsga2", "nsga3"]:
        path = ROOT / "level5_refinement" / "results" / arch / "comparison.json"
        if path.exists():
            out[arch] = json.load(open(path))
    return out


def load_compare_results() -> list:
    files = sorted(RESULTS.glob("compare_k*.json"))
    return [json.load(open(f)) for f in files]


# ── Fig 1: Cooling curve ────────────────────────────────────────────────────

def fig_cooling_curve(ax, d10: dict, k: int, end_sup: bool):
    h = [s for s in d10["history"] if s["source"] != "fem_ic"]

    t_pts    = [s["t_end"]       for s in h]
    T_fem    = [s["T_mean_fem"]  for s in h]
    T_pred   = [s["T_mean_pred"] for s in h]

    # 2D analytical reference: spatial-mean cooling curve
    # T_mean(t) = T_w + C * (T_init - T_w) * exp(-alpha_2d * t)
    # C = sin(mu_x*Lx/2)/(mu_x*Lx/2) * sin(mu_y*Ly/2)/(mu_y*Ly/2)
    _MU_X    = 2.31;  _MU_Y = 4.80
    _ALPHA2D = 150.0 * (_MU_X**2 + _MU_Y**2) / 2.4e6   # ~1.77e-3 /s
    _Cx = np.sinc(_MU_X * 0.65 / np.pi)   # sinc(x) = sin(pi*x)/(pi*x)
    _Cy = np.sinc(_MU_Y * 0.30 / np.pi)
    _C  = _Cx * _Cy                         # spatial averaging factor ~ 0.457

    t_cont = np.linspace(0, 30, 200)
    T_anal = 20 + _C * 520 * np.exp(-_ALPHA2D * t_cont)

    ax.plot(t_cont, T_anal, "--", color=COLORS["fem"], lw=1.5,
            label="2D Analytical reference (spatial mean)", alpha=0.7)
    ax.plot(t_pts, T_fem,  "o", color=COLORS["fem"],  ms=7, zorder=5,
            label="FEM anchor points")
    ax.plot(t_pts, T_pred, "s--", color=COLORS["mswp"], lw=2, ms=7, zorder=4,
            label=f"MSWP prediction (k={k})")

    # Error arrows
    for tf, tp, tm in zip(t_pts, T_pred, T_fem):
        ax.annotate("", xy=(tf, tm), xytext=(tf, tp),
                    arrowprops=dict(arrowstyle="<->", color="gray", lw=0.8))

    tag = f"k={k}" + (" + end_sup" if end_sup else "")
    ax.set_xlabel("Time [s]")
    ax.set_ylabel("Mean Temperature [deg C]")
    ax.set_title(f"Cooling Curve — MSWP ({tag}) vs FEM Reference")
    ax.legend(framealpha=0.9, fontsize=9)

    all_T = T_fem + T_pred + [float(T_anal[0]), float(T_anal[-1])]
    ax.set_xlim(-0.5, 31)
    ax.set_ylim(min(all_T) - 15, max(all_T) + 15)


# ── Fig 2: Per-segment MAE ───────────────────────────────────────────────────

def fig_segment_mae(ax, d10: dict, k: int):
    h       = [s for s in d10["history"] if s["source"] != "fem_ic"]
    labels  = [f"{int(s['t_start'])}→{int(s['t_end'])}s" for s in h]
    maes    = [s["mae"] for s in h]
    x       = np.arange(len(maes))

    bars = ax.bar(x, maes, color=COLORS["mswp"], edgecolor="white", linewidth=0.5)

    avg = np.mean(maes)
    ax.axhline(avg, color=COLORS["fem"], lw=1.5, ls="--",
               label=f"Mean MAE = {avg:.1f} deg C")

    for bar, mae in zip(bars, maes):
        ax.text(bar.get_x() + bar.get_width() / 2, mae + 0.5,
                f"{mae:.0f}", ha="center", va="bottom", fontsize=8)

    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=40, ha="right", fontsize=8)
    ax.set_ylabel("MAE [deg C]")
    ax.set_title(f"Per-Segment Error — MSWP k={k}")
    ax.legend()


# ── Fig 3: Cross-level comparison ───────────────────────────────────────────

def fig_level_comparison(ax, d_l2: dict, d_l5: dict, d_l10: dict, end_sup: bool):
    """
    Fair cross-level comparison at equivalent FEM anchor frequency.
    L10 k=3 uses FEM every 6s  →  L2 skip=4 (4×1.5s=6s) is the fair match.
    L5 uses no FEM anchors (full-horizon single PINN).
    All evaluated against 2D analytical FEM reference.
    """
    entries = []   # (label, MAE, color, hatch)

    if d_l2:
        # skip=4: FEM every 6s — same anchor frequency as L10 k=3
        for arch, rows in d_l2.items():
            for r in rows:
                if r["skip"] == 4:
                    entries.append((
                        f"L2 {arch}\nskip=4\n(6s anchor)",
                        r["mae_C"], COLORS["l2"], ""
                    ))
        # Also show skip=1 (full FEM) for reference
        best_skip1 = min(
            (r for rows in d_l2.values() for r in rows if r["skip"] == 1),
            key=lambda r: r["mae_C"],
        )
        entries.insert(0, ("L2 best\nskip=1\n(1.5s anchor)",
                           best_skip1["mae_C"], COLORS["l2"], "//"))

    if d_l5:
        # All 3 architectures
        for arch in ["bayesian", "nsga2", "nsga3"]:
            if arch in d_l5:
                mae = d_l5[arch]["level5_adam_lbfgs"]["MAE_C"]
                if np.isfinite(mae):
                    entries.append((f"L5 {arch}\n(no FEM)", mae, COLORS["l5"], ""))

    if d_l10:
        mae_l10 = d_l10["summary"]["mean_mae"]
        tag = "k=3\n+end_sup" if end_sup else "k=3"
        entries.append((f"L10 MSWP\n{tag}\n(6s anchor)", mae_l10, COLORS["l10"], ""))

    if not entries:
        ax.text(0.5, 0.5, "No data", transform=ax.transAxes, ha="center")
        return

    labels  = [e[0] for e in entries]
    values  = [e[1] for e in entries]
    colors  = [e[2] for e in entries]
    hatches = [e[3] for e in entries]
    x = np.arange(len(labels))

    bars = ax.bar(x, values, color=colors, hatch=hatches,
                  edgecolor="white", linewidth=0.5, width=0.65)

    for bar, val, h in zip(bars, values, hatches):
        ax.text(bar.get_x() + bar.get_width() / 2, val + 1.0,
                f"{val:.1f}", ha="center", va="bottom", fontsize=8, fontweight="bold")

    # Highlight fair comparison pair
    ax.axvline(len([e for e in entries if "L2" in e[0]]) - 0.5,
               color="gray", ls=":", lw=1.0, alpha=0.6)
    ax.axvline(len([e for e in entries if "L2" in e[0] or "L5" in e[0]]) - 0.5,
               color="gray", ls=":", lw=1.0, alpha=0.6)

    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=8)
    ax.set_ylabel("MAE [deg C]")
    ax.set_title("Cross-Level MAE Comparison\n(2D FEM Reference, all methods)")

    legend_handles = [
        mpatches.Patch(color=COLORS["l2"],  label="Level 2 — NAS Time-Stepper"),
        mpatches.Patch(color=COLORS["l5"],  label="Level 5 — Adam+L-BFGS"),
        mpatches.Patch(color=COLORS["l10"], label="Level 10 — MSWP (this work)"),
    ]
    ax.legend(handles=legend_handles, fontsize=8, loc="upper right")
    ax.set_ylim(0, max(values) * 1.2)


# ── Fig 4: MSWP vs Sequential ───────────────────────────────────────────────

def fig_mswp_vs_seq(ax, compare_results: list):
    if not compare_results:
        ax.text(0.5, 0.5, "Run --sweep to generate comparison data",
                transform=ax.transAxes, ha="center", fontsize=10, color="gray")
        return

    # Group by k_skip, average over multiple t_start values
    grouped = defaultdict(list)
    for r in compare_results:
        grouped[r["k_skip"]].append(r)

    ks       = sorted(grouped.keys())
    mae_seq  = [np.mean([r["mae_sequential"] for r in grouped[k]]) for k in ks]
    mae_mswp = [np.mean([r["mae_mswp"]       for r in grouped[k]]) for k in ks]
    improve  = [np.mean([r["improvement_pct"] for r in grouped[k]]) for k in ks]

    x = np.arange(len(ks))
    w = 0.35

    ax.bar(x - w/2, mae_seq,  w, label="Sequential PINN", color=COLORS["seq"],  alpha=0.85)
    ax.bar(x + w/2, mae_mswp, w, label="MSWP (this work)", color=COLORS["mswp"], alpha=0.85)

    # Improvement label above each pair
    for xi, imp, ms, mw in zip(x, improve, mae_seq, mae_mswp):
        top = max(ms, mw)
        clr = "green" if imp > 0 else "red"
        ax.text(xi, top + top * 0.02, f"{imp:+.1f}%",
                ha="center", fontsize=10, color=clr, fontweight="bold")

    ax.set_xticks(x)
    ax.set_xticklabels([f"k={k}" for k in ks])
    ax.set_xlabel("k_skip (FEM steps per PINN window)")
    ax.set_ylabel("MAE at t_end [deg C]")
    ax.set_title("MSWP vs Sequential PINN — t_end MAE")
    ax.legend()


# ── Main ────────────────────────────────────────────────────────────────────

def main(k: int = 3, end_sup: bool = False):
    d10      = load_l10(k, end_sup)
    d_l2     = load_l2_skip_table()
    d_l5     = load_l5_comparison()
    compares = load_compare_results()

    if d10 is None:
        tag = f"--k {k}" + (" --end_sup" if end_sup else "")
        print(f"ERROR: results/full_series_k{k}_endsup{int(end_sup)}.json not found.")
        print(f"Run first:  python level10_multiwindow/main_level10.py --full_series {tag}")
        return

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    tag = f"k={k}" + (" + end_supervision" if end_sup else "")
    fig.suptitle(f"Level 10 — Multi-Step Window PINN (MSWP, {tag})",
                 fontsize=13, fontweight="bold", y=1.01)

    fig_cooling_curve(axes[0, 0], d10, k, end_sup)
    fig_segment_mae(axes[0, 1], d10, k)
    fig_level_comparison(axes[1, 0], d_l2, d_l5, d10, end_sup)
    fig_mswp_vs_seq(axes[1, 1], compares)

    plt.tight_layout()

    out = RESULTS / f"l10_overview_k{k}_endsup{int(end_sup)}.png"
    plt.savefig(out, bbox_inches="tight", dpi=150)
    print(f"Saved: {out}")
    plt.close()

    _print_summary(d10, d_l2, d_l5, k, end_sup)


def _print_summary(d10, d_l2, d_l5, k, end_sup):
    print("\n" + "=" * 62)
    print("SUMMARY — Cross-Level MAE Comparison")
    print("=" * 62)
    print(f"{'Level':<20} {'Method':<28} {'MAE [deg C]':>12}")
    print("-" * 62)

    if d_l2:
        best_s1 = min(
            (r for rows in d_l2.values() for r in rows if r["skip"] == 1),
            key=lambda r: r["mae_C"],
        )
        print(f"{'Level 2':<20} {'NAS PINN, skip=1':<28} {best_s1['mae_C']:>12.2f}")
        s2 = [r for rows in d_l2.values() for r in rows if r["skip"] == 2]
        if s2:
            print(f"{'Level 2':<20} {'NAS PINN, skip=2':<28} {min(r['mae_C'] for r in s2):>12.2f}")

    if d_l5:
        b5 = min(v["level5_adam_lbfgs"]["MAE_C"] for v in d_l5.values())
        print(f"{'Level 5':<20} {'Adam + L-BFGS (best)':<28} {b5:>12.2f}")

    if d10:
        tag = f"MSWP k={k}" + ("+end_sup" if end_sup else "")
        print(f"{'Level 10':<20} {tag:<28} {d10['summary']['mean_mae']:>12.2f}")

    print("=" * 62)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Level 10 MSWP — result plots")
    parser.add_argument("--k",       type=int,  default=3)
    parser.add_argument("--end_sup", action="store_true")
    args = parser.parse_args()
    main(args.k, args.end_sup)
