"""
generate_word.py  —  Compact 5-page project report (professor brief style).
Run:  python reports/professor_brief/generate_word.py
"""

import os
from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

# ---------------------------------------------------------------------------
# PATHS
# ---------------------------------------------------------------------------
BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(BASE, "..", ".."))
L8   = os.path.join(ROOT, "level8_nas_mco_pinn", "results")
L9   = os.path.join(ROOT, "level9_sa_fourier",   "results", "plots")
OUT  = os.path.join(BASE, "NAS_PINNS3_professor_brief.docx")

# ---------------------------------------------------------------------------
# COLORS
# ---------------------------------------------------------------------------
NAVY      = RGBColor(0x1a, 0x23, 0x7e)
DARK_GRAY = RGBColor(0x33, 0x33, 0x33)
WHITE     = RGBColor(0xFF, 0xFF, 0xFF)
L_BLUE    = "D6E4F0"
TBLNAV    = "1a237e"
GRAYBG    = "F2F2F2"
GREEN_H   = "1B5E20"   # dark green header for MAE table
L_GREEN   = "C8E6C9"   # light green
L_YELLOW  = "FFF9C4"
L_RED     = "FFCDD2"

FEM_SHORT = "D. Mortensen, G. Noorsumar, H.G. Fjaer, R. Babaei, P.E. Dronen (2026)"

# ---------------------------------------------------------------------------
# XML HELPERS
# ---------------------------------------------------------------------------

def set_cell_bg(cell, hex_color):
    tc   = cell._tc
    tcPr = tc.get_or_add_tcPr()
    shd  = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear"); shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_color)
    tcPr.append(shd)


def set_cell_borders(table):
    for row in table.rows:
        for cell in row.cells:
            tcPr   = cell._tc.get_or_add_tcPr()
            tcBdr  = OxmlElement("w:tcBorders")
            for side in ("top","left","bottom","right","insideH","insideV"):
                b = OxmlElement(f"w:{side}")
                b.set(qn("w:val"),"single"); b.set(qn("w:sz"),"4")
                b.set(qn("w:space"),"0");    b.set(qn("w:color"),"AAAAAA")
                tcBdr.append(b)
            tcPr.append(tcBdr)


def set_para_shading(para, hex_color):
    pPr = para._p.get_or_add_pPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"),"clear"); shd.set(qn("w:color"),"auto")
    shd.set(qn("w:fill"), hex_color)
    pPr.append(shd)


# ---------------------------------------------------------------------------
# DOCUMENT SETUP
# ---------------------------------------------------------------------------

def create_doc():
    doc = Document()
    sec = doc.sections[0]
    sec.page_width  = Cm(21.0)
    sec.page_height = Cm(29.7)
    for a in ("top_margin","bottom_margin","left_margin","right_margin"):
        setattr(sec, a, Cm(2.2))
    style = doc.styles["Normal"]
    style.font.name = "Times New Roman"
    style.font.size = Pt(10.5)
    return doc


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def heading(doc, text, level=1):
    p = doc.add_paragraph()
    r = p.add_run(text)
    r.bold = True
    if level == 1:
        r.font.size      = Pt(12)
        r.font.color.rgb = NAVY
        p.paragraph_format.space_before = Pt(10)
        p.paragraph_format.space_after  = Pt(4)
    else:
        r.font.size      = Pt(10.5)
        r.font.color.rgb = DARK_GRAY
        p.paragraph_format.space_before = Pt(7)
        p.paragraph_format.space_after  = Pt(3)
    r.font.name = "Times New Roman"
    return p


def para(doc, text, bold_start=None, indent=False, size=10.5, space_after=5):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(1)
    p.paragraph_format.space_after  = Pt(space_after)
    if indent:
        p.paragraph_format.left_indent = Cm(0.8)
    if bold_start:
        r = p.add_run(bold_start + " ")
        r.bold = True; r.font.name = "Times New Roman"; r.font.size = Pt(size)
    r = p.add_run(text)
    r.font.name = "Times New Roman"; r.font.size = Pt(size)
    return p


def bullet(doc, text, size=10.5):
    p = doc.add_paragraph(style="List Bullet")
    r = p.add_run(text)
    r.font.name = "Times New Roman"; r.font.size = Pt(size)
    p.paragraph_format.space_before = Pt(1)
    p.paragraph_format.space_after  = Pt(3)


def equation(doc, eq_text, note=None):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(4)
    p.paragraph_format.space_after  = Pt(1)
    p.paragraph_format.left_indent  = Cm(1.0)
    p.paragraph_format.right_indent = Cm(1.0)
    set_para_shading(p, GRAYBG)
    r = p.add_run(eq_text)
    r.font.name = "Courier New"; r.font.size = Pt(10); r.bold = True
    if note:
        np_ = doc.add_paragraph()
        np_.paragraph_format.space_before = Pt(1)
        np_.paragraph_format.space_after  = Pt(5)
        np_.paragraph_format.left_indent  = Cm(1.0)
        nr = np_.add_run(note)
        nr.font.name = "Times New Roman"; nr.font.size = Pt(9); nr.font.italic = True


def std_table(doc, headers, rows, col_widths=None, hdr_color=None):
    hc = hdr_color or TBLNAV
    tbl = doc.add_table(rows=1+len(rows), cols=len(headers))
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    tbl.style = "Table Grid"
    for i, h in enumerate(headers):
        c = tbl.rows[0].cells[i]
        set_cell_bg(c, hc)
        c.paragraphs[0].clear()
        r = c.paragraphs[0].add_run(h)
        r.bold = True; r.font.color.rgb = WHITE
        r.font.name = "Times New Roman"; r.font.size = Pt(9)
        c.paragraphs[0].paragraph_format.space_before = Pt(1)
        c.paragraphs[0].paragraph_format.space_after  = Pt(1)
    for ri, rd in enumerate(rows):
        row = tbl.rows[ri+1]
        bg  = L_BLUE if ri%2==0 else "FFFFFF"
        for ci, val in enumerate(rd):
            c = row.cells[ci]
            set_cell_bg(c, bg)
            c.paragraphs[0].clear()
            r = c.paragraphs[0].add_run(str(val))
            r.font.name = "Times New Roman"; r.font.size = Pt(9)
            c.paragraphs[0].paragraph_format.space_before = Pt(1)
            c.paragraphs[0].paragraph_format.space_after  = Pt(1)
    if col_widths:
        for i, w in enumerate(col_widths):
            for row in tbl.rows:
                row.cells[i].width = Cm(w)
    set_cell_borders(tbl)
    doc.add_paragraph().paragraph_format.space_after = Pt(4)
    return tbl


def mae_table(doc, headers, rows, col_widths=None):
    """MAE result table with colour coding: green < 8°C, yellow 8-15°C, red > 15°C."""
    tbl = doc.add_table(rows=1+len(rows), cols=len(headers))
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    tbl.style = "Table Grid"
    for i, h in enumerate(headers):
        c = tbl.rows[0].cells[i]
        set_cell_bg(c, GREEN_H)
        c.paragraphs[0].clear()
        r = c.paragraphs[0].add_run(h)
        r.bold = True; r.font.color.rgb = WHITE
        r.font.name = "Times New Roman"; r.font.size = Pt(8.5)
        c.paragraphs[0].paragraph_format.space_before = Pt(1)
        c.paragraphs[0].paragraph_format.space_after  = Pt(1)
    for ri, rd in enumerate(rows):
        row = tbl.rows[ri+1]
        for ci, val in enumerate(rd):
            c = row.cells[ci]
            if ci >= 2:           # numeric MAE columns
                try:
                    v = float(val)
                    bg = L_GREEN if v < 8 else (L_YELLOW if v < 15 else L_RED)
                except Exception:
                    bg = "FFFFFF"
            else:
                bg = "F5F5F5" if ri%2==0 else "FFFFFF"
            set_cell_bg(c, bg)
            c.paragraphs[0].clear()
            r = c.paragraphs[0].add_run(str(val))
            r.font.name = "Times New Roman"; r.font.size = Pt(8.5)
            c.paragraphs[0].paragraph_format.space_before = Pt(1)
            c.paragraphs[0].paragraph_format.space_after  = Pt(1)
    if col_widths:
        for i, w in enumerate(col_widths):
            for row in tbl.rows:
                row.cells[i].width = Cm(w)
    set_cell_borders(tbl)
    doc.add_paragraph().paragraph_format.space_after = Pt(4)
    return tbl


def caption(doc, text):
    p = doc.add_paragraph(text)
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(1)
    p.paragraph_format.space_after  = Pt(7)
    for r in p.runs:
        r.font.name = "Times New Roman"; r.font.size = Pt(9); r.font.italic = True


def img(doc, path, w_cm=14, cap=None):
    if not os.path.isfile(path):
        return
    try:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_before = Pt(4)
        p.paragraph_format.space_after  = Pt(1)
        p.add_run().add_picture(path, width=Cm(w_cm))
    except Exception:
        return
    if cap:
        caption(doc, cap)


def hr(doc):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(3)
    p.paragraph_format.space_after  = Pt(3)
    pPr = p._p.get_or_add_pPr()
    pBdr = OxmlElement("w:pBdr")
    b = OxmlElement("w:bottom")
    b.set(qn("w:val"),"single"); b.set(qn("w:sz"),"6")
    b.set(qn("w:space"),"1");    b.set(qn("w:color"),"1a237e")
    pBdr.append(b); pPr.append(pBdr)


# ---------------------------------------------------------------------------
# DOCUMENT CONTENT
# ---------------------------------------------------------------------------

def build():
    doc = create_doc()

    # ── Title block ─────────────────────────────────────────────────────────
    tp = doc.add_paragraph()
    tp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    tp.paragraph_format.space_before = Pt(6)
    tp.paragraph_format.space_after  = Pt(4)
    tr = tp.add_run(
        "Step Optimization in Thermal Simulation with PINNs: "
        "Selective FEM Step Skipping via Neural Architecture Search"
    )
    tr.bold = True; tr.font.name = "Times New Roman"
    tr.font.size = Pt(13); tr.font.color.rgb = NAVY

    sp = doc.add_paragraph()
    sp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    sp.paragraph_format.space_after = Pt(4)
    for txt, bold in [
        ("Omer Cetinkaya", True),
        ("  |  IKT590-G 26V — Master's Thesis  |  March 2026", False)
    ]:
        r = sp.add_run(txt)
        r.bold = bold; r.font.name = "Times New Roman"; r.font.size = Pt(10.5)

    hr(doc)

    # ── Section 1: Introduction ─────────────────────────────────────────────
    heading(doc, "1.  Introduction")
    para(doc,
        "In this project we investigated whether Physics-Informed Neural Networks (PINNs) "
        "can replace intermediate Finite Element Method (FEM) time steps in a transient "
        "thermal simulation. We chose the water quenching of an A356 aluminium automotive "
        "subframe as our test case — a real manufacturing process where engineers currently "
        "rely on slow FEM simulations to predict and control part distortion."
    )
    para(doc,
        "The governing PDE is ρ·cₚ·∂T/∂t = k·∇²T with a nonlinear Robin boundary condition "
        "-k·∂T/∂n = h(T)·(T − T∞). We used FEM reference data from "
        + FEM_SHORT + " as ground truth — we did not implement FEM ourselves. "
        "Their simulation runs 21 time steps totalling 184 s "
        "(A356: ρ = 2670 kg/m³, cₚ = 963 J/(kg·K), k = 151 W/(m·K))."
    )
    para(doc,
        "We developed a nine-level framework, adding one new contribution per level. "
        "Our three main technical contributions are: "
        "(i) a temporal skip operator we designed to predict s FEM steps ahead from any "
        "initial condition; "
        "(ii) Fourier feature embedding [Tancik et al., 2020] to overcome spectral bias; "
        "(iii) self-adaptive loss weights [Wang et al., 2022] replacing fixed λ values. "
        "We validated our approach across four 3D geometries and in 2D with three NAS optimisers. "
        "Our best result: L2 = 0.014 (SA+Fourier, NSGA-II, 2D) — 9.2× better than FEM skip=1."
    )

    # ── Section 2: Skip Operator ─────────────────────────────────────────────
    heading(doc, "2.  The Temporal Skip Operator — Our Design")
    para(doc,
        "Instead of training one PINN per FEM time step (21 separate runs), we designed "
        "a single network that predicts s steps ahead from any given initial condition:"
    )
    equation(doc,
        "T_hat(t + s*dt)  =  T_IC  +  tau * f_theta(x, y, [z,] tau, T_IC)",
        note="tau = t/(s*dt) in [0,1]. At tau=0, output equals T_IC exactly — IC is satisfied without a separate loss term."
    )
    para(doc,
        "We found that skip=2 outperforms skip=1 (L2: 0.108 vs 0.126) because "
        "our PINN smooths the step-to-step numerical noise present in the FEM output. "
        "This was a counterintuitive finding: predicting further ahead actually gives better accuracy."
    )

    std_table(doc,
        headers=["Skip s", "FEM Steps Saved", "Reduction", "PINN Calls"],
        rows=[
            ["s = 1  (baseline)", "0 steps",  "0%",  "21"],
            ["s = 2",             "10 steps", "52%", "11"],
            ["s = 4",             "15 steps", "71%",  "6"],
            ["s = 6",             "17 steps", "81%",  "4"],
        ],
        col_widths=[3.5, 3.5, 2.5, 2.5]
    )
    caption(doc, "Table 1. FEM computation savings per skip value (21 total time steps).")

    # ── Section 3: Methods ──────────────────────────────────────────────────
    heading(doc, "3.  Training, NAS, and Level 9 Techniques")
    para(doc,
        "We trained each PINN window with Adam (30,000 epochs at Level 9). "
        "For Neural Architecture Search (NAS) we defined a search space of "
        "layers 3–6, neurons/layer 64–160, and activations {Tanh, GELU, SiLU, ReLU}. "
        "We compared three NAS strategies: Bayesian Optimisation (scikit-optimize), "
        "NSGA-II and NSGA-III (pymoo), each evaluating ~500 architectures. "
        "We found that NSGA-II consistently found the best accuracy/size trade-off."
    )

    heading(doc, "Fourier Feature Embedding  [Tancik et al., 2020]", level=2)
    para(doc,
        "We noticed that our standard PINN converged slowly in the first 5 seconds of "
        "the quench — the period with the fastest cooling (ΔT ≈ 200 °C). "
        "This is the spectral bias problem: MLPs learn low-frequency patterns first. "
        "To fix this, we prepended a frozen random Fourier projection to the MLP input:"
    )
    equation(doc,
        "gamma(v)  =  [ sin(2*pi*B*v) ,  cos(2*pi*B*v) ]",
        note="B ~ N(0, sigma^2), frozen at init. We used n_fourier=64, sigma=1.0 → 128-dim encoding for (t,x,y)."
    )

    heading(doc, "Self-Adaptive Loss Weights  [Wang et al., 2022]", level=2)
    para(doc,
        "We observed that our three PINN loss terms (PDE, BC, IC) differ by ~10⁴ in scale, "
        "making manual weight tuning unreliable. Instead of fixing λ values, we made them "
        "learnable: λ = softplus(w), trained jointly with the network at a lower LR (1e-4). "
        "Our best model converged to: λ_phys ≈ 0.48, λ_bc ≈ 9.28, λ_ic ≈ 9.28 — "
        "the optimiser automatically learned to weight BC/IC 19× more than the PDE residual."
    )

    # ── Section 4: Level 8 Results (3D, 48 runs) ───────────────────────────
    heading(doc, "4.  Results: Level 8 — 3D Multi-Geometry (48 Runs)")
    para(doc,
        "At Level 8 we extended our framework to four 3D geometries: Rectangular Prism "
        "(1.3×0.6×0.4 m), Cylinder (R=0.2 m, H=0.4 m), Stacked Cubes, and L-Shape. "
        "We ran 48 experiments (4 domains × 3 NAS optimisers × 4 skip values) "
        "and used MCO adaptive weights (w_i = 1/σ_i²) during training."
    )

    mae_table(doc,
        headers=["Domain", "Optimizer", "skip=1 (0%)", "skip=2 (52%)", "skip=4 (71%)", "skip=6 (81%)"],
        rows=[
            ["Rectangular", "Bayesian",  "5.53",  "10.31", "21.39", "15.65"],
            ["Rectangular", "NSGA-II",   "5.41",  "10.39", "20.99", "25.86"],
            ["Rectangular", "NSGA-III",  "5.41",  "10.50", "21.00", "25.90"],
            ["Cylinder",    "Bayesian",  "5.33",  "10.69", "11.54", "10.23"],
            ["Cylinder",    "NSGA-II",   "4.23",  " 8.69", "18.93", "25.38"],
            ["Cylinder",    "NSGA-III",  "4.20",  " 9.14", "16.24", "22.54"],
            ["Stacked",     "Bayesian",  "4.95",  " 9.80", "21.64", "17.18"],
            ["Stacked",     "NSGA-II",   "5.32",  "10.20", "19.60", "25.69"],
            ["Stacked",     "NSGA-III",  "5.12",  "10.27", "19.77", "25.51"],
            ["L-Shape",     "Bayesian",  "5.60",  " 6.19", " 5.61", " 5.60"],
            ["L-Shape",     "NSGA-II",   "2.19",  " 5.74", "15.45", "22.53"],
            ["L-Shape",     "NSGA-III",  "2.19",  " 5.72", "15.51", "22.73"],
        ],
        col_widths=[2.8, 2.8, 2.4, 2.5, 2.5, 2.5]
    )
    caption(doc,
        "Table 2. MAE (°C) for all 48 training runs across 4 domains, 3 optimisers, 4 skip values. "
        "Green < 8 °C  |  Yellow 8–15 °C  |  Red > 15 °C."
    )

    img(doc,
        os.path.join(L8, "fig1_thermal_fields.png"),
        w_cm=15,
        cap=(
            "Figure 1. Level 8 — Predicted temperature fields on the z-midplane for all four "
            "3D domains at skip=1 (best NAS architecture per domain). "
            "Turbo colormap: blue = 20 °C, yellow = 540 °C."
        )
    )
    img(doc,
        os.path.join(L8, "fig8_3d_feasibility.png"),
        w_cm=15,
        cap=(
            "Figure 2. Level 8 — 3D feasibility: PINN prediction vs. FEM reference "
            "side-by-side for all four domains. We achieved MAE = 2.19 °C on L-Shape (NSGA-II, skip=1)."
        )
    )

    # ── Section 5: Level 9 Results (SA + Fourier) ──────────────────────────
    heading(doc, "5.  Results: Level 9 — SA-PINNs + Fourier Features (Best Result)")
    para(doc,
        "At Level 9 we combined all three contributions and ran experiments in both 2D and 3D "
        "using the architectures found by NAS. We trained each model for 30,000 Adam epochs. "
        "Our best 2D result (SA+Fourier, NSGA-II): L2 = 0.0137 — 9.2× better than FEM skip=1 "
        "(L2=0.126) — with inference at 0.01 s vs. 184 s for FEM (18,400× speedup). "
        "For 3D, we obtained L2 = 0.247 (Bayesian), which is weaker because we ran NAS in 2D; "
        "running NAS directly in 3D is our next step."
    )

    std_table(doc,
        headers=["Variant", "Optimizer", "Dim", "Best L2", "vs L5 ref", "Train Time", "Params"],
        rows=[
            ["SA+Fourier", "Bayesian",   "2D", "0.0253", "2.2×",  "482 s", "111,439"],
            ["SA+Fourier", "NSGA-II  ★", "2D", "0.0137", "4.0×",  "444 s",  "67,015"],
            ["SA+Fourier", "NSGA-III",   "2D", "0.0668", "0.8×",  "412 s",  "21,151"],
            ["SA+Fourier", "Bayesian",   "3D", "0.247",  "—",     "596 s", "111,439"],
            ["SA+Fourier", "NSGA-II",    "3D", "0.717",  "—",     "555 s",  "67,015"],
            ["SA-only",    "Bayesian",   "2D", "0.0151", "3.6×",  "404 s",  "92,564"],
            ["SA-only",    "NSGA-II",    "2D", "0.0397", "1.4×",  "378 s",  "47,890"],
            ["SA-only",    "NSGA-III",   "2D", "0.1789", "—",     "372 s",  "21,151"],
        ],
        col_widths=[2.8, 2.8, 1.2, 2.2, 2.0, 2.4, 2.4]
    )
    caption(doc,
        "Table 3. Level 9 results. ★ = best overall. L5 reference L2 = 0.055. "
        "3D results are weaker because NAS was performed in 2D — running NAS in 3D is the next step."
    )

    img(doc,
        os.path.join(L9, "fig1_2d_comparison.png"),
        w_cm=15,
        cap=(
            "Figure 3. Level 9 2D result (SA+Fourier, NSGA-II): exact temperature field (left), "
            "our PINN prediction (centre), and absolute error map (right). "
            "Largest errors near corners where boundary layer gradients are steepest."
        )
    )
    img(doc,
        os.path.join(L9, "fig2_3d_comparison.png"),
        w_cm=15,
        cap=(
            "Figure 4. Level 9 3D result (SA+Fourier, Bayesian): exact vs. PINN-predicted "
            "temperature on the z-midplane. We achieved L2 = 0.247 in 3D; the gap to our "
            "2D result (L2 = 0.014) shows that running NAS in 3D is the key next step."
        )
    )

    # ── Section 6: Conclusions ──────────────────────────────────────────────
    heading(doc, "6.  Conclusions")
    bullet(doc,
        "We achieved MAE = 2.19 °C on the L-Shape domain (skip=1, NSGA-II/III, 3D). "
        "All 3D domains achieve < 5.6 °C at skip=1."
    )
    bullet(doc,
        "We found that skip=2 is the practical optimum: 52% FEM savings while keeping "
        "MAE < 11 °C for all domains — we recommend this as the default setting."
    )
    bullet(doc,
        "Our best 2D result (Level 9, SA+Fourier, NSGA-II): L2 = 0.0137, "
        "9.2× better than FEM skip=1. We reduced inference time from 184 s to 0.01 s."
    )
    bullet(doc,
        "We added Fourier embedding to fix slow convergence in the high-gradient early phase "
        "(0–5 s). Without it, SA-only gives L2 = 0.0151 — Fourier pushes it further to 0.0137."
    )
    bullet(doc,
        "Our self-adaptive weights converged to λ_bc ≈ 19·λ_phys — we learned that "
        "satisfying the boundary and initial conditions matters far more than minimising "
        "the PDE residual at collocation points."
    )
    bullet(doc,
        "We found NSGA-II gives the best trade-off (3 layers × 153 neurons, 67 K params) — "
        "it outperformed the larger Bayesian solution (111 K params) in accuracy."
    )
    bullet(doc,
        "Open problem: our 3D results are weaker (L2 ≈ 0.25) because we ran NAS in 2D. "
        "We plan to run NAS directly in 3D as the most impactful next step."
    )

    # ── References ──────────────────────────────────────────────────────────
    heading(doc, "References")
    refs = [
        ("[1]", "M. Raissi, P. Perdikaris, G.E. Karniadakis, \"Physics-informed neural networks,\" "
                "J. Comput. Phys., vol. 378, 2019. DOI: 10.1016/j.jcp.2018.10.045"),
        ("[2]", "D. Mortensen, G. Noorsumar, H.G. Fjaer, R. Babaei, P.E. Dronen, \"Mitigating "
                "distortions in cast automotive subframes: A FEM simulation approach,\" "
                "Int J Adv Manuf Technol, 2026. DOI: 10.1007/s00170-026-17515-w"),
        ("[3]", "M. Tancik et al., \"Fourier Features Let Networks Learn High Frequency Functions,\" "
                "NeurIPS, 2020."),
        ("[4]", "S. Wang, S. Sankaran, P. Perdikaris, \"Respecting Causality for Training PINNs,\" "
                "Comput. Methods Appl. Mech. Eng., vol. 421, 2024. DOI: 10.1016/j.cma.2024.116813"),
        ("[5]", "K. Deb et al., \"NSGA-II,\" IEEE Trans. Evol. Comput., vol. 6, 2002."),
        ("[6]", "K. Deb & H. Jain, \"NSGA-III,\" IEEE Trans. Evol. Comput., vol. 18, 2014."),
        ("[7]", "J. Snoek, H. Larochelle, R.P. Adams, \"Practical Bayesian Optimization,\" NeurIPS, 2012."),
        ("[8]", "I.E. Lagaris et al., \"ANNs for solving ODEs and PDEs,\" IEEE Trans. Neural Netw., 1998."),
    ]
    for num, text in refs:
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(1)
        p.paragraph_format.space_after  = Pt(3)
        p.paragraph_format.left_indent  = Cm(0.7)
        p.paragraph_format.first_line_indent = Cm(-0.7)
        r = p.add_run(num + " ")
        r.bold = True; r.font.name = "Times New Roman"; r.font.size = Pt(9.5)
        r2 = p.add_run(text)
        r2.font.name = "Times New Roman"; r2.font.size = Pt(9.5)

    # ── Save ────────────────────────────────────────────────────────────────
    doc.save(OUT)
    size_mb = os.path.getsize(OUT) / 1024**2
    print(f"Saved: {OUT}  ({size_mb:.1f} MB)")


if __name__ == "__main__":
    build()
