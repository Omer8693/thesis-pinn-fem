"""
hybrid_multiwindow.py — Multi-Step Window Hybrid Runner
========================================================
Uses a single wide-window PINN between consecutive FEM anchor points.

Example flow (k_skip=3, dt=1s):
    t=0   FEM anchor
    t=1,2 skipped -> PINN_WIDE([0,3]) trains once, queried at t=3
    t=3   FEM anchor (reset)
    t=4,5 skipped -> PINN_WIDE([3,6]) ...

compare_mswp_vs_sequential(): compares MSWP vs sequential PINN on one segment.
run_multiwindow():             runs MSWP over an entire time series.
"""

import sys
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional

import numpy as np
import torch

# Load Level 2 ts_model + ts_trainer (they import each other via src.*)
_L2 = str(Path(__file__).parent.parent.parent / "level2_timestepper")
if _L2 not in sys.path:
    sys.path.insert(0, _L2)
from src.ts_model   import TimeStepperPINN
from src.ts_trainer import train_window   # single-step PINN (for comparison)

# Load Level 3 FEMCheckpoint via importlib to avoid 'src' namespace collision
import importlib.util as _ilu
_fem_spec = _ilu.spec_from_file_location(
    "fem_interface",
    Path(__file__).parent.parent.parent / "level3_hybrid_fem" / "src" / "fem_interface.py",
)
_fem_mod = _ilu.module_from_spec(_fem_spec)
_fem_spec.loader.exec_module(_fem_mod)
FEMCheckpoint = _fem_mod.FEMCheckpoint

from .multi_window_trainer import train_multi_window

X_MAX = 1.3   # [m]
Y_MAX = 0.6   # [m]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _anchor_fn(ckpt: FEMCheckpoint) -> Callable:
    """Wrap a FEMCheckpoint as a callable T_fn(x, y) -> tensor(N,1)."""
    def fn(x: torch.Tensor, y: torch.Tensor) -> torch.Tensor:
        return ckpt.interpolate_at(x.squeeze(), y.squeeze()).unsqueeze(1)
    return fn


def _query_at_end(model: TimeStepperPINN,
                  anchor_fn: Callable,
                  dt_total: float,
                  n_query: int,
                  device: torch.device) -> FEMCheckpoint:
    """Query the trained PINN at t_local = dt_total to get T(t_end)."""
    x = torch.rand(n_query, 1, device=device) * X_MAX
    y = torch.rand(n_query, 1, device=device) * Y_MAX
    t_end_local = torch.full((n_query, 1), dt_total, device=device)
    T_anc = anchor_fn(x, y).detach()
    with torch.no_grad():
        T_pred = model(x, y, t_end_local, T_anc, dt_total)
    return FEMCheckpoint(0.0, T_pred.squeeze(), x.squeeze(), y.squeeze())


# ---------------------------------------------------------------------------
# Single-segment comparison
# ---------------------------------------------------------------------------

def compare_mswp_vs_sequential(
        model_cfg:            dict,
        fem_solver:           Callable,
        t_start:              float,
        t_end:                float,
        k_skip:               int,
        dt_single:            float,
        train_kwargs_single:  dict,
        train_kwargs_wide:    dict,
        use_end_supervision:  bool = False,
        n_query:              int  = 500,
        device:               torch.device = torch.device("cpu"),
        logger=None) -> dict:
    """
    Compare two strategies over one k-step segment.

    A) Sequential PINN (current Level 3 approach):
       FEM(t0) -> P1(t0->t1) -> P2(t1->t2) -> P3(t2->t3)
       Each PINN takes the previous PINN output as IC.

    B) MSWP (new):
       FEM(t0) -> PINN_WIDE([t0, t3]) -> query at t3

    Both use only the t_start FEM anchor.
    Comparison metric: MAE at t_end vs FEM reference.

    Returns
    -------
    dict with keys: mae_sequential, mae_mswp, improvement_pct, winner, timings
    """
    def log(m):
        (logger.info if logger else print)(m)

    anchor_ckpt  = fem_solver(t_start)
    fem_end_ckpt = fem_solver(t_end)

    x_q = torch.rand(n_query, 1, device=device) * X_MAX
    y_q = torch.rand(n_query, 1, device=device) * Y_MAX
    T_fem_end = fem_end_ckpt.interpolate_at(x_q.squeeze(), y_q.squeeze())

    # ---- A: Sequential PINN -------------------------------------------------
    log("\n-- A: Sequential PINN --")
    t_seq = np.arange(t_start, t_end + dt_single * 0.5, dt_single)
    cur = anchor_ckpt
    t_seq_wall = []

    for i in range(1, len(t_seq)):
        ta, tb = float(t_seq[i - 1]), float(t_seq[i])
        dt     = tb - ta
        T_prev_fn = _anchor_fn(cur)
        m = TimeStepperPINN(model_cfg).to(device)
        m, info = train_window(model=m, T_prev_fn=T_prev_fn,
                               t_start=ta, t_end=tb, device=device,
                               **train_kwargs_single)
        t_seq_wall.append(info["train_time"])

        x_s = torch.rand(n_query, 1, device=device) * X_MAX
        y_s = torch.rand(n_query, 1, device=device) * Y_MAX
        t_loc = torch.full((n_query, 1), dt, device=device)
        T_a   = T_prev_fn(x_s, y_s).detach()
        with torch.no_grad():
            T_next = m(x_s, y_s, t_loc, T_a, dt)
        cur = FEMCheckpoint(tb, T_next.squeeze(), x_s.squeeze(), y_s.squeeze())
        log(f"  t={tb:.1f}s | T_mean={T_next.mean():.1f} deg C")

    T_seq   = cur.interpolate_at(x_q.squeeze(), y_q.squeeze())
    mae_seq = float((T_seq - T_fem_end).abs().mean())
    log(f"  Sequential MAE @ t={t_end:.1f}s: {mae_seq:.4f} deg C")

    # ---- B: MSWP ------------------------------------------------------------
    log("\n-- B: MSWP --")
    T_anc_fn = _anchor_fn(anchor_ckpt)
    T_end_fn = _anchor_fn(fem_end_ckpt) if use_end_supervision else None

    m_wide = TimeStepperPINN(model_cfg).to(device)
    m_wide, wi = train_multi_window(
        model=m_wide, T_anchor_fn=T_anc_fn,
        t_start=t_start, t_end=t_end,
        T_end_fem_fn=T_end_fn,
        device=device, **train_kwargs_wide,
    )
    log(f"  Training time: {wi['train_time']:.1f}s")

    pred     = _query_at_end(m_wide, T_anc_fn, t_end - t_start, n_query, device)
    T_wide   = pred.interpolate_at(x_q.squeeze(), y_q.squeeze())
    mae_wide = float((T_wide - T_fem_end).abs().mean())
    log(f"  MSWP MAE @ t={t_end:.1f}s: {mae_wide:.4f} deg C")

    improvement = 100.0 * (mae_seq - mae_wide) / max(mae_seq, 1e-9)
    log(f"\n  Sequential={mae_seq:.4f} | MSWP={mae_wide:.4f} | "
        f"Improvement: {improvement:+.1f}%")

    return {
        "t_start":            t_start,
        "t_end":              t_end,
        "k_skip":             k_skip,
        "use_end_supervision": use_end_supervision,
        "mae_sequential":     mae_seq,
        "mae_mswp":           mae_wide,
        "improvement_pct":    improvement,
        "time_sequential_s":  sum(t_seq_wall),
        "time_mswp_s":        wi["train_time"],
        "winner":             "mswp" if mae_wide < mae_seq else "sequential",
    }


# ---------------------------------------------------------------------------
# Full time-series MSWP runner
# ---------------------------------------------------------------------------

def run_multiwindow(
        model_cfg:           dict,
        fem_solver:          Callable,
        t_steps:             np.ndarray,
        k_skip:              int = 3,
        use_end_supervision: bool = False,
        train_kwargs:        dict = None,
        n_query:             int  = 300,
        device:              torch.device = torch.device("cpu"),
        logger=None) -> tuple:
    """
    Run the full MSWP hybrid loop over a time series.

    Every k steps one FEM anchor is used; the interval between anchors
    is covered by a single wide-window PINN.

    Parameters
    ----------
    model_cfg           : TimeStepperPINN config dict (neurons, activation)
    fem_solver          : callable t -> FEMCheckpoint
    t_steps             : array of time points (assumed uniform spacing)
    k_skip              : number of FEM steps one PINN covers
    use_end_supervision : add FEM(t_end) supervision loss (costs one extra FEM call)
    train_kwargs        : forwarded to train_multi_window

    Returns
    -------
    (final_checkpoint, history_list, summary_dict)
    """
    if train_kwargs is None:
        train_kwargs = {}

    def log(m):
        (logger.info if logger else print)(m)

    anchor_idxs = list(range(0, len(t_steps), k_skip))
    if anchor_idxs[-1] != len(t_steps) - 1:
        anchor_idxs.append(len(t_steps) - 1)

    fem_cache: Dict[float, FEMCheckpoint] = {}

    def get_fem(t: float) -> FEMCheckpoint:
        key = round(float(t), 6)
        if key not in fem_cache:
            fem_cache[key] = fem_solver(t)
        return fem_cache[key]

    current = get_fem(t_steps[0])
    history: List[dict] = [{
        "t_start":      float(t_steps[0]),
        "t_end":        float(t_steps[0]),
        "source":       "fem_ic",
        "mae":          0.0,
        "T_mean_pred":  float(current.T_field.mean()),
    }]
    t0_wall = time.time()

    for si in range(len(anchor_idxs) - 1):
        i_s  = anchor_idxs[si]
        i_e  = anchor_idxs[si + 1]
        t_s  = float(t_steps[i_s])
        t_e  = float(t_steps[i_e])
        k    = i_e - i_s
        dt_w = t_e - t_s

        log(f"\n=== Segment [{t_s:.1f} -> {t_e:.1f}s]  k={k}  dt_total={dt_w:.1f}s ===")

        T_anc_fn = _anchor_fn(current)
        T_end_fn = _anchor_fn(get_fem(t_e)) if use_end_supervision else None

        model = TimeStepperPINN(model_cfg).to(device)
        model, wi = train_multi_window(
            model=model, T_anchor_fn=T_anc_fn,
            t_start=t_s, t_end=t_e,
            T_end_fem_fn=T_end_fn,
            device=device, **train_kwargs,
        )

        pred   = _query_at_end(model, T_anc_fn, dt_w, n_query, device)
        pred.t = t_e

        fem_ref = get_fem(t_e)
        x_q = torch.rand(n_query, 1, device=device) * X_MAX
        y_q = torch.rand(n_query, 1, device=device) * Y_MAX
        T_p = pred.interpolate_at(x_q.squeeze(), y_q.squeeze())
        T_f = fem_ref.interpolate_at(x_q.squeeze(), y_q.squeeze())
        mae = float((T_p - T_f).abs().mean())

        log(f"  MAE={mae:.3f} deg C | "
            f"T_pred={T_p.mean():.1f} | T_fem={T_f.mean():.1f} | "
            f"train={wi['train_time']:.1f}s")

        history.append({
            "t_start":      t_s,
            "t_end":        t_e,
            "source":       "pinn_wide",
            "k":            k,
            "mae":          mae,
            "T_mean_pred":  float(T_p.mean()),
            "T_mean_fem":   float(T_f.mean()),
            "train_time_s": wi["train_time"],
        })

        # Next segment anchor = FEM (reliable reset)
        current = fem_ref

    elapsed = time.time() - t0_wall
    maes = [h["mae"] for h in history if h["mae"] > 0]
    log(f"\nDone: {elapsed:.1f}s | "
        f"Mean MAE={np.mean(maes):.3f} deg C | Segments={len(anchor_idxs)-1}")

    return current, history, {
        "total_wall_time_s": elapsed,
        "mean_mae":          float(np.mean(maes)) if maes else 0.0,
        "n_segments":        len(anchor_idxs) - 1,
        "k_skip":            k_skip,
        "use_end_supervision": use_end_supervision,
    }
