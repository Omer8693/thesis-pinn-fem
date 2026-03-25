"""
plot_level9_full.py — Level 9 Kapsamlı Görselleştirme
=======================================================
Grafik listesi:
  Şekil 1 — 2D L2 çubuk karşılaştırması (L1 / L5 / SA-only / SA+Fourier)
  Şekil 2 — 3D L2 çubuk karşılaştırması (SA-only / SA+Fourier)
  Şekil 3 — Tüm optimizer'lar için L2 yakınsama eğrileri (2D, her iki varyant)
  Şekil 4 — Öz-uyumlu ağırlık evrimi (başlangıç → son λ değerleri)
  Şekil 5 — 2D sıcaklık ısı haritaları: Exact / Predicted / Hata (en iyi model)
  Şekil 6 — Tüm 6 eğitim için t=5s anında mutlak hata haritaları
  Şekil 7 — Soğuma eğrisi karşılaştırması: FEM kanalları + analitik + PINN
  Şekil 8 — Temporal skip faydası: L2 doğruluğu → FEM hızlanması
  Şekil 9 — Tam özet tablosu (12 sonucun tamamı)

Tablo başlıkları İngilizce; yorum/etiket Türkçe.
Renk şeması: Level 7 multi-domain grafiklerle aynı
  · Sıcaklık alanı → YlGnBu
  · Hata alanı     → YlOrRd
  · Arka plan      → #f7f1e3 / #fffdf8
"""

import json, math, sys
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import DEVICE, T_END, X_MAX, Y_MAX
from level9_sa_fourier.src.fourier_pinn import FourierPINN

# ── paths ────────────────────────────────────────────────────────────────────
RES   = Path("level9_sa_fourier/results")
PLOTS = RES / "plots"
PLOTS.mkdir(parents=True, exist_ok=True)

X3D, Y3D, Z3D = 1.3, 0.6, 0.4

# ── reference L2 values ──────────────────────────────────────────────────────
L1 = {"bayesian": 0.076, "nsga2": 0.252, "nsga3": 0.513}
L5 = {"bayesian": 0.030, "nsga2": 0.055, "nsga3": 0.259}
OPTS = ["bayesian", "nsga2", "nsga3"]
OPT_ARCH = {
    "bayesian": "Bayesian\nReLU 5×151",
    "nsga2":    "NSGA-II\ntanh 3×153",
    "nsga3":    "NSGA-III\ntanh 3×75",
}

# ── renk paleti (Level 6 & 7 ile aynı stil) ──────────────────────────────────
# Çubuk/çizgi renkleri
C = {
    "l1":     "#E65100",   # Level 1 referansı — turuncu-kırmızı
    "l5":     "#F9A825",   # Level 5 referansı — sarı-turuncu
    "fem":    "#2E7D32",   # FEM doğruluk seviyesi — koyu yeşil
    "sa":     "#90CAF9",   # SA-only — açık mavi
    "sa_f":   "#1565C0",   # SA+Fourier — koyu mavi
    "bg":     "#f7f1e3",   # figür arka planı (Level 7 ile aynı)
    "ax_bg":  "#fffdf8",   # eksen arka planı
    "spine":  "#d8cfbf",   # eksen çerçevesi
    "txt":    "#2f2a24",   # birincil metin
    "tick":   "#4c463f",   # eksen etiketleri
    "box_fc": "#fef6e4",   # not kutusu arka planı
    "box_ec": "#e8c77a",   # not kutusu çerçevesi
}
# Isı haritası renk skalaları (Level 7 ile birebir aynı)
CMAP_SOL = "YlGnBu"   # sıcaklık / çözüm alanı
CMAP_ERR = "YlOrRd"   # hata alanı
OPT_C = {"bayesian": "#1565C0", "nsga2": "#2E7D32", "nsga3": "#E65100"}

# ── helpers ───────────────────────────────────────────────────────────────────

def _load(variant, mode, opt):
    p = RES / variant / mode / opt / "result.json"
    return json.load(open(p)) if p.exists() else None


def _model(variant, mode, opt):
    r = _load(variant, mode, opt)
    if r is None:
        return None, None
    arch = dict(r["arch"])
    if mode == "3d":
        arch["n_input"] = 4
    scales = [T_END, X3D, Y3D, Z3D] if mode == "3d" else [T_END, X_MAX, Y_MAX]
    nf = r.get("n_fourier", 64) if variant == "sa_fourier" else 0
    m = FourierPINN(arch, sigma=r.get("sigma", 1.0),
                    n_fourier=nf, scales=scales).to(DEVICE)
    pt = RES / variant / mode / opt / "model_l9.pt"
    if pt.exists():
        m.load_state_dict(torch.load(pt, map_location=DEVICE, weights_only=False))
    m.eval()
    return m, r


def _style(ax):
    ax.set_facecolor(C["ax_bg"])
    for sp in ax.spines.values():
        sp.set_color(C["spine"]); sp.set_linewidth(0.8)
    ax.tick_params(colors=C["tick"], labelsize=8)
    ax.xaxis.label.set_color(C["tick"])
    ax.yaxis.label.set_color(C["tick"])


def _note(ax, text, loc="upper right"):
    kwarg = dict(transform=ax.transAxes, fontsize=8, color=C["txt"],
                 bbox={"facecolor": C["box_fc"], "edgecolor": C["box_ec"],
                       "boxstyle": "round,pad=0.22"})
    x, y, ha, va = (0.97, 0.96, "right", "top") if loc == "upper right" \
                   else (0.03, 0.96, "left", "top")
    ax.text(x, y, text, ha=ha, va=va, **kwarg)


def T_ref(t):
    """Analytical quenching reference: T(t) = 20 + 520·exp(-1.75e-3·t)"""
    return 20.0 + 520.0 * np.exp(-1.75e-3 * t)


# ═══════════════════════════════════════════════════════════════════════════════
# Fig 1 — 2D L2 bar chart
# ═══════════════════════════════════════════════════════════════════════════════
def fig1_2d():
    fig, ax = plt.subplots(figsize=(10, 5))
    fig.patch.set_facecolor(C["bg"]); ax.set_facecolor(C["ax_bg"])

    x, w = np.arange(3), 0.17
    sa  = [_load("sa_only",   "2d", o)["best_l2"] for o in OPTS]
    sf  = [_load("sa_fourier","2d", o)["best_l2"] for o in OPTS]

    ax.bar(x - 1.5*w, [L1[o] for o in OPTS], w, color=C["l1"], label="Level 1 (NAS baseline)", alpha=0.85)
    ax.bar(x - 0.5*w, [L5[o] for o in OPTS], w, color=C["l5"], label="Level 5 (L-BFGS)",       alpha=0.85)
    ax.bar(x + 0.5*w, sa,                     w, color=C["sa"], label="L9 SA-only",             alpha=0.95, edgecolor="white")
    ax.bar(x + 1.5*w, sf,                     w, color=C["sa_f"],label="L9 SA + Fourier",       alpha=0.95, edgecolor="white")

    ax.axhline(0.05, color=C["fem"], ls="--", lw=1.3, label="FEM accuracy (~5%)")

    for i, o in enumerate(OPTS):
        best = min(sa[i], sf[i])
        if best < L5[o]:
            ax.annotate(f"{L5[o]/best:.1f}×", xy=(x[i]+1.0*w, best - 0.003),
                        ha="center", va="top", fontsize=8.5, color=C["sa_f"],
                        fontweight="bold")

    ax.set_xticks(x + 0.0); ax.set_xticklabels([OPT_ARCH[o] for o in OPTS], fontsize=10)
    ax.set_ylabel("Relative L2 Error", fontsize=11, color=C["txt"])
    ax.set_title("Level 9 — 2D Quenching L2 Comparison\n"
                 "Interior validation [0.2L, 0.8L]  |  Analytic ref: T(t) = 20 + 520·e^{−αt}",
                 fontsize=11, color=C["txt"])
    ax.legend(fontsize=9, framealpha=0.85)
    ax.set_ylim(0, 0.62); ax.grid(axis="y", alpha=0.25)
    _style(ax)
    plt.tight_layout()
    plt.savefig(PLOTS / "fig1_2d_comparison.png", dpi=150, bbox_inches="tight")
    plt.close(); print("✓ fig1_2d_comparison.png")


# ═══════════════════════════════════════════════════════════════════════════════
# Fig 2 — 3D L2 bar chart
# ═══════════════════════════════════════════════════════════════════════════════
def fig2_3d():
    fig, ax = plt.subplots(figsize=(9, 5))
    fig.patch.set_facecolor(C["bg"]); ax.set_facecolor(C["ax_bg"])

    x, w = np.arange(3), 0.28
    sa = [_load("sa_only",   "3d", o)["best_l2"] for o in OPTS]
    sf = [_load("sa_fourier","3d", o)["best_l2"] for o in OPTS]

    ax.bar(x - w/2, sa, w, color=C["sa"],   label="SA-only (3D)",    alpha=0.95, edgecolor="white")
    ax.bar(x + w/2, sf, w, color=C["sa_f"], label="SA + Fourier (3D)",alpha=0.95, edgecolor="white")

    for i in range(3):
        if sf[i] < sa[i]:
            ax.text(x[i]+w/2, sf[i]+0.02, f"↓{sa[i]/sf[i]:.1f}×",
                    ha="center", fontsize=8.5, color=C["sa_f"], fontweight="bold")

    ax.axhline(1.0, color="gray", ls=":", alpha=0.4, label="Trivial (T ≡ T_water)")
    ax.axhline(0.30, color="orange", ls="--", lw=1.2, alpha=0.8, label="Target < 30%")

    ax.set_xticks(x); ax.set_xticklabels([OPT_ARCH[o] for o in OPTS], fontsize=10)
    ax.set_ylabel("Relative L2 Error", fontsize=11, color=C["txt"])
    ax.set_title("Level 9 — 3D Quenching Generalization\n"
                 "New domain: 1.3 × 0.6 × 0.4 m box  |  ref: T(z,t) = 20 + 520·exp(−α(z)·t)",
                 fontsize=11, color=C["txt"])
    ax.legend(fontsize=9); ax.set_ylim(0, 1.15); ax.grid(axis="y", alpha=0.25)
    _style(ax)
    plt.tight_layout()
    plt.savefig(PLOTS / "fig2_3d_comparison.png", dpi=150, bbox_inches="tight")
    plt.close(); print("✓ fig2_3d_comparison.png")


# ═══════════════════════════════════════════════════════════════════════════════
# Fig 3 — L2 convergence curves
# ═══════════════════════════════════════════════════════════════════════════════
def fig3_convergence():
    fig, axes = plt.subplots(1, 2, figsize=(13, 5), sharey=True)
    fig.patch.set_facecolor(C["bg"])

    titles  = ["SA-only  (adaptive λ, no Fourier)", "SA + Fourier  (adaptive λ + γ, σ=1.0)"]
    variants= ["sa_only", "sa_fourier"]
    ls_map  = {"bayesian": "-", "nsga2": "--", "nsga3": ":"}

    for ax, variant, title in zip(axes, variants, titles):
        ax.set_facecolor(C["ax_bg"])
        for opt in OPTS:
            r = _load(variant, "2d", opt)
            if r is None or not r.get("val_history"):
                continue
            vh = r["val_history"]
            ep = [v["epoch"] for v in vh]
            l2 = [v["l2"]    for v in vh]
            ax.semilogy(ep, l2, ls_map[opt], color=OPT_C[opt], lw=2,
                        label=f"{opt.upper()}  (best={r['best_l2']:.4f})")

        for val, col, lbl in [
            (0.076, C["l1"],  "L1 Bayesian (0.076)"),
            (0.030, C["l5"],  "L5 Bayesian (0.030)"),
            (0.050, C["fem"], "FEM ≈ 5%"),
        ]:
            ax.axhline(val, color=col, ls="--", lw=1.1, alpha=0.7, label=lbl)

        ax.set_xlabel("Epoch", fontsize=10, color=C["tick"])
        if ax is axes[0]:
            ax.set_ylabel("L2 Error (log scale)", fontsize=10, color=C["tick"])
        ax.set_title(title, fontsize=10, color=C["txt"])
        ax.legend(fontsize=7.5, framealpha=0.85)
        ax.grid(True, alpha=0.22)
        _style(ax)

    fig.suptitle("Level 9 — 2D L2 Convergence  (30 k epochs · StepLR · Adam)",
                 fontsize=12, color=C["txt"], fontweight="bold")
    plt.tight_layout()
    plt.savefig(PLOTS / "fig3_convergence.png", dpi=150, bbox_inches="tight")
    plt.close(); print("✓ fig3_convergence.png")


# ═══════════════════════════════════════════════════════════════════════════════
# Fig 4 — Self-adaptive weight evolution
# ═══════════════════════════════════════════════════════════════════════════════
def fig4_weights():
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
    fig.patch.set_facecolor(C["bg"])

    lam_k   = ["lambda_phys", "lambda_bc", "lambda_ic"]
    lam_lbl = ["λ_phys", "λ_bc", "λ_ic"]
    init    = [1.0, 10.0, 10.0]
    bw      = 0.19
    x       = np.arange(3)

    for ax, variant, title in zip(axes,
        ["sa_only", "sa_fourier"],
        ["SA-only", "SA + Fourier"]):

        ax.set_facecolor(C["ax_bg"])
        ax.bar(x - 1.5*bw, init, bw, color="gray", alpha=0.45, label="Initial", edgecolor="white")

        for j, opt in enumerate(OPTS):
            r = _load(variant, "2d", opt)
            if r is None: continue
            vals = [r["final_weights"].get(k, 0) for k in lam_k]
            ax.bar(x + (j - 0.5)*bw, vals, bw, color=OPT_C[opt],
                   label=opt.upper(), alpha=0.9, edgecolor="white")

        ax.set_xticks(x); ax.set_xticklabels(lam_lbl, fontsize=12)
        ax.set_ylabel("λ value", fontsize=10, color=C["tick"])
        ax.set_title(f"{title} — Final Self-Adaptive Weights", fontsize=10, color=C["txt"])
        ax.legend(fontsize=9); ax.grid(axis="y", alpha=0.25)
        _style(ax)

    fig.suptitle("Self-Adaptive Weight Evolution: Initial → Final  (30 k epochs)",
                 fontsize=12, color=C["txt"], fontweight="bold")
    plt.tight_layout()
    plt.savefig(PLOTS / "fig4_sa_weights.png", dpi=150, bbox_inches="tight")
    plt.close(); print("✓ fig4_sa_weights.png")


# ═══════════════════════════════════════════════════════════════════════════════
# Şekil 5 — Exact / Predicted / Hata ısı haritaları (en iyi model: SA+Fourier Bayesian)
# Renk şeması: Level 7 multi-domain ile aynı (YlGnBu sıcaklık, YlOrRd hata)
# ═══════════════════════════════════════════════════════════════════════════════
def fig5_heatmaps():
    model, r = _model("sa_fourier", "2d", "bayesian")
    if model is None:
        print("⚠  model bulunamadı, Şekil 5 atlandı"); return

    # Zaman dilimleri: su daldırmanın farklı aşamaları
    t_slices = [2.0, 5.0, 10.0, 20.0]
    NX, NY   = 80, 38                              # grid çözünürlüğü
    x_arr    = np.linspace(0, X_MAX, NX)
    y_arr    = np.linspace(0, Y_MAX, NY)
    XX, YY   = np.meshgrid(x_arr, y_arr)

    fig, axes = plt.subplots(3, 4, figsize=(16, 8))
    fig.patch.set_facecolor(C["bg"])

    for col, tv in enumerate(t_slices):
        # Model tahmini al
        pts = torch.tensor(
            np.stack([np.full(NX * NY, tv), XX.ravel(), YY.ravel()], 1),
            dtype=torch.float32, device=DEVICE)
        with torch.no_grad():
            T_pred = model(pts).cpu().numpy().reshape(NY, NX)

        # Analitik referans (düzgün alan — zamana bağlı soğuma)
        T_exact = T_ref(tv) * np.ones((NY, NX))

        # Mutlak hata (°C) — yüzde değil, fiziksel birim daha anlamlı
        err_abs = np.abs(T_pred - T_exact)

        # Sıcaklık skalası: ref ve tahmin aynı eksenle
        vT_min = min(T_pred.min(), T_exact.min()) - 2
        vT_max = max(T_pred.max(), T_exact.max()) + 2
        err_max = max(err_abs.max(), 1.0)          # sıfır olmasın

        extent = [0, X_MAX, 0, Y_MAX]
        kw_T = dict(extent=extent, origin="lower", cmap=CMAP_SOL,
                    aspect="auto", vmin=vT_min, vmax=vT_max)
        kw_E = dict(extent=extent, origin="lower", cmap=CMAP_ERR,
                    aspect="auto", vmin=0, vmax=err_max)

        # Satır 0 — analitik referans sıcaklık alanı
        im0 = axes[0, col].imshow(T_exact, **kw_T)
        axes[0, col].set_title(f"t = {tv:.0f} s", fontsize=10.5,
                                color=C["txt"], fontweight="bold")
        plt.colorbar(im0, ax=axes[0, col], fraction=0.04, pad=0.03, label="°C")

        # Satır 1 — PINN tahmin sıcaklık alanı
        im1 = axes[1, col].imshow(T_pred, **kw_T)
        plt.colorbar(im1, ax=axes[1, col], fraction=0.04, pad=0.03, label="°C")

        # Satır 2 — mutlak hata alanı (°C)
        im2 = axes[2, col].imshow(err_abs, **kw_E)
        plt.colorbar(im2, ax=axes[2, col], fraction=0.04, pad=0.03, label="|ΔT| °C")
        axes[2, col].set_xlabel("x [m]", fontsize=8, color=C["tick"])

        for row_ax in axes[:, col]:
            _style(row_ax)

    # Satır etiketleri (Türkçe açıklama)
    axes[0, 0].set_ylabel("Analytic Reference\ny [m]", fontsize=9, color=C["txt"])
    axes[1, 0].set_ylabel("PINN Prediction\n(SA+Fourier · Bayesian)\ny [m]", fontsize=9, color=C["txt"])
    axes[2, 0].set_ylabel("Absolute Error |ΔT|\ny [m]", fontsize=9, color=C["txt"])

    fig.suptitle(
        "2D Quenching — Reference vs Prediction vs Error  (SA+Fourier · Bayesian · L2=0.025)\n"
        "Domain: 1.3 × 0.6 m  |  Colourmap: YlGnBu (temperature) · YlOrRd (error)",
        fontsize=11, color=C["txt"], fontweight="bold")
    plt.tight_layout()
    plt.savefig(PLOTS / "fig5_heatmaps.png", dpi=150, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    plt.close(); print("✓ fig5_heatmaps.png")


# ═══════════════════════════════════════════════════════════════════════════════
# Şekil 6 — t=5s anındaki mutlak hata haritaları (tüm 6 model)
# Her iki satır için ortak renk skalası → adil karşılaştırma
# Renk: YlOrRd (Level 7 hata haritalarıyla aynı)
# ═══════════════════════════════════════════════════════════════════════════════
def fig6_error_maps():
    tv = 5.0   # su daldırmanın kritik anı: en hızlı soğuma bölgesi
    NX, NY = 80, 38
    x_arr  = np.linspace(0, X_MAX, NX)
    y_arr  = np.linspace(0, Y_MAX, NY)
    XX, YY = np.meshgrid(x_arr, y_arr)
    pts    = torch.tensor(
        np.stack([np.full(NX * NY, tv), XX.ravel(), YY.ravel()], 1),
        dtype=torch.float32, device=DEVICE)
    T_exact = T_ref(tv)   # analitik referans — tek skaler

    # Tüm modellerin max hatasını önceden hesapla → ortak skala
    all_err = []
    models_cache = {}
    for variant in ["sa_only", "sa_fourier"]:
        for opt in OPTS:
            m, r = _model(variant, "2d", opt)
            if m is None: continue
            with torch.no_grad():
                T_pred = m(pts).cpu().numpy().reshape(NY, NX)
            err = np.abs(T_pred - T_exact)
            all_err.append(err.max())
            models_cache[(variant, opt)] = (T_pred, r)
    vmax_shared = float(np.percentile(all_err, 90))  # aykırı değerleri kes

    fig, axes = plt.subplots(2, 3, figsize=(14, 7))
    fig.patch.set_facecolor(C["bg"])

    for row, variant in enumerate(["sa_only", "sa_fourier"]):
        for col, opt in enumerate(OPTS):
            ax = axes[row, col]
            if (variant, opt) not in models_cache:
                ax.text(0.5, 0.5, "No result", ha="center", va="center"); continue

            T_pred, r = models_cache[(variant, opt)]
            err = np.abs(T_pred - T_exact)

            im = ax.imshow(err, extent=[0, X_MAX, 0, Y_MAX], origin="lower",
                           cmap=CMAP_ERR, aspect="auto", vmin=0, vmax=vmax_shared)
            ax.set_title(f"{opt.upper()}  ·  L2 = {r['best_l2']:.4f}",
                         fontsize=10, color=C["txt"], fontweight="bold")
            plt.colorbar(im, ax=ax, fraction=0.04, pad=0.03, label="|ΔT| °C")

            if col == 0:
                lbl = "SA-only" if variant == "sa_only" else "SA + Fourier"
                ax.set_ylabel(f"{lbl}\ny [m]", fontsize=9, color=C["txt"])
            if row == 1:
                ax.set_xlabel("x [m]", fontsize=8, color=C["tick"])
            _style(ax)

    fig.suptitle(
        f"2D Quenching — Absolute Error |T_PINN − T_ref| [°C]  @  t = {tv:.0f} s\n"
        f"Shared colour scale 0 – {vmax_shared:.0f} °C  |  Top: SA-only  ·  Bottom: SA + Fourier",
        fontsize=11, color=C["txt"], fontweight="bold")
    plt.tight_layout()
    plt.savefig(PLOTS / "fig6_error_maps.png", dpi=150, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    plt.close(); print("✓ fig6_error_maps.png")


# ═══════════════════════════════════════════════════════════════════════════════
# Fig 7 — Cooling curve comparison
# ═══════════════════════════════════════════════════════════════════════════════
def fig7_cooling():
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    fig.patch.set_facecolor(C["bg"])

    # ── left: FEM water tank channels (Mortensen 2026 Fig 7) ──
    ax = axes[0]; ax.set_facecolor(C["ax_bg"])
    try:
        with open("level1_single_shot/results/baseline/baseline_data.json") as f:
            bl = json.load(f)
        d   = bl["fig7_water_temp"]
        t_f = np.array(d["time_s"])
        for ch, col, lbl in [
            ("Channel_1",  "#1565C0", "Channel 1 (surface)"),
            ("Channel_6",  "#2E7D32", "Channel 6 (middle)"),
            ("Channel_12", "#E65100", "Channel 12 (bottom)"),
        ]:
            ax.plot(t_f, d[ch], "o-", color=col, ms=5, lw=1.5, label=lbl)
        ax.axhline(20, color="gray", ls="--", alpha=0.6, label="T_water,0 = 20 °C")
        ax.set_title("FEM Measurement — Water Tank Temperature\n(Mortensen 2026, Fig 7)", fontsize=10, color=C["txt"])
    except Exception:
        ax.text(0.5, 0.5, "baseline_data.json not found", ha="center", va="center")
    ax.set_xlabel("Time [s]", fontsize=10, color=C["tick"])
    ax.set_ylabel("Water temperature [°C]", fontsize=10, color=C["tick"])
    ax.legend(fontsize=9); ax.grid(alpha=0.25); _style(ax)

    # ── right: part cooling curves — analytic + all L9 models ──
    ax2 = axes[1]; ax2.set_facecolor(C["ax_bg"])
    t_plot = np.linspace(0, T_END, 300)
    ax2.plot(t_plot, T_ref(t_plot), "k-", lw=2.5, label="Analytic T(t)")

    ls_map = {"bayesian": "-", "nsga2": "--", "nsga3": ":"}
    for variant, suffix in [("sa_only", "SA"), ("sa_fourier", "SA+F")]:
        for opt in OPTS:
            m, _ = _model(variant, "2d", opt)
            if m is None: continue
            t_t = torch.tensor(t_plot.reshape(-1,1), dtype=torch.float32, device=DEVICE)
            xc  = torch.full_like(t_t, 0.65)
            yc  = torch.full_like(t_t, 0.30)
            with torch.no_grad():
                T_p = m(torch.cat([t_t, xc, yc], 1)).cpu().numpy().ravel()
            ax2.plot(t_plot, T_p, ls_map[opt], color=OPT_C[opt], lw=1.4, alpha=0.8,
                     label=f"{opt.upper()} {suffix}")

    ax2.set_xlabel("Time [s]", fontsize=10, color=C["tick"])
    ax2.set_ylabel("Temperature [°C]", fontsize=10, color=C["tick"])
    ax2.set_title("Part Centre Cooling Curve  (x=0.65 m, y=0.30 m)\nAll L9 models vs analytic", fontsize=10, color=C["txt"])
    ax2.legend(fontsize=7.5, ncol=2); ax2.grid(alpha=0.25); _style(ax2)

    fig.suptitle("FEM Reference + PINN Cooling — A356 Aluminium Quenching",
                 fontsize=12, color=C["txt"], fontweight="bold")
    plt.tight_layout()
    plt.savefig(PLOTS / "fig7_cooling_curves.png", dpi=150, bbox_inches="tight")
    plt.close(); print("✓ fig7_cooling_curves.png")


# ═══════════════════════════════════════════════════════════════════════════════
# Fig 8 — Temporal skip benefit
# ═══════════════════════════════════════════════════════════════════════════════
def fig8_skip():
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    fig.patch.set_facecolor(C["bg"])

    thr = 0.15          # L2 threshold used for skip decision

    # ── left: L2 → max skip steps ──
    ax = axes[0]; ax.set_facecolor(C["ax_bg"])
    l2_r = np.linspace(0.005, 0.55, 400)
    sk   = np.floor(thr / l2_r).clip(1, 25)
    ax.plot(l2_r, sk, color=C["sa_f"], lw=2.5)
    ax.axvline(0.05, color=C["fem"], ls="--", lw=1.2, label="FEM ~5%")

    markers = [
        ("L1 Bay",     0.076,  C["l1"]),
        ("L5 Bay",     0.030,  C["l5"]),
        ("L9 SA Bay",  0.0151, C["sa_f"]),
        ("L9 SA+F Bay",0.0253, C["sa"]),
        ("L9 SA+F N2", 0.0137, OPT_C["nsga2"]),
    ]
    for lbl, l2v, col in markers:
        sk_v = max(1, int(np.floor(thr / l2v)))
        ax.plot(l2v, sk_v, "o", color=col, ms=9, zorder=5)
        ax.annotate(f"{lbl}\nk={sk_v}", (l2v, sk_v + 0.5),
                    fontsize=7, ha="center", color=col, fontweight="bold")

    ax.set_xlabel("Relative L2 Error", fontsize=10, color=C["tick"])
    ax.set_ylabel("Max skip steps  k", fontsize=10, color=C["tick"])
    ax.set_title("PINN Accuracy → FEM Timestep Skip\nk = ⌊threshold / L2⌋,  thr = 0.15",
                 fontsize=10, color=C["txt"])
    ax.legend(fontsize=9); ax.grid(alpha=0.25); _style(ax)

    # ── right: speedup bar chart ──
    ax2 = axes[1]; ax2.set_facecolor(C["ax_bg"])
    n_total = 30; p_frac = 0.01

    entries = [
        ("L1 Bay (0.076)",   0.076,  C["l1"]),
        ("L5 Bay (0.030)",   0.030,  C["l5"]),
        ("L9 SA  (0.0151)",  0.0151, C["sa_f"]),
        ("L9 SA+F N2 (0.014)",0.0137,OPT_C["nsga2"]),
    ]
    for lbl, l2v, col in entries:
        k       = max(1, int(np.floor(thr / l2v)))
        n_fem   = math.ceil(n_total / (k + 1))
        n_pinn  = n_total - n_fem
        cost    = n_fem * 1.0 + n_pinn * p_frac
        speedup = n_total / cost
        bar = ax2.barh(lbl, speedup, color=col, alpha=0.88, edgecolor="white")
        ax2.text(speedup + 0.1, lbl, f"{speedup:.1f}×",
                 va="center", fontsize=9, color=C["txt"])

    ax2.set_xlabel("Speedup factor vs full FEM", fontsize=10, color=C["tick"])
    ax2.set_title("SA-PINN → FEM Simulation Speedup\n30-step quenching, PINN cost = 1% FEM",
                  fontsize=10, color=C["txt"])
    ax2.grid(axis="x", alpha=0.25); _style(ax2)

    fig.suptitle("Temporal Skip Benefit: L9 Accuracy Impact on FEM Efficiency",
                 fontsize=12, color=C["txt"], fontweight="bold")
    plt.tight_layout()
    plt.savefig(PLOTS / "fig8_temporal_skip.png", dpi=150, bbox_inches="tight")
    plt.close(); print("✓ fig8_temporal_skip.png")


# ═══════════════════════════════════════════════════════════════════════════════
# Fig 9 — Full summary table
# ═══════════════════════════════════════════════════════════════════════════════
def fig9_table():
    fig, ax = plt.subplots(figsize=(14, 5.5))
    fig.patch.set_facecolor(C["bg"]); ax.axis("off")

    rows = []
    for mode in ["2d", "3d"]:
        for opt in OPTS:
            r_sa = _load("sa_only",   mode, opt)
            r_sf = _load("sa_fourier",mode, opt)
            l1v  = f"{L1[opt]:.3f}" if mode == "2d" else "—"
            l5v  = f"{L5[opt]:.3f}" if mode == "2d" else "—"
            sa_v = f"{r_sa['best_l2']:.4f}" if r_sa else "—"
            sf_v = f"{r_sf['best_l2']:.4f}" if r_sf else "—"
            if mode == "2d" and r_sa and r_sf:
                best = min(r_sa["best_l2"], r_sf["best_l2"])
                imp  = f"{L5[opt]/best:.1f}×"
            else:
                imp = "—"
            rows.append([opt.upper(), mode.upper(), l1v, l5v, sa_v, sf_v, imp])

    cols = ["Optimizer", "Mode", "L1 Ref", "L5 Ref", "SA-only L2", "SA+Fourier L2", "Best / L5"]
    tbl  = ax.table(cellText=rows, colLabels=cols, cellLoc="center", loc="center")
    tbl.auto_set_font_size(False); tbl.set_fontsize(10); tbl.scale(1.15, 1.9)

    for j in range(len(cols)):
        tbl[0, j].set_facecolor("#1565C0")
        tbl[0, j].set_text_props(color="white", fontweight="bold")

    for i, row in enumerate(rows, 1):
        if row[1] == "2D":
            best_col = 4 if (row[4] != "—" and row[5] != "—" and
                             float(row[4]) <= float(row[5])) else 5
            tbl[i, best_col].set_facecolor("#C8E6C9")
            tbl[i, best_col].set_text_props(fontweight="bold")
        else:
            for j in range(len(cols)):
                tbl[i, j].set_facecolor("#E3F2FD")

    ax.set_title("Level 9 — SA-PINN + Fourier Feature: Full Results Summary\n"
                 "(Green = best L2 per row  |  Blue = 3D generalization)",
                 fontsize=12, color=C["txt"], fontweight="bold", pad=18)
    plt.tight_layout()
    plt.savefig(PLOTS / "fig9_summary_table.png", dpi=150, bbox_inches="tight")
    plt.close(); print("✓ fig9_summary_table.png")


# ─── main ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n" + "═"*55)
    print("  Level 9 — Full Visualization (English)")
    print("═"*55 + "\n")
    fig1_2d()
    fig2_3d()
    fig3_convergence()
    fig4_weights()
    fig5_heatmaps()
    fig6_error_maps()
    fig7_cooling()
    fig8_skip()
    fig9_table()
    print(f"\n  All plots saved → {PLOTS}/")
