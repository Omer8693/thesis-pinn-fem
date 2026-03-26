"""
generate_word.py
Generates a professional Word (.docx) report for the NAS-MCO-PINNs master's thesis project.
"""

import os
from docx import Document
from docx.shared import Pt, Cm, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
import copy

# ---------------------------------------------------------------------------
# PATHS
# ---------------------------------------------------------------------------
BASE  = os.path.dirname(os.path.abspath(__file__))
ROOT  = os.path.normpath(os.path.join(BASE, "..", ".."))
PLOTS = os.path.join(ROOT, "level9_sa_fourier", "results", "plots")
L8    = os.path.join(ROOT, "level8_nas_mco_pinn", "results")
OUT   = os.path.join(BASE, "NAS_PINNS3_professor_brief.docx")

# ---------------------------------------------------------------------------
# COLOR CONSTANTS
# ---------------------------------------------------------------------------
NAVY       = RGBColor(0x1a, 0x23, 0x7e)
DARK_GRAY  = RGBColor(0x33, 0x33, 0x33)
WHITE      = RGBColor(0xFF, 0xFF, 0xFF)
LIGHT_BLUE = "D6E4F0"   # for alternating table rows (hex string, no #)
TABLE_NAV  = "1a237e"   # navy for header (hex string, no #)
GRAY_BG    = "F2F2F2"   # equation box background

# ---------------------------------------------------------------------------
# LOW-LEVEL XML HELPERS
# ---------------------------------------------------------------------------

def set_cell_bg(cell, hex_color):
    """Set background fill color of a table cell."""
    tc   = cell._tc
    tcPr = tc.get_or_add_tcPr()
    shd  = OxmlElement("w:shd")
    shd.set(qn("w:val"),   "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"),  hex_color)
    tcPr.append(shd)


def set_para_shading(para, hex_color):
    """Set background shading on a whole paragraph."""
    pPr  = para._p.get_or_add_pPr()
    shd  = OxmlElement("w:shd")
    shd.set(qn("w:val"),   "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"),  hex_color)
    pPr.append(shd)


def set_cell_borders(table):
    """Add thin borders to every cell in a table."""
    for row in table.rows:
        for cell in row.cells:
            tc   = cell._tc
            tcPr = tc.get_or_add_tcPr()
            tcBorders = OxmlElement("w:tcBorders")
            for side in ("top", "left", "bottom", "right", "insideH", "insideV"):
                border = OxmlElement(f"w:{side}")
                border.set(qn("w:val"),   "single")
                border.set(qn("w:sz"),    "4")
                border.set(qn("w:space"), "0")
                border.set(qn("w:color"), "AAAAAA")
                tcBorders.append(border)
            tcPr.append(tcBorders)


# ---------------------------------------------------------------------------
# DOCUMENT SETUP
# ---------------------------------------------------------------------------

def create_document():
    doc = Document()

    # Page size A4
    section = doc.sections[0]
    section.page_width  = Cm(21.0)
    section.page_height = Cm(29.7)

    # Margins 2.54 cm (1 inch)
    for attr in ("top_margin", "bottom_margin", "left_margin", "right_margin"):
        setattr(section, attr, Cm(2.54))

    # Default body style: Times New Roman 11pt
    style = doc.styles["Normal"]
    font  = style.font
    font.name = "Times New Roman"
    font.size = Pt(11)

    return doc


# ---------------------------------------------------------------------------
# HELPER FUNCTIONS
# ---------------------------------------------------------------------------

def add_heading(doc, text, level=1):
    """Add a heading with custom formatting."""
    para = doc.add_paragraph()
    run  = para.add_run(text)
    run.bold = True

    if level == 1:
        run.font.name  = "Times New Roman"
        run.font.size  = Pt(12)
        run.font.color.rgb = NAVY
        para.paragraph_format.space_before = Pt(14)
        para.paragraph_format.space_after  = Pt(6)
    else:
        run.font.name  = "Times New Roman"
        run.font.size  = Pt(11)
        run.font.color.rgb = DARK_GRAY
        para.paragraph_format.space_before = Pt(10)
        para.paragraph_format.space_after  = Pt(4)

    return para


def add_para(doc, text, bold_prefix=None, indent=False):
    """Add a paragraph. If bold_prefix provided, first part is bold."""
    para = doc.add_paragraph()
    para.paragraph_format.space_before = Pt(2)
    para.paragraph_format.space_after  = Pt(6)
    if indent:
        para.paragraph_format.left_indent = Cm(1.0)

    if bold_prefix:
        br = para.add_run(bold_prefix + " ")
        br.bold            = True
        br.font.name       = "Times New Roman"
        br.font.size       = Pt(11)
        run = para.add_run(text)
        run.font.name = "Times New Roman"
        run.font.size = Pt(11)
    else:
        run = para.add_run(text)
        run.font.name = "Times New Roman"
        run.font.size = Pt(11)

    return para


def add_image(doc, path, width_cm=14, caption=None):
    """Add image if file exists, skip silently if not. Add caption below."""
    if not os.path.isfile(path):
        return
    try:
        para = doc.add_paragraph()
        para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        para.paragraph_format.space_before = Pt(6)
        para.paragraph_format.space_after  = Pt(2)
        run = para.add_run()
        run.add_picture(path, width=Cm(width_cm))
    except Exception:
        return

    if caption:
        cap = doc.add_paragraph(caption)
        cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
        cap.paragraph_format.space_before = Pt(2)
        cap.paragraph_format.space_after  = Pt(10)
        for run in cap.runs:
            run.font.name  = "Times New Roman"
            run.font.size  = Pt(10)
            run.font.italic = True


def add_table(doc, headers, rows, col_widths=None):
    """Add a formatted table with navy header row and alternating row shading."""
    tbl = doc.add_table(rows=1 + len(rows), cols=len(headers))
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    tbl.style     = "Table Grid"

    # Header row
    hdr_row = tbl.rows[0]
    for i, h in enumerate(headers):
        cell = hdr_row.cells[i]
        set_cell_bg(cell, TABLE_NAV)
        cell.paragraphs[0].clear()
        run = cell.paragraphs[0].add_run(h)
        run.bold            = True
        run.font.color.rgb  = WHITE
        run.font.name       = "Times New Roman"
        run.font.size       = Pt(10)
        cell.paragraphs[0].paragraph_format.space_before = Pt(2)
        cell.paragraphs[0].paragraph_format.space_after  = Pt(2)

    # Data rows with alternating shading
    for ri, row_data in enumerate(rows):
        row = tbl.rows[ri + 1]
        bg  = LIGHT_BLUE if ri % 2 == 0 else "FFFFFF"
        for ci, val in enumerate(row_data):
            cell = row.cells[ci]
            set_cell_bg(cell, bg)
            cell.paragraphs[0].clear()
            run = cell.paragraphs[0].add_run(str(val))
            run.font.name = "Times New Roman"
            run.font.size = Pt(10)
            cell.paragraphs[0].paragraph_format.space_before = Pt(2)
            cell.paragraphs[0].paragraph_format.space_after  = Pt(2)

    # Column widths
    if col_widths:
        for i, w in enumerate(col_widths):
            for row in tbl.rows:
                row.cells[i].width = Cm(w)

    set_cell_borders(tbl)

    # Spacing after table
    doc.add_paragraph().paragraph_format.space_after = Pt(6)
    return tbl


def add_equation(doc, eq_text, note=None):
    """Add equation in a gray shaded box paragraph, with optional note below."""
    para = doc.add_paragraph()
    para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    para.paragraph_format.space_before = Pt(6)
    para.paragraph_format.space_after  = Pt(2)
    para.paragraph_format.left_indent  = Cm(1.5)
    para.paragraph_format.right_indent = Cm(1.5)
    set_para_shading(para, GRAY_BG)

    run = para.add_run(eq_text)
    run.font.name = "Courier New"
    run.font.size = Pt(11)
    run.bold      = True

    if note:
        np_ = doc.add_paragraph()
        np_.paragraph_format.space_before = Pt(2)
        np_.paragraph_format.space_after  = Pt(8)
        np_.paragraph_format.left_indent  = Cm(1.5)
        nr = np_.add_run(note)
        nr.font.name   = "Times New Roman"
        nr.font.size   = Pt(10)
        nr.font.italic = True

    return para


def add_horizontal_rule(doc):
    """Add a simple horizontal line using a bottom-border paragraph."""
    para = doc.add_paragraph()
    para.paragraph_format.space_before = Pt(4)
    para.paragraph_format.space_after  = Pt(4)
    pPr      = para._p.get_or_add_pPr()
    pBdr     = OxmlElement("w:pBdr")
    bottom   = OxmlElement("w:bottom")
    bottom.set(qn("w:val"),   "single")
    bottom.set(qn("w:sz"),    "6")
    bottom.set(qn("w:space"), "1")
    bottom.set(qn("w:color"), "1a237e")
    pBdr.append(bottom)
    pPr.append(pBdr)


def add_bullet(doc, text):
    """Add a bullet point paragraph."""
    para = doc.add_paragraph(style="List Bullet")
    run  = para.add_run(text)
    run.font.name = "Times New Roman"
    run.font.size = Pt(11)
    para.paragraph_format.space_before = Pt(2)
    para.paragraph_format.space_after  = Pt(4)


# ---------------------------------------------------------------------------
# MAIN DOCUMENT BUILD
# ---------------------------------------------------------------------------

def build_document():
    doc = create_document()

    # ========================================================================
    # TITLE BLOCK
    # ========================================================================
    title_para = doc.add_paragraph()
    title_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title_para.paragraph_format.space_before = Pt(12)
    title_para.paragraph_format.space_after  = Pt(6)
    tr = title_para.add_run(
        "NAS-MCO-PINNs: Neural Architecture Search with Multi-Loss Consistency "
        "Optimization for Physics-Informed Neural Networks in Industrial Thermal Simulation"
    )
    tr.bold            = True
    tr.font.name       = "Times New Roman"
    tr.font.size       = Pt(14)
    tr.font.color.rgb  = NAVY

    auth = doc.add_paragraph()
    auth.alignment = WD_ALIGN_PARAGRAPH.CENTER
    auth.paragraph_format.space_before = Pt(4)
    auth.paragraph_format.space_after  = Pt(2)
    ar = auth.add_run("IKT590-G 26V — Master's Thesis Project Report")
    ar.font.name = "Times New Roman"
    ar.font.size = Pt(11)

    date_p = doc.add_paragraph()
    date_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    date_p.paragraph_format.space_before = Pt(2)
    date_p.paragraph_format.space_after  = Pt(8)
    dr = date_p.add_run("March 2026")
    dr.font.name = "Times New Roman"
    dr.font.size = Pt(11)

    add_horizontal_rule(doc)

    # ========================================================================
    # ABSTRACT
    # ========================================================================
    add_heading(doc, "Abstract", level=1)
    add_para(doc,
        "This report presents a nine-level progressive framework for replacing Finite Element "
        "Method (FEM) time steps with Physics-Informed Neural Networks (PINNs) in transient "
        "thermal simulation of A356 aluminum quenching. We designed a temporal skip operator "
        "that allows a single PINN to predict multiple FEM steps ahead, reducing FEM calls by "
        "up to 81%. We extended the framework with Fourier feature embedding and self-adaptive "
        "loss weights, achieving a final L2 error of 0.014 — 9.2 times better than the FEM skip "
        "baseline — with inference time of approximately 0.01 seconds compared to 184 seconds "
        "for FEM. All FEM reference data was taken from [Mortensen et al., 2026]."
    )

    # ========================================================================
    # SECTION 1: INTRODUCTION
    # ========================================================================
    add_heading(doc, "1. Introduction and Motivation", level=1)
    add_para(doc,
        "Water quenching is a critical step in manufacturing automotive subframes from A356 "
        "aluminum alloy. When the hot casting is plunged into cold water, the rapid and "
        "non-uniform cooling creates residual stresses that eventually lead to part distortion. "
        "Engineers currently use Finite Element Method (FEM) simulations to predict these "
        "stresses, but each simulation requires running 21 time steps at roughly 8.8 seconds "
        "each — about 184 seconds total. This is too slow to use during design optimization, "
        "where thousands of parameter combinations need to be evaluated."
    )
    add_para(doc,
        "We investigated whether Physics-Informed Neural Networks could replace FEM as a faster "
        "predictor. The idea is to train a neural network once (which takes 400–600 seconds) and "
        "then use it to predict the full temperature field in about 0.01 seconds per query — an "
        "18,400-fold speedup at inference."
    )
    add_para(doc,
        "Our framework grew to nine levels over the course of the project, each adding a new "
        "capability. The first few levels established a baseline. Later levels introduced the "
        "temporal skip operator (our own design), then Fourier feature embedding and self-adaptive "
        "loss weights borrowed and adapted from recent PINN literature. The final Level 9 model "
        "achieves L2 = 0.014 on the 2D quenching problem."
    )

    # ========================================================================
    # SECTION 2: PHYSICAL PROBLEM AND FEM REFERENCE
    # ========================================================================
    add_heading(doc, "2. Physical Problem and FEM Reference Model", level=1)

    add_heading(doc, "2.1 Governing Equations", level=2)
    add_para(doc,
        "The physical problem is transient heat conduction during water quenching. "
        "The governing partial differential equation is:"
    )
    add_equation(doc,
        "rho * cp * dT/dt  =  k * nabla^2 T",
        note="Heat equation. rho=2670 kg/m^3, cp=963 J/(kg*K), k=151 W/(m*K) for A356 aluminum."
    )
    add_para(doc,
        "On the wetted boundary surface, we apply a Robin (convective) boundary condition:"
    )
    add_equation(doc,
        "-k * dT/dn  =  h(T) * (T - T_water)",
        note="Newton's law of cooling. h = 5000 W/(m^2*K), T_water = 20 degrees C."
    )
    add_para(doc,
        "The initial condition is T(x,y,0) = 540°C (exit temperature from Solution Heat "
        "Treatment). The 2D domain is a rectangular cross-section of 1.3 m × 0.6 m, simulated "
        "over 30 seconds with 21 equally-spaced time steps."
    )

    add_heading(doc, "2.2 FEM Reference Model — [Mortensen et al., 2026]", level=2)
    add_para(doc,
        "All FEM baseline data comes from the paper: Mortensen et al. (2026), 'Mitigating "
        "distortions in cast automotive subframes: A finite element simulation approach,' "
        "International Journal of Advanced Manufacturing Technology, "
        "DOI: 10.1007/s00170-026-17515-w.",
        bold_prefix="We did not implement FEM ourselves."
    )
    add_para(doc,
        "From this paper we extracted three types of data that we used as ground truth:\n"
        "(a) Material parameters for A356 aluminum (Table 1 of Mortensen et al.): flow stress F, "
        "strain hardening exponent n, and strain-rate sensitivity m as functions of temperature. "
        "These were used to build our material interpolation module.\n"
        "(b) Heat transfer coefficient curve h(T) (Figure 6 of Mortensen et al.): showing the "
        "transition between film boiling, nucleate boiling, and forced convection as the surface "
        "temperature drops from 540°C to 20°C. We implemented a piecewise model that approximates "
        "this curve.\n"
        "(c) Reference temperature histories (Figures 7, 15–17 of Mortensen et al.): used as "
        "ground truth to compute L2 error and MAE for all our models.\n\n"
        "The FEM simulation runs for 21 time steps totaling 184 seconds on our hardware."
    )

    add_table(doc,
        headers=["Property", "Value", "Unit", "Source"],
        rows=[
            ["Density (rho)",              "2670",  "kg/m^3",      "Table 1"],
            ["Specific heat (cp)",          "963",   "J/(kg*K)",    "Table 1"],
            ["Thermal conductivity (k)",    "151",   "W/(m*K)",     "Table 1"],
            ["Initial temperature (T_0)",   "540",   "deg C",       "Table 1"],
            ["Water temperature (T_inf)",   "20",    "deg C",       "Table 1"],
            ["Convection coefficient (h)",  "5000",  "W/(m^2*K)",   "Fig. 6"],
            ["Coherency temperature",       "540",   "deg C",       "Table 1"],
        ],
        col_widths=[5.5, 2.5, 3.0, 2.5]
    )
    cap = doc.add_paragraph(
        "Table 1. A356 Key Material Parameters (Source: Table 1, Mortensen et al. 2026)"
    )
    cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for r in cap.runs:
        r.font.name   = "Times New Roman"
        r.font.size   = Pt(10)
        r.font.italic = True
    cap.paragraph_format.space_after = Pt(8)

    # ========================================================================
    # SECTION 3: METHODS
    # ========================================================================
    add_heading(doc, "3. Methods", level=1)

    # 3.1 Temporal Skip Operator
    add_heading(doc, "3.1 Temporal Skip Operator — Our Own Design", level=2)
    add_para(doc,
        "The standard approach to training PINNs for time-dependent problems is to train one "
        "network per FEM time step, which requires 21 separate training runs for our problem. "
        "We designed a different approach: a single network that predicts s time steps ahead from "
        "any given initial condition."
    )
    add_para(doc,
        "Why we designed this: Rather than following each FEM step individually, we wanted to "
        "learn the mapping from an initial state to a future state s steps later. This reduces "
        "the number of training runs from 21 to ceil(21/s)."
    )
    add_para(doc, "The key formula we designed is:")
    add_equation(doc,
        "T_hat(t + s*dt)  =  T_IC  +  tau * f_theta(x, y, tau, T_IC)",
        note=(
            "tau = t / (s*dt) in [0, 1] is the normalized time. "
            "T_IC is the initial condition at the start of the window."
        )
    )
    add_para(doc,
        "Why this specific form: We chose to write the prediction as T_IC plus a learned "
        "correction, so that at tau = 0 the output exactly equals the initial condition T_IC, "
        "without needing an explicit initial condition loss term. This guarantees physical "
        "consistency at the start of each window. The idea of using this kind of IC-satisfying "
        "residual form is inspired by early work on neural network solutions to differential "
        "equations [Lagaris et al., 1998], but the temporal skip operator itself — applying it "
        "to predict multiple time steps ahead for a quenching simulation — is our own contribution."
    )
    add_para(doc,
        "We found an interesting result: skip=2 gives lower error than skip=1. This is because "
        "with skip=1, any small FEM numerical error accumulates step by step, while with skip=2 "
        "the PINN smooths out these small oscillations."
    )

    add_table(doc,
        headers=["Skip s", "FEM Calls", "FEM Steps Saved", "L2 Error", "MAE (deg C)", "Runtime"],
        rows=[
            ["1 (baseline)",      "21", "0 (0%)",   "0.126", "43.6", "184s"],
            ["2 (recommended)",   "11", "10 (48%)", "0.108", "33.2", "91s"],
            ["4",                  "6", "15 (71%)", "0.204", "57.5", "46s"],
            ["6",                  "4", "17 (81%)", "0.294", "93.6", "28s"],
        ],
        col_widths=[3.0, 2.5, 3.5, 2.5, 2.8, 2.2]
    )
    cap2 = doc.add_paragraph(
        "Table 2. Skip Operator Results (Level 2, Bayesian architecture)."
    )
    cap2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for r in cap2.runs:
        r.font.name   = "Times New Roman"
        r.font.size   = Pt(10)
        r.font.italic = True
    cap2.paragraph_format.space_after = Pt(8)

    # 3.2 Fourier Feature Embedding
    add_heading(doc, "3.2 Fourier Feature Embedding — Adopted from [Tancik et al., 2020]", level=2)
    add_para(doc,
        "When we tried training a standard PINN on the quenching problem, we noticed that the "
        "network learned the slow late-cooling behavior well but was much slower to learn the "
        "rapid early cooling (where temperature drops from 540°C to around 300°C in the first "
        "5 seconds). This is a known problem called 'spectral bias' [Rahaman et al., 2019]: "
        "standard multi-layer perceptrons learn low-frequency functions first and take much "
        "longer to capture high-frequency components."
    )
    add_para(doc,
        "To address this, we adopted the Fourier feature embedding technique from Tancik et al. "
        "(2020). Before passing the input coordinates (t, x, y) to the MLP, we project them "
        "through a random Fourier mapping:"
    )
    add_equation(doc,
        "gamma(v)  =  [ sin(2*pi*B*v),  cos(2*pi*B*v) ]",
        note=(
            "B in R^(d x F) with entries drawn from N(0, sigma^2). Frozen (not trained). "
            "Doubles the input dimension: d=3 inputs -> 128-dim encoding (n_fourier=64)."
        )
    )
    add_para(doc,
        "We implemented the FourierEmbedding class from scratch "
        "(in level9_sa_fourier/src/fourier_pinn.py), following the formulation in Tancik et al. "
        "(2020). We set n_fourier=64 and sigma=1.0, which gives a 128-dimensional input to the "
        "MLP. The matrix B is sampled once at initialization and frozen during training — only "
        "the MLP weights are optimized."
    )

    # 3.3 Self-Adaptive Loss Weights
    add_heading(doc, "3.3 Self-Adaptive Loss Weights — Adopted from [Wang et al., 2022]", level=2)
    add_para(doc, "A PINN has three loss terms that must all be minimized jointly:")
    add_equation(doc,
        "L  =  lambda_phys * L_phys  +  lambda_bc * L_bc  +  lambda_ic * L_ic",
        note="Three terms: physics residual (PDE), boundary condition (Robin BC), initial condition."
    )
    add_para(doc,
        "The problem is that these three terms have very different natural scales. In our "
        "quenching problem, the PDE residual is on the order of 4x10^7 while the IC residual "
        "is only around 520. With fixed weights lambda = (1, 10, 10), the training often focuses "
        "too much on whichever term happens to dominate, especially in early training."
    )
    add_para(doc,
        "We adopted the self-adaptive weight approach from Wang et al. (2022): instead of fixing "
        "lambda, we make the weights learnable parameters:"
    )
    add_equation(doc,
        "lambda  =  softplus(w)  =  log(1 + exp(w))",
        note="w is a scalar parameter trained jointly with the network. softplus ensures lambda > 0 always."
    )
    add_para(doc,
        "We implemented the SelfAdaptiveWeights module (in level9_sa_fourier/src/sa_loss.py). "
        "The initial values match our previous fixed weights: lambda_phys = 1.0, lambda_bc = 10.0, "
        "lambda_ic = 10.0. During training, these adjust automatically."
    )
    add_para(doc,
        "The final learned weights for our best model (NSGA-II, SA+Fourier) were: "
        "lambda_phys approx 0.48, lambda_bc approx 9.28, lambda_ic approx 9.28. The boundary and "
        "IC terms get roughly 19 times more weight than the physics term. This makes physical sense: "
        "satisfying the initial condition and boundary condition precisely is more important for "
        "accuracy than perfectly minimizing the PDE residual at every collocation point."
    )

    # ========================================================================
    # SECTION 4: NAS
    # ========================================================================
    add_heading(doc, "4. Neural Architecture Search", level=1)
    add_para(doc,
        "We used Neural Architecture Search (NAS) to find the best network architecture for each "
        "level. The search space covers layers 3–6, neurons per layer 64–160, and activations "
        "{Tanh, GELU, SiLU, ReLU}. We evaluated three NAS strategies:"
    )
    add_bullet(doc,
        "Bayesian Optimization [Snoek et al., 2012] (via scikit-optimize): single-objective, "
        "minimizes L2. Best for problems where the landscape is smooth. Uses a Gaussian Process "
        "surrogate model."
    )
    add_bullet(doc,
        "NSGA-II [Deb et al., 2002] (via pymoo): multi-objective evolutionary algorithm, minimizes "
        "both L2 error and number of parameters simultaneously. Finds compact architectures that "
        "generalize well."
    )
    add_bullet(doc,
        "NSGA-III [Deb and Jain, 2014] (via pymoo): extension of NSGA-II with structured "
        "reference-point directions. Tends to find very compact architectures at the cost of "
        "slightly higher error."
    )
    add_para(doc,
        "Each optimizer evaluated 500 candidate architectures. The best architecture from NAS "
        "was then used for full training in each level."
    )

    # ========================================================================
    # SECTION 5: RESULTS
    # ========================================================================
    add_heading(doc, "5. Results", level=1)

    add_heading(doc, "5.1 Nine-Level Progression", level=2)
    add_para(doc,
        "Table 3 shows how the framework improved level by level. Each level built on the previous "
        "one by adding one new capability."
    )
    add_table(doc,
        headers=["Level", "Focus", "Best L2", "Best MAE", "Key Addition"],
        rows=[
            ["L1",    "Single-shot 2D",       "0.076",        "39.1 deg C",  "Baseline PINN + NAS"],
            ["L2",    "Temporal Skip",         "0.108 (s=2)",  "33.2 deg C",  "Skip operator — 48% FEM reduction"],
            ["L3",    "Hybrid FEM+PINN",       "~0.12",        "—",           "Adaptive threshold routing"],
            ["L4",    "Distortion",            "—",            "14.4 deg C",  "Mechanical coupling (plane stress)"],
            ["L5",    "L-BFGS Refine",         "0.030",        "14.4 deg C",  "Adam -> L-BFGS two-stage training"],
            ["L6",    "Poisson Bench.",        "~0.018",       "—",           "Generalization to Poisson PDE"],
            ["L7A",   "Temporal Analysis",     "~0.025",       "—",           "Time-skip regime study"],
            ["L7B",   "Multi-Domain",          "~0.022",       "—",           "5 geometry types"],
            ["L8",    "3D MCO-PINNs",          "—",            "2.19 deg C",  "3D + MCO adaptive weights, 48 runs"],
            ["L9 *",  "SA + Fourier",          "0.0137",       "—",           "Learnable weights + Fourier features"],
        ],
        col_widths=[1.5, 3.5, 2.5, 2.5, 4.0]
    )
    cap3 = doc.add_paragraph("Table 3. Nine-level progression of the NAS-PINNs framework.")
    cap3.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for r in cap3.runs:
        r.font.name   = "Times New Roman"
        r.font.size   = Pt(10)
        r.font.italic = True
    cap3.paragraph_format.space_after = Pt(8)

    # 5.2 Level 8
    add_heading(doc, "5.2 Level 8 — 3D Multi-Geometry Results", level=2)
    add_para(doc,
        "Level 8 extended the framework to four 3D domain shapes: Rectangular Prism, Cylinder, "
        "Stacked Cubes, and L-Shape. We ran 48 experiments (4 domains x 3 NAS optimizers x 4 "
        "skip values). The best result was MAE = 2.19 deg C on the L-Shape domain with NSGA-II/III "
        "at skip=1."
    )
    add_image(doc,
        os.path.join(L8, "fig4_summary_table.png"),
        width_cm=14,
        caption=(
            "Figure 1. Level 8 results summary: MAE (deg C) for all 48 runs across 4 domains, "
            "3 optimizers, and 4 skip values."
        )
    )
    add_image(doc,
        os.path.join(L8, "fig1_thermal_fields.png"),
        width_cm=14,
        caption=(
            "Figure 2. Level 8 predicted temperature fields on the z-midplane for all four "
            "3D domains."
        )
    )

    # 5.3 Level 9
    add_heading(doc, "5.3 Level 9 — SA-PINNs + Fourier Features (Best Results)", level=2)
    add_para(doc,
        "Level 9 is our best result. We combined self-adaptive loss weights and Fourier feature "
        "embedding with the NAS-found architecture."
    )
    add_table(doc,
        headers=["Variant", "Optimizer", "Dim", "Best L2", "Train Time", "Params"],
        rows=[
            ["SA+Fourier", "Bayesian",  "2D", "0.0253",  "482s", "111,439"],
            ["SA+Fourier", "NSGA-II *", "2D", "0.0137",  "444s",  "67,015"],
            ["SA+Fourier", "NSGA-III",  "2D", "0.0668",  "412s",  "21,151"],
            ["SA+Fourier", "Bayesian",  "3D", "0.247",   "596s", "111,439"],
            ["SA+Fourier", "NSGA-II",   "3D", "0.717",   "555s",  "67,015"],
            ["SA-only",    "Bayesian",  "2D", "0.0151",  "404s",  "92,564"],
            ["SA-only",    "NSGA-II",   "2D", "0.0397",  "378s",  "47,890"],
            ["SA-only",    "NSGA-III",  "2D", "0.1789",  "372s",  "21,151"],
        ],
        col_widths=[3.0, 3.0, 1.5, 2.5, 2.5, 2.5]
    )
    cap4 = doc.add_paragraph("Table 4. Level 9 results for all SA variant, optimizer, and dimension combinations.")
    cap4.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for r in cap4.runs:
        r.font.name   = "Times New Roman"
        r.font.size   = Pt(10)
        r.font.italic = True
    cap4.paragraph_format.space_after = Pt(8)

    add_para(doc,
        "* Best result: SA+Fourier with NSGA-II achieves L2 = 0.0137 in 2D — 4 times better "
        "than the Level 5 reference (L2 = 0.055) and 9.2 times better than the FEM skip=1 "
        "baseline (L2 = 0.126). After training, inference takes approximately 0.01 seconds "
        "per query."
    )
    add_para(doc,
        "The 3D results are much weaker (L2 = 0.247 for Bayesian, L2 > 0.7 for NSGA-II/III). "
        "The reason is that our NAS was performed in 2D, and the resulting architectures are not "
        "large enough to handle the additional complexity of 3D. Running NAS directly in 3D is "
        "the most important next step."
    )
    add_image(doc,
        os.path.join(PLOTS, "fig1_2d_comparison.png"),
        width_cm=14,
        caption="Figure 3. Level 9: Exact vs. predicted temperature field (2D, SA+Fourier, NSGA-II)."
    )
    add_image(doc,
        os.path.join(PLOTS, "fig4_sa_weights.png"),
        width_cm=14,
        caption=(
            "Figure 4. Level 9: Evolution of self-adaptive weights lambda_phys, lambda_bc, "
            "lambda_ic during training."
        )
    )

    # 5.4 FEM vs PINN
    add_heading(doc, "5.4 FEM vs. PINN Comparison", level=2)
    add_table(doc,
        headers=["Method", "L2 Error", "FEM Steps", "Runtime", "FEM at Inference?"],
        rows=[
            ["FEM full run",                   "Reference", "21/21",  "184s/run",               "Yes"],
            ["PINN skip=1 (L2)",               "0.126",     "21/21",  "184s/run",               "Yes"],
            ["PINN skip=2 (L2)",               "0.108",     "11/21",  "91s/run",                "Yes"],
            ["L5 PINN (Bayesian)",             "0.030",     "0/21",   "240s train",             "No"],
            ["L9 SA+Fourier (NSGA-II) *",      "0.014",     "0/21",   "444s train + 0.01s/query", "No"],
        ],
        col_widths=[4.5, 2.5, 2.5, 3.8, 3.2]
    )
    cap5 = doc.add_paragraph("Table 5. FEM vs. PINN comparison across all levels and methods.")
    cap5.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for r in cap5.runs:
        r.font.name   = "Times New Roman"
        r.font.size   = Pt(10)
        r.font.italic = True
    cap5.paragraph_format.space_after = Pt(8)

    add_image(doc,
        os.path.join(PLOTS, "fem_pinn_summary_table.png"),
        width_cm=14,
        caption="Figure 5. FEM vs. PINN comparison across all levels and methods."
    )

    # ========================================================================
    # SECTION 6: CONCLUSIONS
    # ========================================================================
    add_heading(doc, "6. Conclusions", level=1)
    add_bullet(doc,
        "The temporal skip operator at s=2 reduces FEM calls by 48% while actually improving "
        "accuracy compared to s=1. This counterintuitive result occurs because the PINN avoids "
        "step-by-step numerical error accumulation."
    )
    add_bullet(doc,
        "Fourier feature embedding is important for capturing the rapid early-stage cooling "
        "signal. Without it, standard MLPs suffer from spectral bias and converge slowly."
    )
    add_bullet(doc,
        "Self-adaptive loss weights converge to lambda_bc approx 19 * lambda_phys, meaning the "
        "optimizer automatically assigns much more importance to satisfying boundary and initial "
        "conditions than the PDE residual."
    )
    add_bullet(doc,
        "NSGA-II finds the best trade-off between accuracy and parameter count in 2D. Its "
        "architecture (3 layers x 153 neurons, 67K params) generalizes better than the larger "
        "Bayesian architecture (111K params)."
    )
    add_bullet(doc,
        "The 3D gap is the main open problem: the NAS was done in 2D and the found architectures "
        "do not transfer well to 3D. The most impactful next step is to run NAS in 3D directly."
    )
    add_bullet(doc,
        "The best overall result is L2 = 0.014 (SA+Fourier, NSGA-II, 2D), which is 9.2 times "
        "better than the FEM skip baseline and takes only 0.01 seconds per inference after a "
        "one-time training of 444 seconds."
    )

    # ========================================================================
    # SECTION 7: REFERENCES
    # ========================================================================
    add_heading(doc, "7. References", level=1)

    refs = [
        (
            "[1]",
            "M. Raissi, P. Perdikaris, G.E. Karniadakis, \"Physics-informed neural networks: "
            "A deep learning framework for solving forward and inverse problems involving "
            "nonlinear partial differential equations,\" Journal of Computational Physics, "
            "vol. 378, pp. 686–707, 2019. DOI: 10.1016/j.jcp.2018.10.045"
        ),
        (
            "[2]",
            "D. Mortensen, G. Noorsumar, H.G. Fjaer, R. Babaei, P.E. Dronen, \"Mitigating "
            "distortions in cast automotive subframes: A finite element simulation approach,\" "
            "International Journal of Advanced Manufacturing Technology, 2026. "
            "DOI: 10.1007/s00170-026-17515-w"
        ),
        (
            "[3]",
            "M. Tancik, P. Srinivasan, B. Mildenhall, S. Fridovich-Keil, N. Raghavan, "
            "U. Singhal, R. Ramamoorthi, J. Barron, R. Ng, \"Fourier Features Let Networks "
            "Learn High Frequency Functions in Low Dimensional Domains,\" Advances in Neural "
            "Information Processing Systems (NeurIPS), vol. 33, pp. 7537–7547, 2020."
        ),
        (
            "[4]",
            "S. Wang, Y. Teng, P. Perdikaris, \"Understanding and Mitigating Gradient Flow "
            "Pathologies in Physics-Informed Neural Networks,\" SIAM Journal on Scientific "
            "Computing, vol. 43, no. 5, pp. A3055–A3081, 2021. DOI: 10.1137/20M1318043"
        ),
        (
            "[5]",
            "S. Wang, S. Sankaran, P. Perdikaris, \"Respecting Causality for Training "
            "Physics-Informed Neural Networks,\" Computer Methods in Applied Mechanics and "
            "Engineering, vol. 421, 2024. DOI: 10.1016/j.cma.2024.116813"
        ),
        (
            "[6]",
            "K. Deb, A. Pratap, S. Agarwal, T. Meyarivan, \"A fast and elitist multiobjective "
            "genetic algorithm: NSGA-II,\" IEEE Transactions on Evolutionary Computation, "
            "vol. 6, no. 2, pp. 182–197, 2002. DOI: 10.1109/4235.996017"
        ),
        (
            "[7]",
            "K. Deb, H. Jain, \"An evolutionary many-objective optimization algorithm using "
            "reference-point based nondominated sorting approach, Part I,\" IEEE Transactions "
            "on Evolutionary Computation, vol. 18, no. 4, pp. 577–601, 2014. "
            "DOI: 10.1109/TEVC.2013.2281535"
        ),
        (
            "[8]",
            "J. Snoek, H. Larochelle, R.P. Adams, \"Practical Bayesian Optimization of Machine "
            "Learning Algorithms,\" Advances in Neural Information Processing Systems (NeurIPS), "
            "vol. 25, pp. 2951–2959, 2012."
        ),
        (
            "[9]",
            "X. Glorot, Y. Bengio, \"Understanding the difficulty of training deep feedforward "
            "neural networks,\" Proceedings of AISTATS, pp. 249–256, 2010."
        ),
        (
            "[10]",
            "I.E. Lagaris, A. Likas, D.I. Fotiadis, \"Artificial neural networks for solving "
            "ordinary and partial differential equations,\" IEEE Transactions on Neural Networks, "
            "vol. 9, no. 5, pp. 987–1000, 1998. DOI: 10.1109/72.712178"
        ),
        (
            "[11]",
            "N. Rahaman et al., \"On the spectral bias of neural networks,\" Proceedings of ICML, "
            "pp. 5301–5310, 2019."
        ),
    ]

    for num, text in refs:
        para = doc.add_paragraph()
        para.paragraph_format.space_before = Pt(2)
        para.paragraph_format.space_after  = Pt(4)
        para.paragraph_format.left_indent  = Cm(0.8)
        para.paragraph_format.first_line_indent = Cm(-0.8)

        bold_run = para.add_run(num + " ")
        bold_run.bold       = True
        bold_run.font.name  = "Times New Roman"
        bold_run.font.size  = Pt(10)

        body_run = para.add_run(text)
        body_run.font.name  = "Times New Roman"
        body_run.font.size  = Pt(10)

    # ========================================================================
    # SAVE
    # ========================================================================
    doc.save(OUT)
    print(f"Document saved to: {OUT}")
    return OUT


# ---------------------------------------------------------------------------
# ENTRY POINT
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    build_document()
