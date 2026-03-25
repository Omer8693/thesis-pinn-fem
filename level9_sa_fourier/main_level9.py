"""
main_level9.py — SA-PINN + Fourier Feature İyileştirmesi
=========================================================
Amaç:
  Level 1–5'te NAS tarafından bulunan en iyi mimarileri
  iki yeni teknikle yeniden eğit ve iyileşmeyi ölç:
    1. Fourier Feature Embedding  — spektral önyargıyı giderir
    2. Self-Adaptive Loss Weights — λ_phys, λ_bc, λ_ic otomatik bulunur

Problemler:
  - MODE_2D : A356 alüminyum quenching — T(t,x,y)     [2D, asıl tez problemi]
  - MODE_3D : Dikdörtgen kutu quenching — T(t,x,y,z)  [3D, genelleştirme]

Referans değerler (karşılaştırma için):
  L1  Bayesian  L2=0.076    NSGA-II  L2=0.252    NSGA-III  L2=0.513
  L5  Bayesian  L2=0.030    NSGA-II  L2=0.055    NSGA-III  L2=0.259

Çalıştırma:
  python -m level9_sa_fourier.main_level9 --mode 2d
  python -m level9_sa_fourier.main_level9 --mode 3d
  python -m level9_sa_fourier.main_level9 --mode both
"""

import argparse
import json
import os
import time
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import torch
import torch.nn as nn

from src.config import DEVICE, T_INIT, T_WATER_INIT, X_MAX, Y_MAX, T_END
from problems.quenching import QuenchingProblem

from level9_sa_fourier.src.fourier_pinn import FourierPINN
from level9_sa_fourier.src.sa_loss import SelfAdaptiveWeights, SAQuenchingLoss
from level9_sa_fourier.src.sa_trainer import SATrainer

# ─────────────────────────────────────────────────────────────
# Sabitler
# ─────────────────────────────────────────────────────────────

RESULTS_DIR = Path("level9_sa_fourier/results")
ARCH_DIRS   = {
    "bayesian": "level1_single_shot/results/bayesian/best_arch.json",
    "nsga2":    "level1_single_shot/results/nsga2/best_arch.json",
    "nsga3":    "level1_single_shot/results/nsga3/best_arch.json",
}

# Level 5 referans değerleri (karşılaştırma için)
L5_REFERENCE = {
    "bayesian": 0.030,
    "nsga2":    0.055,
    "nsga3":    0.259,
}

# 3D kutu boyutları (Level 8 rectangular domain ile aynı)
X3D, Y3D, Z3D = 1.3, 0.6, 0.4

# Eğitim parametreleri
N_DOMAIN    = 3000     # kollokasiyon noktası sayısı
N_BOUNDARY  = 600      # sınır noktası sayısı
N_INITIAL   = 600      # başlangıç koşulu noktası sayısı
N_EPOCHS    = 30_000   # epoch sayısı (L5'te 20k, burada 30k)
N_FOURIER   = 64       # Fourier özellik sayısı → 128 boyutlu giriş
SIGMA_2D    = 1.0      # 2D Fourier bant genişliği (gerçek koordinatlar için küçük σ)
SIGMA_3D    = 1.0      # 3D Fourier bant genişliği
PRINT_EVERY = 2000
VAL_EVERY   = 500


# ─────────────────────────────────────────────────────────────
# Bölüm 1 — Mimari Yükleme
# ─────────────────────────────────────────────────────────────

def load_arch(optimizer_name: str) -> Dict:
    """NAS'tan gelen en iyi mimariyi yükle."""
    path = ARCH_DIRS[optimizer_name]
    with open(path) as f:
        arch = json.load(f)
    return arch


def adapt_arch_for_3d(arch: Dict) -> Dict:
    """2D mimariyi 3D'ye uyarla: n_input 3 → 4 (t,x,y,z)."""
    arch3d = dict(arch)
    arch3d["n_input"] = 4
    return arch3d


# ─────────────────────────────────────────────────────────────
# Bölüm 2 — Batch Üreticiler
# ─────────────────────────────────────────────────────────────

def make_batch_2d(n_domain: int, n_bc: int, n_ic: int) -> Dict:
    """
    2D quenching için gerçek koordinatlarda batch üret.
    t∈[0,30], x∈[0,1.3], y∈[0,0.6]
    """
    def rnd(*shape): return torch.rand(*shape, device=DEVICE)

    # İç alan
    t_d = rnd(n_domain,1)*T_END;  x_d = rnd(n_domain,1)*X_MAX;  y_d = rnd(n_domain,1)*Y_MAX
    pts_d = torch.cat([t_d, x_d, y_d], dim=1).requires_grad_(True)

    # Sınır: 4 yüzey
    n_face = n_bc // 4
    t_b    = rnd(n_face*4, 1) * T_END
    f1 = torch.cat([t_b[:n_face],          torch.zeros(n_face,1,device=DEVICE),            rnd(n_face,1)*Y_MAX], dim=1)
    f2 = torch.cat([t_b[n_face:2*n_face],  torch.full((n_face,1),X_MAX,device=DEVICE),     rnd(n_face,1)*Y_MAX], dim=1)
    f3 = torch.cat([t_b[2*n_face:3*n_face], rnd(n_face,1)*X_MAX, torch.zeros(n_face,1,device=DEVICE)],           dim=1)
    f4 = torch.cat([t_b[3*n_face:],         rnd(n_face,1)*X_MAX, torch.full((n_face,1),Y_MAX,device=DEVICE)],    dim=1)
    pts_b = torch.cat([f1,f2,f3,f4], dim=0).requires_grad_(True)

    # IC: t=0
    pts_i = torch.cat([torch.zeros(n_ic,1,device=DEVICE), rnd(n_ic,1)*X_MAX, rnd(n_ic,1)*Y_MAX], dim=1).requires_grad_(True)
    return {"domain": pts_d, "bc": pts_b, "ic": pts_i}


def make_batch_3d(n_domain: int, n_bc: int, n_ic: int) -> Dict:
    """3D kutu quenching — gerçek koordinatlar t,x,y,z."""
    def rnd(*shape): return torch.rand(*shape, device=DEVICE)

    t_d = rnd(n_domain,1)*T_END
    pts_d = torch.cat([t_d, rnd(n_domain,1)*X3D, rnd(n_domain,1)*Y3D, rnd(n_domain,1)*Z3D], dim=1).requires_grad_(True)

    n_face = n_bc // 6
    t_b = rnd(n_face*6,1)*T_END
    slices = [
        torch.cat([t_b[:n_face],           torch.zeros(n_face,1,device=DEVICE),          rnd(n_face,1)*Y3D, rnd(n_face,1)*Z3D], dim=1),
        torch.cat([t_b[n_face:2*n_face],   torch.full((n_face,1),X3D,device=DEVICE),     rnd(n_face,1)*Y3D, rnd(n_face,1)*Z3D], dim=1),
        torch.cat([t_b[2*n_face:3*n_face], rnd(n_face,1)*X3D, torch.zeros(n_face,1,device=DEVICE),          rnd(n_face,1)*Z3D], dim=1),
        torch.cat([t_b[3*n_face:4*n_face], rnd(n_face,1)*X3D, torch.full((n_face,1),Y3D,device=DEVICE),     rnd(n_face,1)*Z3D], dim=1),
        torch.cat([t_b[4*n_face:5*n_face], rnd(n_face,1)*X3D, rnd(n_face,1)*Y3D, torch.zeros(n_face,1,device=DEVICE)],          dim=1),
        torch.cat([t_b[5*n_face:],         rnd(n_face,1)*X3D, rnd(n_face,1)*Y3D, torch.full((n_face,1),Z3D,device=DEVICE)],     dim=1),
    ]
    pts_b = torch.cat(slices, dim=0).requires_grad_(True)
    pts_i = torch.cat([torch.zeros(n_ic,1,device=DEVICE), rnd(n_ic,1)*X3D, rnd(n_ic,1)*Y3D, rnd(n_ic,1)*Z3D], dim=1).requires_grad_(True)
    return {"domain": pts_d, "bc": pts_b, "ic": pts_i}


# ─────────────────────────────────────────────────────────────
# Bölüm 3 — 3D Kayıp Fonksiyonu
# ─────────────────────────────────────────────────────────────

class SAQuenchingLoss3D:
    """
    3D kutu quenching için self-adaptive PINN kayıp fonksiyonu.
    2D versiyonundan farkı: Laplacian 3 boyutlu, sınır norma yönleri 6 yüzey.
    """

    def __init__(self,
                 sa_weights: SelfAdaptiveWeights,
                 T_init:  float = 540.0,
                 T_water: float = 20.0):
        self.sa_w    = sa_weights
        self.T_init  = T_init
        self.T_water = T_water
        from src.physics_model import WaterQuenchHTC
        self.htc     = WaterQuenchHTC()

    def __call__(self, model: nn.Module, batch: Dict) -> Tuple[torch.Tensor, Dict]:

        from src.config import K_THERMAL, RHO_CP
        from level9_sa_fourier.src.sa_loss import PDE_SCALE, BC_SCALE, IC_SCALE
        T_scale = self.T_init - self.T_water  # 520°C

        # ── 1. Fizik kaybı — 3D, gerçek birimler (2D ile aynı yaklaşım) ──
        pts_d = batch["domain"]   # gerçek koordinatlar: t∈[0,30], x∈[0,X3D], ...
        T_d   = model(pts_d)      # T in °C

        grads = torch.autograd.grad(
            T_d, pts_d, grad_outputs=torch.ones_like(T_d), create_graph=True
        )[0]
        dT_dt = grads[:, 0:1]    # dT/dt  [°C/s]
        dT_dx = grads[:, 1:2]    # dT/dx  [°C/m]
        dT_dy = grads[:, 2:3]
        dT_dz = grads[:, 3:4]

        d2x = torch.autograd.grad(dT_dx, pts_d, torch.ones_like(dT_dx), create_graph=True)[0][:, 1:2]
        d2y = torch.autograd.grad(dT_dy, pts_d, torch.ones_like(dT_dy), create_graph=True)[0][:, 2:3]
        d2z = torch.autograd.grad(dT_dz, pts_d, torch.ones_like(dT_dz), create_graph=True)[0][:, 3:4]

        res    = RHO_CP * dT_dt - K_THERMAL * (d2x + d2y + d2z)  # [W/m³]
        L_phys = ((res / PDE_SCALE) ** 2).mean()

        # ── 2. Sınır koşulu — 6 yüzey normalize ──
        pts_b = batch["bc"]
        T_b   = model(pts_b)
        x_b   = pts_b[:, 1:2]; y_b = pts_b[:, 2:3]; z_b = pts_b[:, 3:4]

        T_surf = T_b.detach().clamp(20.0, 600.0)
        T_wat  = torch.full_like(T_surf, self.T_water)
        h_val  = self.htc.htc(T_surf, T_wat)

        grads_b = torch.autograd.grad(
            T_b, pts_b, torch.ones_like(T_b), create_graph=True
        )[0]

        # Use dimensional tolerances (1% of each axis length) for face detection
        nx = torch.where(x_b < 0.01*X3D, torch.tensor(-1.,device=DEVICE),
             torch.where(x_b > 0.99*X3D, torch.tensor(1.,device=DEVICE),  torch.tensor(0.,device=DEVICE)))
        ny = torch.where(y_b < 0.01*Y3D, torch.tensor(-1.,device=DEVICE),
             torch.where(y_b > 0.99*Y3D, torch.tensor(1.,device=DEVICE),  torch.tensor(0.,device=DEVICE)))
        nz = torch.where(z_b < 0.01*Z3D, torch.tensor(-1.,device=DEVICE),
             torch.where(z_b > 0.99*Z3D, torch.tensor(1.,device=DEVICE),  torch.tensor(0.,device=DEVICE)))

        # dT/dn = grads · n  (real coordinates, nx,ny,nz are ±1 unit normals)
        dT_dn  = grads_b[:,1:2]*nx + grads_b[:,2:3]*ny + grads_b[:,3:4]*nz
        robin  = (K_THERMAL * dT_dn + h_val * (T_b - self.T_water)) / BC_SCALE
        L_bc   = (robin ** 2).mean()

        # ── 3. Başlangıç koşulu ──
        pts_i = batch["ic"]
        T_i   = model(pts_i)
        L_ic  = (((T_i - self.T_init) / IC_SCALE) ** 2).mean()

        L_total = self.sa_w(L_phys, L_bc, L_ic)

        details = {
            "L_total": L_total.item(),
            "L_phys":  L_phys.item(),
            "L_bc":    L_bc.item(),
            "L_ic":    L_ic.item(),
            **self.sa_w.weights_dict()
        }
        return L_total, details


# ─────────────────────────────────────────────────────────────
# Bölüm 4 — L2 Doğrulama
# ─────────────────────────────────────────────────────────────

def analytical_T(t: torch.Tensor, alpha: float = 1.75e-3) -> torch.Tensor:
    """T(t) = 20 + 520 · exp(-alpha·t)  — Robin BC temel modu."""
    return 20.0 + 520.0 * torch.exp(-alpha * t)


def make_val_fn_2d() -> callable:
    """
    2D L2 doğrulama — Level 1 ile tutarlı: SADECE iç bölge.
    Koordinatlar bir kere oluşturulur, her çağrıda yeniden kullanılır.
    Bu sayede training RNG bozulmaz.
    """
    torch.manual_seed(42)
    n_val = 500
    coords_v = torch.cat([
        torch.rand(n_val, 1, device=DEVICE) * T_END,
        torch.rand(n_val, 1, device=DEVICE) * (0.6 * X_MAX) + 0.2 * X_MAX,
        torch.rand(n_val, 1, device=DEVICE) * (0.6 * Y_MAX) + 0.2 * Y_MAX,
    ], dim=1)
    T_ref = 20.0 + 520.0 * torch.exp(-1.75e-3 * coords_v[:, 0:1])

    def val_fn(model: nn.Module) -> float:
        model.eval()
        with torch.no_grad():
            T_pred = model(coords_v)
            l2 = (torch.norm(T_pred - T_ref) / (torch.norm(T_ref) + 1e-10)).item()
        model.train()
        return l2

    return val_fn


def make_val_fn_3d() -> callable:
    """
    3D L2 doğrulama — sadece iç bölge [0.2·L, 0.8·L] her eksende.
    Koordinatlar bir kere oluşturulur, her çağrıda yeniden kullanılır.
    """
    torch.manual_seed(0)
    n_val = 500
    coords_v = torch.cat([
        torch.rand(n_val, 1, device=DEVICE) * T_END,
        torch.rand(n_val, 1, device=DEVICE) * (0.6 * X3D) + 0.2 * X3D,
        torch.rand(n_val, 1, device=DEVICE) * (0.6 * Y3D) + 0.2 * Y3D,
        torch.rand(n_val, 1, device=DEVICE) * (0.6 * Z3D) + 0.2 * Z3D,
    ], dim=1)
    t_pts   = coords_v[:, 0:1]
    zn      = coords_v[:, 3:4] / Z3D
    alpha_z = 0.13 + 0.09 * (1.0 - zn)
    T_ref   = 20.0 + 520.0 * torch.exp(-alpha_z * t_pts)

    def val_fn(model: nn.Module) -> float:
        model.eval()
        with torch.no_grad():
            T_pred = model(coords_v)
            l2 = (torch.norm(T_pred - T_ref) / (torch.norm(T_ref) + 1e-10)).item()
        model.train()
        return l2

    return val_fn


# ─────────────────────────────────────────────────────────────
# Bölüm 5 — Tek Deney Koşucusu
# ─────────────────────────────────────────────────────────────

def run_experiment(optimizer_name: str, mode: str, n_epochs: int = N_EPOCHS, use_fourier: bool = True) -> Dict:
    """
    Tek bir optimizer + mode kombinasyonu için tam eğitim.

    mode : "2d" veya "3d"
    Dönüş: sonuç sözlüğü
    """
    is_3d = (mode == "3d")
    print(f"\n{'━'*54}")
    print(f"  {optimizer_name.upper()}  ─  {'3D' if is_3d else '2D'}")
    print(f"{'━'*54}")

    # Mimari yükle
    arch = load_arch(optimizer_name)
    if is_3d:
        arch = adapt_arch_for_3d(arch)

    sigma = SIGMA_3D if is_3d else SIGMA_2D

    # Koordinat normalizasyon ölçekleri (gerçek → [0,1])
    scales_2d = [T_END, X_MAX, Y_MAX]           # [30, 1.3, 0.6]
    scales_3d = [T_END, X3D, Y3D, Z3D]          # [30, 1.3, 0.6, 0.4]
    scales    = scales_3d if is_3d else scales_2d

    # Model ve SA ağırlıkları
    n_fourier_run = N_FOURIER if use_fourier else 0
    model      = FourierPINN(arch, sigma=sigma, n_fourier=n_fourier_run, scales=scales).to(DEVICE)
    sa_weights = SelfAdaptiveWeights().to(DEVICE)

    tag = f"Fourier σ={sigma}" if use_fourier else "SA-only (Fourier yok)"
    print(f"  Mimari   : {arch['n_layers']} katman × {arch['neurons'][0]} nöron "
          f"({arch['activation']})  |  {'3D' if is_3d else '2D'} {tag}")
    print(f"  Parametre: {model.n_params():,}  (Fourier gömme dahil)")

    # Kayıp fonksiyonu
    if is_3d:
        loss_fn   = SAQuenchingLoss3D(sa_weights)
        get_batch = lambda ep: make_batch_3d(N_DOMAIN, N_BOUNDARY, N_INITIAL)
    else:
        # 2D: varolan QuenchingProblem batch üreticisini kullan
        # (normals dahil, doğru normalizasyon ile)
        problem   = QuenchingProblem()
        loss_fn   = SAQuenchingLoss(sa_weights)
        _batch_fn = problem.make_batch_fn(
            n_domain=N_DOMAIN, n_boundary=N_BOUNDARY, n_initial=N_INITIAL,
            time_mode="full"
        )
        get_batch = lambda ep: _batch_fn(ep)

    # Doğrulama fonksiyonu — coords tek seferlik oluşturulur
    val_fn = make_val_fn_3d() if is_3d else make_val_fn_2d()

    # Eğitici
    trainer = SATrainer(
        model=model,
        sa_weights=sa_weights,
        loss_fn=loss_fn,
        lr_model=1e-3,
        lr_lambda=1e-4,
        T_0=5000,
        T_mult=2
    )

    t0 = time.time()
    result = trainer.train(
        get_batch=get_batch,
        n_epochs=n_epochs,
        val_fn=val_fn,
        val_every=VAL_EVERY,
        print_every=PRINT_EVERY
    )
    elapsed = time.time() - t0

    # Referansla karşılaştır
    l5_ref = L5_REFERENCE.get(optimizer_name, None)
    best_l2 = result["best_l2"]
    improvement = f"{l5_ref/best_l2:.2f}×" if l5_ref else "—"

    print(f"\n  L5 referans L2 : {l5_ref}")
    print(f"  L9 SA-Fourier  : {best_l2:.4f}")
    print(f"  İyileşme       : {improvement}")
    print(f"  Eğitim süresi  : {elapsed:.0f}s")

    # Kayıp ağırlıklarını raporla
    w = sa_weights.weights_dict()
    print(f"  Son λ değerleri: phys={w['lambda_phys']:.2f}  "
          f"bc={w['lambda_bc']:.2f}  ic={w['lambda_ic']:.2f}")

    # Model kaydet
    variant = "sa_fourier" if use_fourier else "sa_only"
    out_dir = RESULTS_DIR / variant / mode / optimizer_name
    out_dir.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), out_dir / "model_l9.pt")

    summary = {
        "optimizer":    optimizer_name,
        "mode":         mode,
        "arch":         arch,
        "n_params":     model.n_params(),
        "sigma":        sigma,
        "n_fourier":    N_FOURIER,
        "n_epochs":     n_epochs,
        "variant":      "sa_fourier" if use_fourier else "sa_only",
        "best_l2":      best_l2,
        "l5_reference": l5_ref,
        "improvement_vs_l5": float(l5_ref / best_l2) if l5_ref else None,
        "elapsed_s":    elapsed,
        "final_weights": w,
        "val_history":  result["history"]["l2"],
    }

    with open(out_dir / "result.json", "w") as f:
        json.dump(summary, f, indent=2)

    return summary


# ─────────────────────────────────────────────────────────────
# Bölüm 6 — Ana Fonksiyon
# ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Level 9 — SA-PINN + Fourier Feature İyileştirmesi"
    )
    parser.add_argument(
        "--mode", choices=["2d", "3d", "both"], default="both",
        help="Çalıştırma modu: 2d | 3d | both (varsayılan: both)"
    )
    parser.add_argument(
        "--optimizer", choices=["bayesian", "nsga2", "nsga3", "all"], default="all",
        help="Hangi optimizer (varsayılan: all)"
    )
    parser.add_argument(
        "--epochs", type=int, default=N_EPOCHS,
        help=f"Epoch sayısı (varsayılan: {N_EPOCHS})"
    )
    parser.add_argument(
        "--no-fourier", action="store_true",
        help="Fourier gömme kullanma — sadece SA ağırlıkları test et"
    )
    args = parser.parse_args()

    # Epoch sayısını güncelle
    n_epochs_run = args.epochs

    optimizers = ["bayesian", "nsga2", "nsga3"] if args.optimizer == "all" \
                 else [args.optimizer]
    modes = ["2d", "3d"] if args.mode == "both" else [args.mode]

    print(f"\n{'═'*54}")
    print(f"  LEVEL 9 — SA-PINN + FOURIER FEATURE")
    print(f"  Device  : {DEVICE}")
    print(f"  Modes   : {modes}")
    print(f"  Optimiz.: {optimizers}")
    print(f"  Epochs  : {n_epochs_run:,}")
    print(f"{'═'*54}")

    use_fourier = not args.no_fourier
    all_results = []
    for mode in modes:
        for opt in optimizers:
            res = run_experiment(opt, mode, n_epochs=n_epochs_run, use_fourier=use_fourier)
            all_results.append(res)

    # Özet tablo
    print(f"\n{'═'*70}")
    print(f"  ÖZET TABLO")
    print(f"{'═'*70}")
    print(f"  {'Opt':10} {'Mode':5} {'L5 Ref':10} {'L9 L2':10} {'İyileşme':12} {'Süre':8}")
    print(f"  {'-'*65}")
    for r in all_results:
        imp = f"{r['improvement_vs_l5']:.2f}×" if r["improvement_vs_l5"] else "—"
        print(
            f"  {r['optimizer']:10} {r['mode']:5} "
            f"{str(r['l5_reference']):10} "
            f"{r['best_l2']:.4f}     "
            f"{imp:12} "
            f"{r['elapsed_s']:.0f}s"
        )
    print(f"{'═'*70}")

    # Tüm sonuçları kaydet
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    variant = "sa_fourier" if use_fourier else "sa_only"
    with open(RESULTS_DIR / f"level9_summary_{variant}.json", "w") as f:
        json.dump(all_results, f, indent=2)

    print(f"\n  Sonuçlar: {RESULTS_DIR}/")


if __name__ == "__main__":
    main()
