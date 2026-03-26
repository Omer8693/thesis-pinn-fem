# NAS-PINNs: Neural Architecture Search for FEM Time-Step Acceleration

**Author:** Omer Cetinkaya  
**Year:** 2026  
**Course:** IKT590-G 26V Master's Thesis  

---

## Abstract

This repository presents a progressive, nine-level framework that investigates whether Neural Architecture Search (NAS) can identify Physics-Informed Neural Network (PINN) architectures capable of replacing intermediate Finite Element Method (FEM) time steps in transient thermal simulations. The physical problem is water quenching of an A356 aluminium alloy component — a process with high industrial relevance in automotive subframe manufacturing. Three NAS strategies are evaluated: Bayesian Optimisation, NSGA-II, and NSGA-III. The framework begins with a global single-shot predictor (Level 1) and culminates in self-adaptive PINNs with Fourier feature embedding (Level 9). The best result — L9 SA+Fourier (NSGA-II) — achieves **L2 = 0.014**, which is 9.2× better than the FEM skip=1 baseline and 18,400× faster at inference (≈ 0.01 s vs 184 s).

---

## FEM Reference

All FEM baseline values, material properties, and CMM distortion measurements come from:

> Dag Mortensen, Gulshan Noorsumar, Hallvard G. Fjaer, Reza Babaei, Per Erik Dronen (2026).  
> "Mitigating distortions in cast automotive subframes: A finite element simulation approach."  
> *The International Journal of Advanced Manufacturing Technology.*  
> https://doi.org/10.1007/s00170-026-17515-w

We did **not** implement FEM. We used this paper's simulation data as ground truth.

---

## Physical Problem

| Parameter | Value |
|-----------|-------|
| Material | A356 cast aluminium alloy |
| Domain (2D) | 1.3 m × 0.6 m |
| Domain (3D) | 1.3 m × 0.6 m × 0.4 m |
| Initial temperature | 540 °C |
| Coolant temperature | 20 °C |
| Simulation duration | 30 s (21 FEM steps) |
| k (thermal conductivity) | 150 W/(m·K) |
| ρ·cp (volumetric heat capacity) | 2.4×10⁶ J/(m³·K) |
| h (convective HTC) | 5000 W/(m²·K) |

**Governing PDE:**

```
ρ·cp · ∂T/∂t = k · ∇²T
```

**Boundary condition (Robin):**

```
-k · ∂T/∂n = h(T) · (T - T_water)
```

---

## Repository Structure

```
thesis-pinn-fem/
│
├── src/                          Core framework (NAS, PINN, trainers, physics)
│   ├── config.py                 Physical constants (A356 properties)
│   ├── physics_model.py          PDE residuals, HTC model, material interpolation
│   ├── pinn_network.py           PINN neural network class
│   ├── trainers.py               Adam training loops
│   ├── arch_search.py            Architecture search utilities
│   ├── opt_bayesian.py           Bayesian optimiser (scikit-optimize)
│   ├── opt_nsga2.py              NSGA-II optimiser (pymoo)
│   ├── opt_nsga3.py              NSGA-III optimiser (pymoo)
│   ├── baseline_data.py          FEM reference data from [Mortensen et al., 2026]
│   └── experiment_runner.py      Experiment orchestration
│
├── problems/                     PDE problem definitions
│   ├── quenching.py              A356 transient heat transfer (main problem)
│   ├── poisson.py                Poisson benchmark
│   ├── burgers.py                Burgers equation
│   └── allen_cahn.py             Allen-Cahn equation
│
├── level1_single_shot/           L1: global T(t,x,y) predictor
├── level2_timestepper/           L2: temporal skip operator
├── level3_hybrid_fem/            L3: adaptive FEM+PINN routing
├── level4_distortion/            L4: thermal-to-distortion mechanics
├── level5_refinement/            L5: Adam → L-BFGS two-stage training
├── level6_poisson_benchmark/     L6: Poisson auxiliary fine-tuning
├── level7_temporal/              L7A: temporal skip regime analysis
├── level7_multiDomain/           L7B: 5-geometry Poisson NAS
├── level8_nas_mco_pinn/          L8: 3D multi-domain (4 geometries, 48 runs)
├── level9_sa_fourier/            L9: SA-PINN + Fourier features (best result)
│   ├── src/
│   │   ├── sa_loss.py            Self-adaptive loss weights (SelfAdaptiveWeights)
│   │   ├── fourier_pinn.py       Fourier feature PINN (FourierEmbedding + FourierPINN)
│   │   └── sa_trainer.py         SA training loop
│   ├── main_level9.py            Main experiment script
│   └── results/                  All L9 result JSONs + plots
│
├── reports/
│   └── professor_brief/
│       ├── generate_report.py    → generates NAS_PINNS3_professor_brief.pdf
│       ├── generate_pptx.py      → generates NAS_PINNS3_Presentation.pptx
│       ├── NAS_PINNS3_professor_brief.pdf   (5-page academic report)
│       └── NAS_PINNS3_Presentation.pptx     (14-slide presentation)
│
├── README.md
└── .gitignore
```

---

## Nine-Level Framework

| Level | Title | Best L2 | Key Contribution |
|-------|-------|---------|-----------------|
| L1 | Single-Shot NAS-PINN | 0.076 | Baseline PINN with NAS architecture search |
| L2 | Temporal Skip Operator | 0.108 (skip=2) | One PINN predicts s FEM steps ahead; 48% FEM reduction |
| L3 | Hybrid FEM + PINN | ~0.12 | Residual-based adaptive routing |
| L4 | Thermal Distortion | MAE=14.4°C | Temperature → CMM distortion mapping |
| L5 | Adam + L-BFGS | 0.030 | Two-stage training; L-BFGS refinement |
| L6 | Poisson Benchmark | ~0.018 | Generalization test on Poisson PDE |
| L7A | Temporal Analysis | ~0.025 | Systematic time-skip regime study |
| L7B | Multi-Domain NAS | ~0.022 | NAS across 5 geometries |
| L8 | 3D MCO-PINNs | MAE=2.19°C | 3D geometries, MCO adaptive weights, 48 runs |
| **L9** | **SA + Fourier** | **0.014** | **Learnable loss weights + Fourier features** |

---

## Three Key Technical Contributions

### 1. Temporal Skip Operator (project-specific design)

Standard PINNs train one network per FEM time step (21 runs). We designed a single network that predicts `s` steps ahead:

```
T̂(t + s·Δt) = T_IC + τ · fθ(x, y, τ, T_IC)
```

where `τ = t/(s·Δt) ∈ [0,1]`. At `τ=0`, the prediction equals `T_IC` exactly (initial condition automatically satisfied). Inspired by IC-residual formulations in early PINN work [Lagaris et al., 1998].

### 2. Fourier Feature Embedding (from [Tancik et al., 2020])

Standard MLPs have spectral bias — they learn low-frequency patterns first. A356 quenching has rapid initial cooling (ΔT ≈ 200°C in first 5s). We apply random Fourier features before the MLP:

```
γ(v) = [sin(2π·B·v), cos(2π·B·v)]    B ~ N(0, σ²)
```

Settings: n_fourier=64, σ=1.0. B is frozen during training.

### 3. Self-Adaptive Loss Weights (from [Wang et al., 2022])

PINN loss scales differ by 10⁴. Instead of manual weight tuning, we make weights learnable:

```
L = λ_phys·L_phys + λ_bc·L_bc + λ_ic·L_ic
λ = softplus(w),  w trained jointly with network
```

Final learned values: λ_phys ≈ 0.48, λ_bc ≈ 9.28, λ_ic ≈ 9.28.

---

## Level 9 Results

| Variant | Optimizer | Dim | Best L2 | Train Time | Params |
|---------|-----------|-----|---------|-----------|--------|
| SA+Fourier | Bayesian | 2D | 0.0253 | 482s | 111,439 |
| SA+Fourier | **NSGA-II** | **2D** | **0.0137** | **444s** | **67,015** |
| SA+Fourier | NSGA-III | 2D | 0.0668 | 412s | 21,151 |
| SA+Fourier | Bayesian | 3D | 0.247 | 596s | 111,439 |
| SA-only | Bayesian | 2D | 0.0151 | 404s | 92,564 |
| SA-only | NSGA-II | 2D | 0.0397 | 378s | 47,890 |

**Best: L2 = 0.0137** (SA+Fourier, NSGA-II, 2D)  
- 4× improvement over L5 reference (L2=0.055)  
- 9.2× better than FEM skip=1 (L2=0.126)  
- Inference: 0.01s vs FEM 184s → **18,400× speedup**

---

## References

1. M. Raissi, P. Perdikaris, G.E. Karniadakis, "Physics-informed neural networks," J. Comput. Phys., 2019. DOI: 10.1016/j.jcp.2018.10.045
2. D. Mortensen et al., "Mitigating distortions in cast automotive subframes," Int J Adv Manuf Technol, 2026. DOI: 10.1007/s00170-026-17515-w
3. M. Tancik et al., "Fourier Features Let Networks Learn High Frequency Functions," NeurIPS, 2020.
4. S. Wang et al., "Understanding and Mitigating Gradient Flow Pathologies in PINNs," SIAM J. Sci. Comput., 2021.
5. K. Deb et al., "NSGA-II," IEEE Trans. Evol. Comput., 2002. DOI: 10.1109/4235.996017
6. K. Deb & H. Jain, "NSGA-III," IEEE Trans. Evol. Comput., 2014. DOI: 10.1109/TEVC.2013.2281535
7. J. Snoek et al., "Practical Bayesian Optimization," NeurIPS, 2012.
8. I.E. Lagaris et al., "Artificial neural networks for solving ODEs and PDEs," IEEE Trans. Neural Netw., 1998.
