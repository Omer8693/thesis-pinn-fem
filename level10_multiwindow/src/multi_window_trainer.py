"""
multi_window_trainer.py — Multi-Step Window PINN Training
==========================================================
Trains a single PINN over a wide time window covering k FEM steps:
    [t_anchor, t_anchor + k * dt_single]

Current approach (Level 3 hybrid_runner):
    FEM(t0) -> PINN(t0->t1) -> PINN(t1->t2) -> PINN(t2->t3) -> FEM(t3)
    Problem: each PINN inherits the error of the previous one.

New approach (MSWP):
    FEM(t0) --> PINN_WIDE([t0, t3], single training pass) --> FEM(t3)
             IC=FEM(t0), BC enforced over full window, PDE on [0, k*dt]
    Benefit: resets from FEM anchor, no error accumulation.

Inference: model(x, y, t_local=k*dt, T_anchor, k*dt) -> T(t_end)
"""

import sys
import time
from pathlib import Path
from typing import Callable, Optional

import torch

# Reuse Level 2 model
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "level2_timestepper"))
from src.ts_model import TimeStepperPINN

# Physical constants (baseline_paper [2026])
K_THERMAL = 150.0    # [W/mK]  thermal conductivity
RHO_CP    = 2.4e6    # [J/m3K] volumetric heat capacity
H_CONV    = 5000.0   # [W/m2K] convective heat transfer coefficient
T_WATER   = 20.0     # [deg C] quench water temperature
X_MAX     = 1.3      # [m]     domain width
Y_MAX     = 0.6      # [m]     domain height
PDE_SCALE = RHO_CP * 520.0 / 30.0   # ~4.16e7 W/m3, for loss normalisation

# Loss weights
W_PDE      = 1.0
W_IC       = 15.0   # FEM anchor deviation — increased vs Level 3
W_BOUNDARY = 5.0
W_END      = 10.0   # optional t_end FEM supervision


# ---------------------------------------------------------------------------
# PDE residual loss
# ---------------------------------------------------------------------------

def _pde_loss(model: TimeStepperPINN,
              x: torch.Tensor, y: torch.Tensor,
              t_local: torch.Tensor,
              T_anchor: torch.Tensor,
              dt_total: float) -> torch.Tensor:
    """Heat equation: rho*Cp * dT/dt - K * (d2T/dx2 + d2T/dy2) = 0,
    sampled over t_local in [0, dt_total]."""
    x = x.requires_grad_(True)
    y = y.requires_grad_(True)
    t = t_local.requires_grad_(True)

    T_pred = model(x, y, t, T_anchor.detach(), dt_total)

    gx, gy, gt_raw = torch.autograd.grad(
        T_pred.sum(), [x, y, t], create_graph=True
    )
    T_t = gt_raw / dt_total   # chain rule for normalised time

    T_xx = torch.autograd.grad(gx.sum(), x, create_graph=True)[0]
    T_yy = torch.autograd.grad(gy.sum(), y, create_graph=True)[0]

    residual = RHO_CP * T_t - K_THERMAL * (T_xx + T_yy)
    return torch.mean((residual / PDE_SCALE) ** 2)


# ---------------------------------------------------------------------------
# Initial condition loss
# ---------------------------------------------------------------------------

def _ic_loss(model: TimeStepperPINN,
             x: torch.Tensor, y: torch.Tensor,
             T_anchor: torch.Tensor,
             dt_total: float) -> torch.Tensor:
    """IC loss: at t_local=0, T must equal T_anchor (FEM).
    This is the key constraint that prevents error accumulation."""
    t_zero = torch.zeros_like(x)
    T_pred = model(x, y, t_zero, T_anchor, dt_total)
    return torch.mean(((T_pred - T_anchor) / 520.0) ** 2)


# ---------------------------------------------------------------------------
# Boundary condition loss
# ---------------------------------------------------------------------------

def _bc_loss(model: TimeStepperPINN,
             T_anchor_mean: float,
             dt_total: float,
             n_bc: int,
             device: torch.device) -> torch.Tensor:
    """Robin BC: K * dT/dn + h * (T - T_water) = 0,
    enforced on all four edges over t_local in [0, dt_total]."""
    bc_scale = (H_CONV / K_THERMAL) * 520.0
    T_anc_bc = torch.full((n_bc, 1), T_anchor_mean, device=device)
    losses = []

    sides = {
        "left":   (lambda: (torch.zeros(n_bc, 1, device=device),
                            torch.rand(n_bc, 1, device=device) * Y_MAX), "x", -1.0),
        "right":  (lambda: (torch.full((n_bc, 1), X_MAX, device=device),
                            torch.rand(n_bc, 1, device=device) * Y_MAX), "x",  1.0),
        "bottom": (lambda: (torch.rand(n_bc, 1, device=device) * X_MAX,
                            torch.zeros(n_bc, 1, device=device)),         "y", -1.0),
        "top":    (lambda: (torch.rand(n_bc, 1, device=device) * X_MAX,
                            torch.full((n_bc, 1), Y_MAX, device=device)), "y",  1.0),
    }

    for side, (pts_fn, normal_ax, sign) in sides.items():
        x_raw, y_raw = pts_fn()
        t_bc = torch.rand(n_bc, 1, device=device) * dt_total
        if normal_ax == "x":
            x_bc = x_raw.requires_grad_(True)
            y_bc = y_raw
            T_bc = model(x_bc, y_bc, t_bc, T_anc_bc, dt_total)
            dT_dn = torch.autograd.grad(T_bc.sum(), x_bc, create_graph=True)[0]
        else:
            x_bc = x_raw
            y_bc = y_raw.requires_grad_(True)
            T_bc = model(x_bc, y_bc, t_bc, T_anc_bc, dt_total)
            dT_dn = torch.autograd.grad(T_bc.sum(), y_bc, create_graph=True)[0]

        robin = (sign * dT_dn + (H_CONV / K_THERMAL) * (T_bc - T_WATER)) / bc_scale
        losses.append(torch.mean(robin ** 2))

    return sum(losses) / len(losses)


# ---------------------------------------------------------------------------
# Optional t_end FEM supervision loss
# ---------------------------------------------------------------------------

def _end_loss(model: TimeStepperPINN,
              x: torch.Tensor, y: torch.Tensor,
              T_anchor: torch.Tensor,
              T_end_fem: torch.Tensor,
              dt_total: float) -> torch.Tensor:
    """Optional end-point supervision: if the FEM solution at t_end is
    available, add a data loss at t_local=dt_total to anchor the window exit."""
    t_end_local = torch.full_like(x, dt_total)
    T_pred = model(x, y, t_end_local, T_anchor.detach(), dt_total)
    return torch.mean(((T_pred - T_end_fem.detach()) / 520.0) ** 2)


# ---------------------------------------------------------------------------
# Main training function
# ---------------------------------------------------------------------------

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
                       T_end_fem_fn: Optional[Callable] = None,
                       device: torch.device = torch.device("cpu")) -> tuple:
    """
    Train a single PINN over the wide window [t_start, t_end].

    Parameters
    ----------
    T_anchor_fn  : callable (x, y) -> (N,1) tensor — FEM temperature at t_start (IC)
    T_end_fem_fn : callable (x, y) -> (N,1) tensor — optional FEM temperature at t_end
                   If provided, adds an extra data supervision term at the window exit.
                   Improves convergence but requires one extra FEM call.

    Inference
    ---------
    After training, query the PINN at t_local = dt_total:
        T_next = model(x, y, full(dt_total), T_anchor, dt_total)

    Returns
    -------
    (trained_model, info_dict)
    """
    dt_total  = t_end - t_start
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    sched     = torch.optim.lr_scheduler.CosineAnnealingLR(
        optimizer, T_max=n_epochs, eta_min=lr_min
    )
    history = {"pde": [], "ic": [], "bc": [], "end_sup": [], "total": []}
    t0 = time.time()

    for epoch in range(n_epochs):
        optimizer.zero_grad()

        x = torch.rand(n_domain, 1, device=device) * X_MAX
        y = torch.rand(n_domain, 1, device=device) * Y_MAX
        t = torch.rand(n_domain, 1, device=device) * dt_total   # sample full window

        T_anc      = T_anchor_fn(x, y).detach()
        T_anc_mean = float(T_anc.mean().item())

        l_pde = _pde_loss(model, x, y, t, T_anc, dt_total)
        l_ic  = _ic_loss(model, x, y, T_anc, dt_total)
        l_bc  = _bc_loss(model, T_anc_mean, dt_total, n_bc, device)
        loss  = W_PDE * l_pde + W_IC * l_ic + W_BOUNDARY * l_bc

        l_end = torch.tensor(0.0)
        if T_end_fem_fn is not None:
            T_end = T_end_fem_fn(x, y).detach()
            l_end = _end_loss(model, x, y, T_anc, T_end, dt_total)
            loss  = loss + W_END * l_end

        loss.backward()
        optimizer.step()
        sched.step()

        if epoch % 100 == 0:
            history["pde"].append(l_pde.item())
            history["ic"].append(l_ic.item())
            history["bc"].append(l_bc.item())
            history["end_sup"].append(l_end.item() if T_end_fem_fn else 0.0)
            history["total"].append(loss.item())

    # L-BFGS refinement phase
    if lbfgs_iters > 0:
        x_f = torch.rand(n_domain, 1, device=device) * X_MAX
        y_f = torch.rand(n_domain, 1, device=device) * Y_MAX
        t_f = torch.rand(n_domain, 1, device=device) * dt_total
        T_anc_f      = T_anchor_fn(x_f, y_f).detach()
        T_anc_mean_f = float(T_anc_f.mean().item())
        T_end_f      = T_end_fem_fn(x_f, y_f).detach() if T_end_fem_fn else None

        lbfgs_opt = torch.optim.LBFGS(
            model.parameters(), max_iter=lbfgs_iters,
            tolerance_grad=1e-7, tolerance_change=1e-9,
            line_search_fn="strong_wolfe",
        )

        def closure():
            lbfgs_opt.zero_grad()
            l = (W_PDE      * _pde_loss(model, x_f, y_f, t_f, T_anc_f, dt_total)
               + W_IC        * _ic_loss(model, x_f, y_f, T_anc_f, dt_total)
               + W_BOUNDARY  * _bc_loss(model, T_anc_mean_f, dt_total, n_bc, device))
            if T_end_f is not None:
                l = l + W_END * _end_loss(model, x_f, y_f, T_anc_f, T_end_f, dt_total)
            l.backward()
            return l

        lbfgs_opt.step(closure)

    elapsed = time.time() - t0
    return model, {
        "history":    history,
        "train_time": elapsed,
        "dt_total":   dt_total,
    }
