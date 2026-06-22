"""
multi_window_trainer.py — Multi-Step Window PINN Eğitimi
=========================================================
Tek bir PINN'i birden fazla FEM adımını kapsayan geniş bir pencerede
[t_anchor, t_anchor + k·dt] eğitir.

Mevcut yaklaşım (hybrid_runner.py):
    FEM(t0) → PINN(t0→t1) → PINN(t1→t2) → PINN(t2→t3) → FEM(t3)
    Problem: her PINN bir öncekinin hatasını miras alır.

Bu yaklaşım:
    FEM(t0) → PINN_WIDE(t0 → t3, tek eğitim) → FEM(t3)
    IC t=t0'dan FEM anchor olarak alınır, hata birikimi yoktur.

Çıkışta T(x,y, t_local=k·dt) sorgulanarak t_end tahmin alınır.
"""

import time
from typing import Callable

import torch
import torch.nn as nn

# Level 2 model ve fiziksel sabitler
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "level2_timestepper"))
from src.ts_model import TimeStepperPINN

# ── Fiziksel sabitler ────────────────────────────────────────────────────────
K_THERMAL = 150.0    # [W/mK]
RHO_CP    = 2.4e6    # [J/m³K]
H_CONV    = 5000.0   # [W/m²K]
T_WATER   = 20.0     # [°C]
X_MAX     = 1.3      # [m]
Y_MAX     = 0.6      # [m]

# Kayıp ağırlıkları — IC anchor kritik, BC ve PDE pencere boyunca
W_PDE      = 1.0
W_IC       = 15.0    # FEM anchor'dan sapma cezası artırıldı
W_BOUNDARY = 5.0
W_END      = 10.0    # (opsiyonel) t_end FEM değeri biliniyorsa ek kısıt

PDE_SCALE = RHO_CP * 520.0 / 30.0   # ≈ 4.16e7 W/m³


# ── Kayıp fonksiyonları ──────────────────────────────────────────────────────

def _pde_loss_wide(model: TimeStepperPINN,
                   x: torch.Tensor, y: torch.Tensor,
                   t_local: torch.Tensor,
                   T_anchor: torch.Tensor,
                   dt_total: float) -> torch.Tensor:
    """
    Geniş pencere [0, dt_total] boyunca ısı denklemi PDE kaybı.
    t_local ∈ [0, dt_total] düzgün örneklenir.
    T_anchor: t=0 anındaki FEM sıcaklığı (sabit, detach).
    """
    x = x.requires_grad_(True)
    y = y.requires_grad_(True)
    t = t_local.requires_grad_(True)

    T_pred = model(x, y, t, T_anchor.detach(), dt_total)

    grads = torch.autograd.grad(T_pred.sum(), [x, y, t], create_graph=True)
    T_x, T_y, T_t_raw = grads
    T_t = T_t_raw / dt_total   # zincir kuralı

    T_xx = torch.autograd.grad(T_x.sum(), x, create_graph=True)[0]
    T_yy = torch.autograd.grad(T_y.sum(), y, create_graph=True)[0]

    residual = RHO_CP * T_t - K_THERMAL * (T_xx + T_yy)
    return torch.mean((residual / PDE_SCALE) ** 2)


def _ic_loss_wide(model: TimeStepperPINN,
                  x: torch.Tensor, y: torch.Tensor,
                  T_anchor: torch.Tensor,
                  dt_total: float) -> torch.Tensor:
    """
    IC kaybı: t_local=0 → T = T_anchor (FEM).
    FEM anchor'dan sapma en önemli kısıt.
    """
    t_zero = torch.zeros_like(x)
    T_pred = model(x, y, t_zero, T_anchor, dt_total)
    return torch.mean(((T_pred - T_anchor) / 520.0) ** 2)


def _boundary_loss_wide(model: TimeStepperPINN,
                        T_anchor_mean: float,
                        dt_total: float,
                        n_bc: int,
                        device: torch.device) -> torch.Tensor:
    """
    Robin BC: K·∂T/∂n + h·(T - T_water) = 0
    t_local ∈ [0, dt_total] boyunca dört kenarda uygulanır.
    """
    bc_scale = (H_CONV / K_THERMAL) * 520.0
    T_anchor_bc = torch.full((n_bc, 1), T_anchor_mean, device=device)
    losses = []

    for side in ["left", "right", "bottom", "top"]:
        # Pencere boyunca rastgele zaman örnekle
        t_bc = torch.rand(n_bc, 1, device=device) * dt_total

        if side == "left":
            x_bc = torch.zeros(n_bc, 1, device=device).requires_grad_(True)
            y_bc = torch.rand(n_bc, 1, device=device) * Y_MAX
            T_bc = model(x_bc, y_bc, t_bc, T_anchor_bc, dt_total)
            dT_dn = torch.autograd.grad(T_bc.sum(), x_bc, create_graph=True)[0]
            sign = -1.0
        elif side == "right":
            x_bc = torch.full((n_bc, 1), X_MAX, device=device).requires_grad_(True)
            y_bc = torch.rand(n_bc, 1, device=device) * Y_MAX
            T_bc = model(x_bc, y_bc, t_bc, T_anchor_bc, dt_total)
            dT_dn = torch.autograd.grad(T_bc.sum(), x_bc, create_graph=True)[0]
            sign = 1.0
        elif side == "bottom":
            x_bc = torch.rand(n_bc, 1, device=device) * X_MAX
            y_bc = torch.zeros(n_bc, 1, device=device).requires_grad_(True)
            T_bc = model(x_bc, y_bc, t_bc, T_anchor_bc, dt_total)
            dT_dn = torch.autograd.grad(T_bc.sum(), y_bc, create_graph=True)[0]
            sign = -1.0
        else:  # top
            x_bc = torch.rand(n_bc, 1, device=device) * X_MAX
            y_bc = torch.full((n_bc, 1), Y_MAX, device=device).requires_grad_(True)
            T_bc = model(x_bc, y_bc, t_bc, T_anchor_bc, dt_total)
            dT_dn = torch.autograd.grad(T_bc.sum(), y_bc, create_graph=True)[0]
            sign = 1.0

        robin = (sign * dT_dn + (H_CONV / K_THERMAL) * (T_bc - T_WATER)) / bc_scale
        losses.append(torch.mean(robin ** 2))

    return sum(losses) / len(losses)


def _end_supervision_loss(model: TimeStepperPINN,
                          x: torch.Tensor, y: torch.Tensor,
                          T_anchor: torch.Tensor,
                          T_end_fem: torch.Tensor,
                          dt_total: float) -> torch.Tensor:
    """
    Opsiyonel: t_end FEM çözümü biliniyorsa ek denetim kaybı.
    Pencere sonunda FEM'e yakınsamayı zorlar.
    T_end_fem: t_anchor + k*dt anındaki FEM sıcaklığı (float tensor, N,1).
    """
    t_end = torch.full_like(x, dt_total)
    T_pred = model(x, y, t_end, T_anchor.detach(), dt_total)
    return torch.mean(((T_pred - T_end_fem.detach()) / 520.0) ** 2)


# ── Ana eğitim fonksiyonu ────────────────────────────────────────────────────

def train_multi_window(model: TimeStepperPINN,
                       T_anchor_fn: Callable,
                       t_start: float,
                       t_end: float,
                       n_domain: int = 1500,
                       n_bc: int = 300,
                       n_epochs: int = 800,
                       lr: float = 1e-3,
                       lr_min: float = 1e-5,
                       lbfgs_iters: int = 50,
                       T_end_fem_fn: Callable = None,
                       device: torch.device = torch.device("cpu")) -> tuple:
    """
    Tek PINN'i [t_start, t_end] penceresinde eğit.
    t_end - t_start = k * dt_single (k FEM adımını kapsar).

    T_anchor_fn(x, y) → tensor(N,1): t_start FEM sıcaklığı (IC)
    T_end_fem_fn(x, y) → tensor(N,1): t_end FEM sıcaklığı (opsiyonel, ek denetim)

    Döndürür: (model, history_dict)

    Çıkarım: T_next = model(x, y, t_local=dt_total, T_anchor, dt_total)
             yani PINN'i t_end'de sorgula.
    """
    dt_total = t_end - t_start
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
        optimizer, T_max=n_epochs, eta_min=lr_min
    )
    history = {"pde": [], "ic": [], "bc": [], "end": [], "total": []}
    t0 = time.time()

    for epoch in range(n_epochs):
        optimizer.zero_grad()

        # Pencere boyunca (0, dt_total) aralığında örnekle
        x = torch.rand(n_domain, 1, device=device) * X_MAX
        y = torch.rand(n_domain, 1, device=device) * Y_MAX
        t = torch.rand(n_domain, 1, device=device) * dt_total   # t_local ∈ [0, dt_total]

        T_anchor = T_anchor_fn(x, y).detach()
        T_anchor_mean = float(T_anchor.mean().item())

        loss_pde = _pde_loss_wide(model, x, y, t, T_anchor, dt_total)
        loss_ic  = _ic_loss_wide(model, x, y, T_anchor, dt_total)
        loss_bc  = _boundary_loss_wide(model, T_anchor_mean, dt_total, n_bc, device)

        loss = W_PDE * loss_pde + W_IC * loss_ic + W_BOUNDARY * loss_bc

        # Opsiyonel: t_end FEM denetimi
        loss_end = torch.tensor(0.0)
        if T_end_fem_fn is not None:
            T_end = T_end_fem_fn(x, y).detach()
            loss_end = _end_supervision_loss(model, x, y, T_anchor, T_end, dt_total)
            loss = loss + W_END * loss_end

        loss.backward()
        optimizer.step()
        scheduler.step()

        if epoch % 100 == 0:
            history["pde"].append(loss_pde.item())
            history["ic"].append(loss_ic.item())
            history["bc"].append(loss_bc.item())
            history["end"].append(loss_end.item() if T_end_fem_fn else 0.0)
            history["total"].append(loss.item())

    # ── L-BFGS ince ayar ────────────────────────────────────────────────────
    if lbfgs_iters > 0:
        x_f = torch.rand(n_domain, 1, device=device) * X_MAX
        y_f = torch.rand(n_domain, 1, device=device) * Y_MAX
        t_f = torch.rand(n_domain, 1, device=device) * dt_total
        T_anc_f = T_anchor_fn(x_f, y_f).detach()
        T_anc_mean_f = float(T_anc_f.mean().item())

        T_end_f = T_end_fem_fn(x_f, y_f).detach() if T_end_fem_fn else None

        lbfgs_opt = torch.optim.LBFGS(
            model.parameters(),
            max_iter=lbfgs_iters,
            tolerance_grad=1e-7,
            tolerance_change=1e-9,
            line_search_fn="strong_wolfe",
        )

        def closure():
            lbfgs_opt.zero_grad()
            l_pde = _pde_loss_wide(model, x_f, y_f, t_f, T_anc_f, dt_total)
            l_ic  = _ic_loss_wide(model, x_f, y_f, T_anc_f, dt_total)
            l_bc  = _boundary_loss_wide(model, T_anc_mean_f, dt_total, n_bc, device)
            l = W_PDE * l_pde + W_IC * l_ic + W_BOUNDARY * l_bc
            if T_end_f is not None:
                l_end = _end_supervision_loss(model, x_f, y_f, T_anc_f, T_end_f, dt_total)
                l = l + W_END * l_end
            l.backward()
            return l

        lbfgs_opt.step(closure)

    elapsed = time.time() - t0
    return model, {"history": history, "train_time": elapsed,
                   "dt_total": dt_total, "k_steps": round(dt_total / (dt_total / max(1, len(history["pde"]))))}


def query_pinn_at_end(model: TimeStepperPINN,
                      T_anchor_fn: Callable,
                      n_query: int,
                      dt_total: float,
                      device: torch.device) -> "FEMCheckpoint":
    """
    Eğitilmiş PINN'den t_end tahminini al.
    t_local = dt_total → T(x, y, t_end)

    Döndürür: FEMCheckpoint (sonraki anchor veya karşılaştırma için)
    """
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from level3_hybrid_fem.src.fem_interface import FEMCheckpoint

    x = torch.rand(n_query, 1, device=device) * X_MAX
    y = torch.rand(n_query, 1, device=device) * Y_MAX
    t_end_local = torch.full((n_query, 1), dt_total, device=device)
    T_anchor = T_anchor_fn(x, y).detach()

    with torch.no_grad():
        T_pred = model(x, y, t_end_local, T_anchor, dt_total)

    return FEMCheckpoint(
        t=0.0,  # caller t_end'i atar
        T_field=T_pred.squeeze(),
        x_grid=x.squeeze(),
        y_grid=y.squeeze(),
    )
