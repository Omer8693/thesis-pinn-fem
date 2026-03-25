# NAS-PINNs: Neural Architecture Search for FEM Time-Step Acceleration

**Author:** Omer Cetinkaya
**Year:** 2026
**Thesis Context:** MSc / Research Project — Computational Engineering

---

## Abstract

This repository presents a progressive, nine-level framework that investigates whether Neural Architecture Search (NAS) can identify Physics-Informed Neural Network (PINN) architectures capable of replacing intermediate Finite Element Method (FEM) time steps in transient thermal simulations. The physical problem of concern is water quenching of an A356 aluminium alloy component — a process with high industrial relevance in automotive subframe manufacturing. Three NAS strategies are evaluated: Bayesian optimisation (TPE), NSGA-II, and NSGA-III. The framework begins with a global single-shot predictor (Level 1) and culminates in self-adaptive PINNs with Fourier feature embedding (Level 9). The best result — L9 SA+Fourier (NSGA-II) — achieves L2 = 0.014, which is **9.2× better than FEM skip=1** with near-instant inference (≈ 0.01 s).

---

## Physical Problem

**Material:** A356 cast aluminium alloy
**Domain:** Rectangular cross-section (2D: 1.3 m × 0.6 m; 3D: 1.3 m × 0.6 m × 0.4 m)
**Initial temperature:** T_0 = 540 °C
**Coolant bath:** T_water = 20 °C
**Simulation duration:** 30 s

### Governing PDE

The transient heat conduction equation:

    rho * C_p * dT/dt = K * nabla^2(T)    in Omega

with Robin boundary condition on the wetted surface:

    K * dT/dn = h(T) * (T - T_water)      on partial Omega

### Material Properties (A356)

| Property                  | Value              |
|---------------------------|--------------------|
| Thermal conductivity K    | 150 W/(m·K)        |
| Volumetric heat capacity  | 2.4e6 J/(m³·K)     |
| Elastic modulus E         | 69 GPa             |
| Thermal expansion alpha   | 22e-6 /°C          |

### Analytical Cooling Reference

    T(t) = 20 + 520 * exp(-1.75e-3 * t)

Derived from the Robin BC fundamental mode using the material parameters reported in Mortensen et al. (2026).

---

## Repository Structure

```
thesis-pinn-fem/
|
+-- src/                          Core framework
|   +-- nas/                      NAS engine (Bayesian, NSGA-II, NSGA-III)
|   +-- pinn/                     PINN model classes and trainers
|   +-- physics/                  PDE residual evaluators
|   +-- utils/                    Logging, seeding, checkpointing
|
+-- problems/                     PDE definitions
|   +-- quenching.py              A356 transient heat transfer
|   +-- poisson.py                Poisson benchmark problems
|
+-- level1_single_shot/           L1: global T(t,x,y) predictor
+-- level2_timestepper/           L2: temporal skip operator (2D)
+-- level3_hybrid_fem/            L3: adaptive FEM+PINN routing
+-- level4_distortion/            L4: thermal-to-distortion mechanics
+-- level5_refinement/            L5: extended Adam training (20k epochs)
+-- level6_poisson_benchmark/     L6: Poisson auxiliary fine-tuning
+-- level7_temporal/              L7A: temporal skip analysis (extended)
+-- level7_multiDomain/           L7B: 5-geometry Poisson NAS
+-- level8_nas_mco_pinn/          L8: 3D multi-domain NAS (4 geometries)
+-- level9_sa_fourier/            L9: SA-PINN + Fourier Feature Embedding
|
+-- docs/                         Static documentation website (GitHub Pages)
|   +-- index.html                Interactive research overview
|   +-- levels/                   Per-level detail pages (level1–level8)
|   +-- static/                   CSS, JavaScript, images, result JSONs
|   +-- results.html              Results and comparison page
|   +-- references.html           Full academic reference list
|
+-- results/                      Generated plots and summary tables
+-- README.md                     This file
+-- .gitignore
```

---

## Eight-Level Experimental Framework

| Level | Title                     | Dimensionality | Key Contribution                                         |
|-------|---------------------------|----------------|----------------------------------------------------------|
| L1    | Single-Shot NAS-PINN      | 2D             | Architecture search for global T(t,x,y) predictor        |
| L2    | Temporal Skip Operator    | 2D             | PINN replaces FEM at intermediate time steps             |
| L3    | Hybrid FEM + PINN         | 2D             | Residual-based adaptive routing; 80 % FEM reduction      |
| L4    | Thermal Distortion        | 2D             | Temperature field mapped to CMM distortion (mm)          |
| L5    | Extended Adam Training    | 2D             | 20 000 epochs; Bayesian L2 = 0.030, NSGA-II = 0.055      |
| L6    | Poisson Auxiliary Loss    | 2D             | Auxiliary Poisson fine-tuning; marginal gain             |
| L7    | Multi-Domain Poisson NAS  | 2D             | NAS across 5 geometries; circle L2 = 1.4e-4             |
| L8    | 3D Multi-Domain NAS-PINN  | 3D             | 4 geometries, 3 optimizers, 4 skip values               |
| L9    | SA-PINN + Fourier Embed.  | 2D + 3D        | Learnable loss weights + Fourier features; best L2=0.014 |

---

## NAS Search Space

All three optimisers search the same architecture space:

| Hyperparameter         | Options                                      |
|------------------------|----------------------------------------------|
| Number of hidden layers| {2, 3, 4, 5, 6}                              |
| Neurons per layer      | {32, 48, 64, 96, 128, 160, 192, 256}         |
| Activation function    | tanh, relu, swish, gelu                      |
| Architecture type      | Uniform depth (same neuron count per layer)  |

**Optimisers:**
- **Bayesian (TPE):** Single-objective, minimises L2_rel. Uses Optuna with 50 trials.
- **NSGA-II:** Multi-objective (L2, parameter count). Evolutionary, 20 generations.
- **NSGA-III:** Multi-objective with structured reference-point directions. 20 generations.

---

## Level 8 — 3D Multi-Domain NAS-PINN

Level 8 extends the framework to three-dimensional geometries. Four domain shapes are studied:

| Domain       | Geometry Description                        |
|--------------|---------------------------------------------|
| Rectangular  | Box 1.3 m × 0.6 m × 0.4 m                 |
| Cylinder     | Radius 0.25 m, height 0.6 m               |
| Stacked      | Two cubes (0.5 m³ each), vertically aligned |
| L-Shape      | Horizontal slab + vertical fin             |

Training uses 800 epochs (v1) and 2 000 epochs (v2) with cosine learning rate decay. Four skip values are evaluated: skip ∈ {1, 2, 4, 6}.

**Selected v2 Results (2 000 epochs, MAE in °C):**

| Domain      | Optimizer | skip=1 | skip=2 | skip=4 | skip=6 |
|-------------|-----------|--------|--------|--------|--------|
| Rectangular | Bayesian  |   4.21 |   5.83 |  11.20 |  18.70 |
| Cylinder    | Bayesian  |   3.87 |   6.45 |  12.10 |  20.30 |
| Stacked     | Bayesian  |   6.33 |  10.90 |  18.40 |  27.60 |
| L-Shape     | Bayesian  |   2.74 |   4.92 |   5.61 |   8.84 |

Feasibility threshold: MAE < 10 °C. Rectangular and cylinder domains satisfy this at skip=2; the L-shape domain satisfies it at skip=4 and skip=6.

---

## Key Findings

1. **Architecture depth determines accuracy.** The Bayesian 5-layer network achieves L2_rel = 0.076 at Level 1, while the NSGA-III 3-layer network reaches only 0.513 under identical training conditions — a 7-fold difference attributable primarily to network capacity.

2. **Epoch count is the primary bottleneck for multi-objective optimisers.** At 500 epochs, only Bayesian converges at skip=2. At 2 000 epochs, all three optimisers satisfy the convergence criterion (MAE ratio < 1.5).

3. **Bayesian skip=2 outperforms skip=1 (2D).** The temporal skip operator at skip=2 produces a lower MAE (33.2 °C) than skip=1 (43.6 °C) for the Bayesian architecture, indicating that PINN avoids the sequential numerical error accumulation present in step-by-step FEM.

4. **3D extension is feasible for rectangular and cylindrical domains.** At skip=4 (71 % FEM reduction), Bayesian PINNs achieve MAE < 12 °C for rectangular and cylinder geometries. Stacked and complex domain shapes require more training or architecture refinement.

5. **Poisson auxiliary loss provides marginal improvement.** Fine-tuning with an auxiliary Poisson loss reduces L2_rel by 6–17 %, which is insufficient to justify the additional training cost in production use.

6. **Self-adaptive weights (L9) outperform fixed weights.** Learnable λ values allow the network to automatically balance PDE, BC, and IC losses. Combined with Fourier feature embedding, L9 achieves L2 = 0.014 — the lowest across all levels and 9.2× better than FEM skip=1 (L2 = 0.126). Inference time after a single training pass is ≈ 0.01 s, making it suitable for real-time prediction.

---

## Installation

```bash
# Clone the repository
git clone https://github.com/<your-username>/thesis-pinn-fem.git
cd thesis-pinn-fem

# Install dependencies
pip install torch numpy scipy matplotlib optuna pymoo
```

Python 3.9 or later is required. PyTorch 2.x is recommended. No GPU is required; all experiments in this study were conducted on CPU.

---

## Running Experiments

Each level has a self-contained runner script in its directory:

```bash
# Level 1 — Single-Shot NAS
python level1_single_shot/run_nas.py

# Level 2 — Temporal Skip Operator
python level2_timestepper/run_skip.py

# Level 8 — 3D Multi-Domain NAS
python level8_nas_mco_pinn/run_3d_nas.py
```

Result JSON files are written to the corresponding `level*/` directory and are also consumed by the documentation website.

---

## Documentation Website

The `docs/` folder contains a static website that can be served locally or via GitHub Pages.

**Local preview:**
```bash
cd docs
python -m http.server 8080
# Open: http://localhost:8080
```

**Online access (GitHub Pages):**
After enabling GitHub Pages from the repository Settings (Source: `docs/` folder, branch: `main`), the website is accessible at:

    https://<your-username>.github.io/thesis-pinn-fem/

The website includes interactive Plotly visualisations for all levels, 3D geometry viewers, an animated training convergence display, and a full results comparison table.

---

## Reference

> Dag Mortensen, Gulshan Noorsumar, Hallvard G. Fjaer, Reza Babaei, Per Erik Dronen (2026).
> "Mitigating distortions in cast automotive subframes: A finite element simulation approach."
> *The International Journal of Advanced Manufacturing Technology.*
> https://doi.org/10.1007/s00170-026-17515-w

All FEM baseline values, CMM distortion measurements, and A356 material properties originate from this publication. The analytical cooling reference T(t) = 20 + 520·exp(-1.75e-3·t) is derived from the Robin BC fundamental mode using the material parameters therein.

---

## License

This project is released for academic and research purposes. Commercial use requires explicit permission from the author.
