"""
main_level10.py — Multi-Step Window PINN (MSWP) Experiment
===========================================================
Research question:
    Is it better to cover k FEM steps with k separate single-step PINNs,
    or with one single wide-window PINN?

Hypothesis:
    MSWP (single wide window) should accumulate less error because it
    resets from a clean FEM anchor at every k-step boundary.

Experiment plan:
    1. Run compare_mswp_vs_sequential for k_skip in {2, 3, 4, 5}
    2. Report t_end MAE: sequential vs MSWP
    3. Optionally run with use_end_supervision=True (one extra FEM call)
    4. Save results as JSON + generate plots

Usage:
    python level10_multiwindow/main_level10.py                    # k=3 comparison
    python level10_multiwindow/main_level10.py --k 4 --end_sup   # with end supervision
    python level10_multiwindow/main_level10.py --sweep            # k={2,3,4,5} sweep
    python level10_multiwindow/main_level10.py --full_series      # 30s full run
    python level10_multiwindow/main_level10.py --full_series --k 3 --cuda
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import importlib.util as _ilu

def _import_mod(root: str, module: str):
    spec = _ilu.spec_from_file_location(
        f"_m_{module}",
        ROOT / root / "src" / f"{module}.py",
    )
    m = _ilu.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m

FEMCheckpoint = _import_mod("level3_hybrid_fem", "fem_interface").FEMCheckpoint

from level10_multiwindow.src.hybrid_multiwindow import (
    compare_mswp_vs_sequential,
    run_multiwindow,
)

RESULTS_DIR = Path(__file__).parent / "results"
RESULTS_DIR.mkdir(exist_ok=True)

# Default model configuration
DEFAULT_MODEL_CFG = {
    "neurons":    [64, 64, 64, 64],
    "activation": "tanh",
}

# Single-step PINN training settings (matches Level 3)
TRAIN_SINGLE = {
    "n_domain":    1000,
    "n_bc":        200,
    "n_epochs":    500,
    "lr":          1e-3,
    "lr_min":      1e-5,
    "lbfgs_iters": 30,
}

# Wide-window PINN training settings (more epochs for larger temporal domain)
TRAIN_WIDE = {
    "n_domain":    1500,
    "n_bc":        300,
    "n_epochs":    800,
    "lr":          1e-3,
    "lr_min":      1e-5,
    "lbfgs_iters": 50,
}

DT_SINGLE = 1.0   # [s] single FEM time step

# ---------------------------------------------------------------------------
# Physical constants (must match PINN training in multi_window_trainer.py)
# ---------------------------------------------------------------------------
_K      = 150.0    # [W/mK]
_RHO_CP = 2.4e6    # [J/m3K]
_H      = 5000.0   # [W/m2K]
_T_W    = 20.0     # [deg C]
_T_INIT = 540.0    # [deg C]
_LX     = 1.3      # [m]
_LY     = 0.6      # [m]
_N_GRID = 50       # grid resolution per axis

# First-mode eigenvalues for 2D rectangle with Robin BC on all sides.
# Solved from:  mu * tan(mu * L_half) = h / K
# x: mu_x * tan(mu_x * 0.65) = 33.33  ->  mu_x = 2.31 rad/m
# y: mu_y * tan(mu_y * 0.30) = 33.33  ->  mu_y = 4.80 rad/m
_MU_X   = 2.31    # rad/m
_MU_Y   = 4.80    # rad/m
_ALPHA  = _K * (_MU_X**2 + _MU_Y**2) / _RHO_CP   # ~1.77e-3 /s


def fem_solver_2d(t: float, device=torch.device("cpu")) -> FEMCheckpoint:
    """
    Proper 2D analytical reference for the heat equation with Robin BC.

    T(x, y, t) = T_w + (T_init - T_w)
                 * cos(mu_x * (x - Lx/2))
                 * cos(mu_y * (y - Ly/2))
                 * exp(-alpha * t)

    This is the CORRECT first-mode solution, consistent with the Robin BC
    parameters used in PINN training (h=5000, K=150, rho_Cp=2.4e6).
    Replaces the incorrect 0D placeholder in fem_interface.from_analytical().

    Key difference from 0D placeholder:
      - 0D: T = constant everywhere (no spatial gradient)
      - 2D: strong gradient near walls (Bi_x=21.7, Bi_y=10.0)
    """
    x = torch.linspace(0.0, _LX, _N_GRID, device=device)
    y = torch.linspace(0.0, _LY, _N_GRID, device=device)
    xx, yy = torch.meshgrid(x, y, indexing="ij")

    x_c = xx - _LX / 2.0
    y_c = yy - _LY / 2.0
    T = (_T_W
         + (_T_INIT - _T_W)
         * torch.cos(torch.tensor(_MU_X) * x_c)
         * torch.cos(torch.tensor(_MU_Y) * y_c)
         * float(np.exp(-_ALPHA * t)))

    return FEMCheckpoint(
        t       = t,
        T_field = T.flatten(),
        x_grid  = xx.flatten(),
        y_grid  = yy.flatten(),
    )


def fem_solver(t: float, device=torch.device("cpu")) -> FEMCheckpoint:
    """Default FEM solver — uses the proper 2D analytical reference."""
    return fem_solver_2d(t, device=device)


def run_single_comparison(k: int,
                          t_start: float,
                          use_end_sup: bool,
                          device: torch.device) -> dict:
    """Compare sequential vs MSWP for one (k, t_start) segment."""
    t_end = t_start + k * DT_SINGLE
    print(f"\n{'='*60}")
    print(f"k_skip={k} | t=[{t_start:.0f}, {t_end:.0f}]s | end_supervision={use_end_sup}")
    print(f"{'='*60}")

    result = compare_mswp_vs_sequential(
        model_cfg            = DEFAULT_MODEL_CFG,
        fem_solver           = lambda t: fem_solver(t, device),
        t_start              = t_start,
        t_end                = t_end,
        k_skip               = k,
        dt_single            = DT_SINGLE,
        train_kwargs_single  = TRAIN_SINGLE,
        train_kwargs_wide    = TRAIN_WIDE,
        use_end_supervision  = use_end_sup,
        n_query              = 500,
        device               = device,
    )

    fname = RESULTS_DIR / f"compare_k{k}_t{int(t_start)}_endsup{int(use_end_sup)}.json"
    with open(fname, "w") as f:
        json.dump(result, f, indent=2)
    print(f"\nSaved: {fname}")
    return result


def run_k_sweep(device: torch.device) -> list:
    """Run comparison for k_skip in {2, 3, 4, 5}, with and without end supervision."""
    all_results = []
    t_start = 5.0   # early rapid cooling phase

    for k in [2, 3, 4, 5]:
        for use_end_sup in [False, True]:
            r = run_single_comparison(k, t_start, use_end_sup, device)
            r["use_end_supervision"] = use_end_sup
            all_results.append(r)

    summary_path = RESULTS_DIR / "k_sweep_summary.json"
    with open(summary_path, "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"\nK-sweep summary saved: {summary_path}")

    print("\n-- Result Table --")
    print(f"{'k':>4} {'end_sup':>8} {'MAE_seq':>10} {'MAE_mswp':>10} "
          f"{'Improvement':>12} {'Winner':>12}")
    for r in all_results:
        es = "yes" if r.get("use_end_supervision") else "no"
        print(f"{r['k_skip']:>4} {es:>8} {r['mae_sequential']:>10.3f} "
              f"{r['mae_mswp']:>10.3f} {r['improvement_pct']:>+11.1f}% "
              f"{r['winner']:>12}")

    return all_results


def run_full_series(k: int, use_end_sup: bool, device: torch.device):
    """Run MSWP over the full 30-second quenching series."""
    t_steps = np.arange(0.0, 30.5, DT_SINGLE)
    print(f"\n{'='*60}")
    print(f"Full series MSWP | k_skip={k} | t=[0, 30]s | "
          f"{len(t_steps)} steps | end_sup={use_end_sup}")
    print(f"{'='*60}")

    _, history, summary = run_multiwindow(
        model_cfg            = DEFAULT_MODEL_CFG,
        fem_solver           = lambda t: fem_solver(t, device),
        t_steps              = t_steps,
        k_skip               = k,
        use_end_supervision  = use_end_sup,
        train_kwargs         = TRAIN_WIDE,
        n_query              = 300,
        device               = device,
    )

    out = {"summary": summary, "history": history}
    fname = RESULTS_DIR / f"full_series_k{k}_endsup{int(use_end_sup)}.json"
    with open(fname, "w") as f:
        json.dump(out, f, indent=2)
    print(f"\nSaved: {fname}")
    print(f"Mean MAE:   {summary['mean_mae']:.3f} deg C")
    print(f"Wall time:  {summary['total_wall_time_s']:.1f}s")
    print(f"Segments:   {summary['n_segments']}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Level 10: Multi-Step Window PINN (MSWP)"
    )
    parser.add_argument("--k",           type=int,   default=3,
                        help="k_skip — number of FEM steps per PINN window (default: 3)")
    parser.add_argument("--t_start",     type=float, default=5.0,
                        help="Segment start time in seconds (default: 5.0)")
    parser.add_argument("--end_sup",     action="store_true",
                        help="Add FEM(t_end) supervision loss")
    parser.add_argument("--sweep",       action="store_true",
                        help="Run k={2,3,4,5} comparison sweep")
    parser.add_argument("--full_series", action="store_true",
                        help="Run full 30s quenching series with MSWP")
    parser.add_argument("--cuda",        action="store_true",
                        help="Use GPU if available")
    args = parser.parse_args()

    device = torch.device("cuda" if args.cuda and torch.cuda.is_available() else "cpu")
    print(f"Device: {device}")

    if args.sweep:
        run_k_sweep(device)
    elif args.full_series:
        run_full_series(args.k, args.end_sup, device)
    else:
        run_single_comparison(args.k, args.t_start, args.end_sup, device)
