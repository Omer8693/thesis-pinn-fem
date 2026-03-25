"""
sa_loss.py — Self-Adaptive PINN Kayıp Fonksiyonu
==================================================
Varolan QuenchingProblem'in çalışan kayıp yapısını kullanır;
sadece sabit W_PHYSICS/W_BOUNDARY/W_INITIAL yerine öğrenilebilir
λ ağırlıkları koyar.

Mevcut kodun sırrı (problems/quenching.py):
  - Her terim fiziksel ölçeğiyle normalize edilir → hepsi O(1)
  - BC: normals batch'te ayrıca sağlanır (infer edilmez)
  - PDE_SCALE = RHO_CP * ΔT / T_END ≈ 4.16e7
  - BC_SCALE  = (h_ref/K) * ΔT       ≈ 17333
  - IC_SCALE  = ΔT                    = 520

SA-PINN katkısı:
  Sabit λ = (1.0, 10.0, 10.0) yerine eğitilebilir λ = softplus(w).
  Düşük LR ile descent → optimizer'a özel denge otomatik bulunur.
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Dict, Tuple

from src.config import DEVICE, K_THERMAL, RHO_CP, T_END, T_INIT, T_WATER_INIT
from src.physics_model import heat_equation_residual, WaterQuenchHTC


# ─────────────────────────────────────────────────────────────
# Fiziksel normalizasyon ölçekleri (problems/quenching.py ile aynı)
# ─────────────────────────────────────────────────────────────
_dT_ref   = T_INIT - T_WATER_INIT                    # 520 °C
_H_REF    = 5000.0                                    # W/m²K
PDE_SCALE = RHO_CP * _dT_ref / T_END                  # ~4.16e7
BC_SCALE  = (_H_REF / K_THERMAL) * _dT_ref            # ~17333
IC_SCALE  = _dT_ref                                   # 520


# ─────────────────────────────────────────────────────────────
# Self-Adaptive Ağırlık Modülü
# ─────────────────────────────────────────────────────────────

class SelfAdaptiveWeights(nn.Module):
    """
    Eğitilebilir kayıp ağırlıkları — softplus ile pozitif tutulur.
    Başlangıç değerleri problems/quenching.py (config.py) ile aynı:
        λ_phys  = W_PHYSICS  = 1.0
        λ_bc    = W_BOUNDARY = 10.0
        λ_ic    = W_INITIAL  = 10.0
    """

    def __init__(self,
                 init_phys: float = 1.0,
                 init_bc:   float = 10.0,
                 init_ic:   float = 10.0):
        super().__init__()

        def _inv_sp(y: float) -> float:
            return float(torch.log(torch.exp(torch.tensor(float(y))) - 1.0))

        self.w_phys = nn.Parameter(torch.tensor(_inv_sp(init_phys)))
        self.w_bc   = nn.Parameter(torch.tensor(_inv_sp(init_bc)))
        self.w_ic   = nn.Parameter(torch.tensor(_inv_sp(init_ic)))

    @property
    def lambda_phys(self): return F.softplus(self.w_phys)
    @property
    def lambda_bc(self):   return F.softplus(self.w_bc)
    @property
    def lambda_ic(self):   return F.softplus(self.w_ic)

    def forward(self, L_phys, L_bc, L_ic):
        return self.lambda_phys * L_phys + self.lambda_bc * L_bc + self.lambda_ic * L_ic

    def weights_dict(self) -> Dict[str, float]:
        return {
            "lambda_phys": self.lambda_phys.item(),
            "lambda_bc":   self.lambda_bc.item(),
            "lambda_ic":   self.lambda_ic.item(),
        }


# ─────────────────────────────────────────────────────────────
# 2D Quenching — SA Kayıp
# ─────────────────────────────────────────────────────────────

class SAQuenchingLoss:
    """
    Varolan QuenchingProblem kayıp yapısı + SA ağırlıkları.
    Batch formatı: {"domain", "boundary", "normals", "initial"}
    (problems/quenching.py make_batch_fn çıktısıyla uyumlu)
    """

    def __init__(self, sa_weights: SelfAdaptiveWeights,
                 T_init: float = T_INIT,
                 T_water: float = T_WATER_INIT):
        self.sa_w    = sa_weights
        self.T_init  = T_init
        self.T_water = T_water
        self.htc     = WaterQuenchHTC()

    def __call__(self, model: nn.Module, batch: Dict) -> Tuple[torch.Tensor, Dict]:

        # ── 1. PDE rezidüeli (normalize)
        coords_f = batch["domain"]
        pred_f   = model(coords_f)
        r_f      = heat_equation_residual(pred_f, coords_f)
        L_phys   = ((r_f / PDE_SCALE) ** 2).mean()

        # ── 2. Robin BC (normalize) — normal vektörler batch'te gelir
        coords_b = batch["boundary"]
        normals  = batch["normals"]
        pred_b   = model(coords_b)
        T_surf   = pred_b[:, 0]

        grads_b  = torch.autograd.grad(
            pred_b, coords_b,
            grad_outputs=torch.ones_like(pred_b),
            create_graph=True,
        )[0]
        dT_dn = grads_b[:, 1] * normals[:, 0] + grads_b[:, 2] * normals[:, 1]

        # h(T) is a coefficient — detach to avoid gradients flowing through
        # the nonlinear HTC function (T^2.33, T^4), which causes NaN with tanh nets
        T_w    = torch.full_like(T_surf, self.T_water)
        h_vals = self.htc.htc(T_surf.detach().clamp(20.0, 600.0), T_w)
        robin  = (dT_dn + (h_vals / K_THERMAL) * (T_surf - self.T_water)) / BC_SCALE
        L_bc   = (robin ** 2).mean()

        # ── 3. IC (normalize)
        coords_i = batch["initial"]
        pred_i   = model(coords_i)
        L_ic     = (((pred_i - self.T_init) / IC_SCALE) ** 2).mean()

        # ── 4. SA toplam
        L_total = self.sa_w(L_phys, L_bc, L_ic)

        details = {
            "L_total": L_total.item(),
            "L_phys":  L_phys.item(),
            "L_bc":    L_bc.item(),
            "L_ic":    L_ic.item(),
            **self.sa_w.weights_dict(),
        }
        return L_total, details


# ─────────────────────────────────────────────────────────────
# 3D Quenching — SA Kayıp
# ─────────────────────────────────────────────────────────────

class SAQuenchingLoss3D:
    """
    3D kutu için SA kayıp. Batch formatı aynı: {"domain", "boundary", "normals", "initial"}
    Normals 3 boyutlu: [nx, ny, nz]
    """

    def __init__(self, sa_weights: SelfAdaptiveWeights,
                 T_init: float = T_INIT, T_water: float = T_WATER_INIT):
        self.sa_w    = sa_weights
        self.T_init  = T_init
        self.T_water = T_water
        self.htc     = WaterQuenchHTC()

    def __call__(self, model: nn.Module, batch: Dict) -> Tuple[torch.Tensor, Dict]:

        # ── 1. PDE — 3D Laplacian
        pts_d = batch["domain"]
        T_d   = model(pts_d)

        g = torch.autograd.grad(T_d, pts_d, torch.ones_like(T_d), create_graph=True)[0]
        dT_dt = g[:,0:1]; dT_dx = g[:,1:2]; dT_dy = g[:,2:3]; dT_dz = g[:,3:4]

        d2x = torch.autograd.grad(dT_dx, pts_d, torch.ones_like(dT_dx), create_graph=True)[0][:,1:2]
        d2y = torch.autograd.grad(dT_dy, pts_d, torch.ones_like(dT_dy), create_graph=True)[0][:,2:3]
        d2z = torch.autograd.grad(dT_dz, pts_d, torch.ones_like(dT_dz), create_graph=True)[0][:,3:4]

        r_f    = RHO_CP * dT_dt - K_THERMAL * (d2x + d2y + d2z)
        L_phys = ((r_f / PDE_SCALE) ** 2).mean()

        # ── 2. Robin BC
        pts_b   = batch["boundary"]
        normals = batch["normals"]    # [N, 3]
        T_b     = model(pts_b)
        T_surf  = T_b[:, 0]

        gb = torch.autograd.grad(T_b, pts_b, torch.ones_like(T_b), create_graph=True)[0]
        dT_dn = (gb[:,1]*normals[:,0] + gb[:,2]*normals[:,1] + gb[:,3]*normals[:,2])

        T_w    = torch.full_like(T_surf, self.T_water)
        h_vals = self.htc.htc(T_surf, T_w)
        robin  = (dT_dn + (h_vals / K_THERMAL) * (T_surf - self.T_water)) / BC_SCALE
        L_bc   = (robin ** 2).mean()

        # ── 3. IC
        pts_i = batch["initial"]
        T_i   = model(pts_i)
        L_ic  = (((T_i - self.T_init) / IC_SCALE) ** 2).mean()

        L_total = self.sa_w(L_phys, L_bc, L_ic)
        details = {
            "L_total": L_total.item(),
            "L_phys":  L_phys.item(),
            "L_bc":    L_bc.item(),
            "L_ic":    L_ic.item(),
            **self.sa_w.weights_dict(),
        }
        return L_total, details
