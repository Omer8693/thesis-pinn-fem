"""
generate_report.py
Generates a professional 5-page A4 academic PDF for the NAS-MCO-PINNs project.
Output: NAS_PINNS3_professor_brief.pdf  (same directory as this script)

Usage:
    python generate_report.py
"""

import os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.lines as mlines
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib import rcParams

# ── paths ────────────────────────────────────────────────────────────────────
BASE  = os.path.dirname(os.path.abspath(__file__))
ROOT  = os.path.normpath(os.path.join(BASE, "..", ".."))
PLOTS = os.path.join(ROOT, "level9_sa_fourier", "results", "plots")
OUT   = os.path.join(BASE, "NAS_PINNS3_professor_brief.pdf")

# ── global style ──────────────────────────────────────────────────────────────
rcParams.update({
    "font.family":        "DejaVu Serif",
    "font.serif":         ["DejaVu Serif"],
    "mathtext.fontset":   "dejavuserif",
    "axes.unicode_minus": True,
    "figure.facecolor":   "white",
    "axes.facecolor":     "white",
})

A4W, A4H  = 8.27, 11.69     # inches
DPI       = 180
NAVY      = "#1a237e"
BODY      = "#222222"
LIGHT     = "#e8eaf6"
MID_BLUE  = "#9fa8da"
ALT_ROW   = "#eef0fb"
DATE_STR  = "March 2026"

# margins in inches
ML = 1.00   # left
MR = 0.85   # right
MT = 0.72   # top
MB = 0.60   # bottom
FH = 0.30   # footer height (inside bottom margin)


# ════════════════════════════════════════════════════════════════════════════
# Page helper — cursor-based layout (cursor = inches from top of content area)
# ════════════════════════════════════════════════════════════════════════════
class Page:
    def __init__(self, page_num, total_pages=5):
        self.fig        = plt.figure(figsize=(A4W, A4H))
        self.page_num   = page_num
        self.total      = total_pages
        self.cw         = A4W - ML - MR          # content width  (inches)
        self.ch         = A4H - MT - MB - FH     # content height (inches)
        self.cursor     = 0.0                    # inches from top of content

    # ── coordinate helpers ────────────────────────────────────────────────
    def _fy(self, y_from_top_inch):
        """Convert inches-from-top-of-content to figure fraction (y)."""
        return (A4H - MT - y_from_top_inch) / A4H

    def _fx(self, x_offset_inch=0.0):
        """Convert inches-from-left-of-content to figure fraction (x)."""
        return (ML + x_offset_inch) / A4W

    def _ax(self, height_inch, x_offset=0.0, width=None):
        """Create an axes starting at current cursor, with given height."""
        if width is None:
            width = self.cw - x_offset
        fx = self._fx(x_offset)
        fy = self._fy(self.cursor)          # top of axes in fig coords
        fw = width / A4W
        fh = height_inch / A4H
        # matplotlib axes: [left, bottom, width, height]
        ax = self.fig.add_axes([fx, fy - fh, fw, fh])
        ax.set_axis_off()
        return ax

    # ── basic primitives ──────────────────────────────────────────────────
    def vspace(self, h):
        self.cursor += h

    def hline(self, color="#cccccc", lw=0.6):
        y = self._fy(self.cursor)
        self.fig.add_artist(mlines.Line2D(
            [ML / A4W, (ML + self.cw) / A4W], [y, y],
            transform=self.fig.transFigure,
            color=color, linewidth=lw,
        ))
        self.cursor += 0.04

    # ── text ──────────────────────────────────────────────────────────────
    def text(self, content, size=9.2, color=BODY, bold=False,
             indent=0.0, extra_skip=0.0, linespacing=1.50,
             ha="left", center=False):
        """Render one text element at the current cursor and advance."""
        weight  = "bold" if bold else "normal"
        line_h  = size / 72.0 * linespacing

        x_fig = self._fx(indent)
        if center:
            x_fig = 0.5
            ha    = "center"

        y_fig = self._fy(self.cursor + line_h * 0.18)  # slight top padding
        self.fig.text(
            x_fig, y_fig, content,
            fontsize=size, color=color, fontweight=weight,
            va="top", ha=ha,
            transform=self.fig.transFigure,
            fontfamily="DejaVu Serif",
            wrap=True,
        )
        self.cursor += line_h + extra_skip

    def section(self, title, size=11.2, skip_before=0.14, skip_after=0.06):
        """Bold navy heading with a hairline rule underneath."""
        self.cursor += skip_before
        line_h = size / 72.0 * 1.45
        y_fig  = self._fy(self.cursor + line_h * 0.15)
        self.fig.text(
            self._fx(), y_fig, title,
            fontsize=size, color=NAVY, fontweight="bold",
            va="top", ha="left",
            transform=self.fig.transFigure,
            fontfamily="DejaVu Serif",
        )
        self.cursor += line_h + 0.04
        # thin rule
        self.hline(color=NAVY, lw=0.7)
        self.cursor += skip_after - 0.04   # hline already added 0.04

    def bullet(self, items, size=9.0, indent=0.20, gap=0.05):
        for item in items:
            self.text(f"\u2022  {item}", size=size, indent=indent,
                      extra_skip=gap)

    # ── table ──────────────────────────────────────────────────────────────
    def table(self, headers, rows, col_widths=None,
              row_height=0.22, fontsize=8.2,
              header_bg=NAVY, alt_bg=ALT_ROW):
        n_cols = len(headers)
        if col_widths is None:
            col_widths = [self.cw / n_cols] * n_cols

        n_rows   = len(rows) + 1   # +1 for header
        total_h  = row_height * n_rows

        ax = self._ax(total_h)

        # x positions of column left edges (axes coords 0–1 maps to cw)
        x_left = [sum(col_widths[:j]) / self.cw for j in range(n_cols)]

        def row_bottom_ax(r):
            """Bottom of row r (0=header) in axes coords."""
            return 1.0 - (r + 1) / n_rows

        def draw_cell(r, j, text_str, bg, fg=BODY, fw="normal"):
            bx = x_left[j]
            by = row_bottom_ax(r)
            bw = col_widths[j] / self.cw
            bh = 1.0 / n_rows
            rect = mpatches.FancyBboxPatch(
                (bx, by), bw, bh,
                boxstyle="square,pad=0",
                facecolor=bg, edgecolor="#c8c8c8", linewidth=0.35,
                transform=ax.transAxes, clip_on=False,
            )
            ax.add_patch(rect)
            cx = bx + bw / 2
            cy = by + bh / 2
            ax.text(cx, cy, text_str,
                    fontsize=fontsize, color=fg, fontweight=fw,
                    ha="center", va="center",
                    transform=ax.transAxes,
                    fontfamily="DejaVu Serif")

        # header row
        for j, hdr in enumerate(headers):
            draw_cell(0, j, hdr, bg=header_bg, fg="white", fw="bold")

        # data rows
        for i, row in enumerate(rows):
            bg = alt_bg if i % 2 == 0 else "white"
            for j, cell in enumerate(row):
                draw_cell(i + 1, j, str(cell), bg=bg)

        self.cursor += total_h + 0.06

    # ── image ──────────────────────────────────────────────────────────────
    def image(self, path, height=2.2, caption=None, caption_size=7.8):
        ax = self._ax(height)
        ax.set_axis_off()
        try:
            img = plt.imread(path)
            ax.imshow(img, aspect="auto")
        except Exception:
            ax.add_patch(mpatches.FancyBboxPatch(
                (0.01, 0.01), 0.98, 0.98,
                boxstyle="square,pad=0", facecolor=LIGHT,
                edgecolor=MID_BLUE, linewidth=1.0,
                transform=ax.transAxes,
            ))
            ax.text(0.5, 0.5,
                    f"[Figure not found]\n{os.path.basename(path)}",
                    ha="center", va="center", fontsize=8,
                    color="#777777", transform=ax.transAxes)
        self.cursor += height
        if caption:
            self.text(caption, size=caption_size, color="#555555",
                      extra_skip=0.04)

    # ── footer ─────────────────────────────────────────────────────────────
    def footer(self):
        y_f = (MB - FH * 0.35) / A4H
        # rule
        self.fig.add_artist(mlines.Line2D(
            [ML / A4W, (A4W - MR) / A4W],
            [(MB + FH * 0.55) / A4H] * 2,
            transform=self.fig.transFigure,
            color="#aaaaaa", linewidth=0.5,
        ))
        # left label
        self.fig.text(
            ML / A4W, y_f,
            f"NAS-MCO-PINNs Progress Report \u2014 Page {self.page_num} of {self.total}",
            fontsize=7.5, color="#666666", va="baseline", ha="left",
            fontfamily="DejaVu Serif",
        )
        # right date
        self.fig.text(
            (A4W - MR) / A4W, y_f, DATE_STR,
            fontsize=7.5, color="#666666", va="baseline", ha="right",
            fontfamily="DejaVu Serif",
        )

    def save(self, pdf):
        self.footer()
        pdf.savefig(self.fig, dpi=DPI)
        plt.close(self.fig)


# ════════════════════════════════════════════════════════════════════════════
# PAGE 1 — Title + Motivation + Problem Statement
# ════════════════════════════════════════════════════════════════════════════
def make_page1(pdf):
    p = Page(1)

    # ── banner ────────────────────────────────────────────────────────────
    banner_h = 1.50
    ax_b = p._ax(banner_h)
    ax_b.add_patch(mpatches.FancyBboxPatch(
        (0, 0), 1, 1, boxstyle="square,pad=0",
        facecolor=NAVY, edgecolor="none",
        transform=ax_b.transAxes,
    ))
    ax_b.text(
        0.5, 0.70,
        ("NAS-MCO-PINNs: A Nine-Level Framework for\n"
         "Physics-Informed Neural Network Optimization\n"
         "in Industrial Thermal Simulation"),
        fontsize=13.0, color="white", fontweight="bold",
        ha="center", va="center", transform=ax_b.transAxes,
        fontfamily="DejaVu Serif", linespacing=1.55,
    )
    ax_b.text(
        0.5, 0.17,
        "IKT464 Advanced ICT Project Progress Report \u2014 March 2026",
        fontsize=9.2, color="#c5cae9",
        ha="center", va="center", transform=ax_b.transAxes,
        fontfamily="DejaVu Serif",
    )
    p.cursor += banner_h + 0.12

    # ── Section 1 ─────────────────────────────────────────────────────────
    p.section("1.  Introduction and Motivation", skip_before=0.0)

    p.text(
        "We study the water quenching of A356 aluminum automotive subframes. "
        "Parts exit a solution heat treatment furnace at 540\u00b0C and are "
        "submerged in 20\u00b0C quench water. The rapid, non-uniform cooling "
        "generates steep temperature gradients, residual stresses, and permanent "
        "geometric distortions that must be predicted and controlled in order to "
        "meet dimensional tolerances in series production.",
        size=9.2, extra_skip=0.05,
    )

    p.text(
        "The standard simulation tool is the Finite Element Method (FEM). "
        "While accurate, FEM requires 21 time steps of approximately 8.8 seconds "
        "each, giving a total runtime of \u2248184 seconds per run. "
        "This is too slow for design optimization or real-time process control, "
        "which can require thousands of evaluations.",
        size=9.2, extra_skip=0.05,
    )

    p.text(
        "We propose Physics-Informed Neural Networks (PINNs) [1] as a faster "
        "surrogate. Once trained (400\u2013600 s), a PINN predicts the full "
        "temperature field in approximately 0.01 s\u2014an 18,400\u00d7 speedup "
        "at inference. Our framework is organized into nine progressive levels, "
        "each adding a new capability. "
        "The Level 9 model achieves "
        r"$L_2 = 0.014$"
        ", which is 4\u00d7 better than the Level 5 reference "
        r"($L_2 = 0.055$)"
        " and 9\u00d7 better than the standard FEM-skip approach "
        r"($L_2 = 0.126$)"
        ".",
        size=9.2, extra_skip=0.08,
    )

    # ── Section 2 ─────────────────────────────────────────────────────────
    p.section("2.  Overview of Contributions", skip_before=0.0)

    p.text(
        "This project introduces three technical innovations: one novel "
        "contribution designed specifically for this problem, and two carefully "
        "adapted methods from the recent PINN literature.",
        size=9.2, extra_skip=0.06,
    )

    contrib_items = [
        (
            "Temporal Skip Operator  [our contribution].",
            "A single PINN is trained to predict "
            r"$s$ time steps ahead from any initial condition $T_{\mathrm{IC}}$, "
            "reducing the required training runs from 21 to as few as 4. "
            "At skip\u2009=\u20092 this cuts training time by 48% while also "
            r"improving accuracy ($L_2$: 0.126 $\rightarrow$ 0.108)."
        ),
        (
            "Fourier Feature Embedding  [Tancik et al., 2020].",
            "Random Fourier projections are prepended to the network inputs, "
            "enabling the MLP to learn the rapid early-cooling signal "
            r"($\Delta T \approx 200\,{}^\circ\mathrm{C}$ in the first 5 s). "
            "We implemented the FourierEmbedding class from scratch following [3]."
        ),
        (
            "Self-Adaptive Loss Weights  [Wang et al., 2022].",
            "The three PINN loss terms differ in magnitude by up to "
            r"$10^4$. "
            "We make the weights learnable via a softplus activation, eliminating "
            "manual tuning. "
            r"Final values: $\lambda_{\mathrm{phys}}\approx 0.48$, "
            r"$\lambda_{\mathrm{bc}}\approx 9.28$, "
            r"$\lambda_{\mathrm{ic}}\approx 9.28$."
        ),
    ]

    for i, (label, body) in enumerate(contrib_items):
        p.text(f"  {i+1}.  {label}", size=9.2, bold=False,
               indent=0.10, extra_skip=0.01)
        p.text(f"       {body}", size=8.9, indent=0.10, extra_skip=0.06)

    p.save(pdf)


# ════════════════════════════════════════════════════════════════════════════
# PAGE 2 — Physical Problem + FEM Reference Model
# ════════════════════════════════════════════════════════════════════════════
def make_page2(pdf):
    p = Page(2)

    # ── Section 3 ─────────────────────────────────────────────────────────
    p.section("3.  Physical Problem: A356 Aluminum Quenching", skip_before=0.0)

    p.text(
        "The temperature field inside the aluminum part obeys the transient "
        "heat conduction equation:",
        size=9.2, extra_skip=0.03,
    )
    p.text(
        r"$\rho\, c_p\, \dfrac{\partial T}{\partial t} \;=\; k\,\nabla^2 T$",
        size=12.0, indent=1.10, extra_skip=0.04, linespacing=1.65,
    )
    p.text(
        r"where $\rho = 2670\,\mathrm{kg/m^3}$, "
        r"$c_p = 963\,\mathrm{J/(kg\cdot K)}$, "
        r"$k = 151\,\mathrm{W/(m\cdot K)}$ for A356 aluminum.",
        size=9.0, extra_skip=0.06,
    )

    p.text(
        "At the part boundary, Newton\u2019s law of cooling "
        "(Robin boundary condition) models convective heat transfer to the "
        "quench water:",
        size=9.2, extra_skip=0.03,
    )
    p.text(
        r"$-k\,\dfrac{\partial T}{\partial n} \;=\; h\,(T - T_\infty)$",
        size=12.0, indent=1.10, extra_skip=0.04, linespacing=1.65,
    )
    p.text(
        r"where $h = 5000\,\mathrm{W/(m^2\cdot K)}$ is the heat transfer "
        r"coefficient and $T_\infty = 20\,{}^\circ\mathrm{C}$.",
        size=9.0, extra_skip=0.06,
    )

    p.text(
        r"Initial condition: $T(x,\,y,\,0) = 540\,{}^\circ\mathrm{C}$ "
        "(part exits the solution heat treatment furnace).",
        size=9.0, extra_skip=0.04,
    )
    p.text(
        r"Domain: 2D plate $1.3\,\mathrm{m} \times 0.6\,\mathrm{m}$. "
        r"Simulation time $t \in [0,\,30]\,\mathrm{s}$, discretized into "
        "21 FEM time steps.",
        size=9.0, extra_skip=0.10,
    )

    # material table
    p.text("Table 1.  A356 aluminum key material parameters.",
           size=8.5, color="#444444", extra_skip=0.04)
    mat_h = ["Parameter", "Symbol", "Value", "Unit"]
    mat_r = [
        ["Density",              r"$\rho$",    "2670",  r"$\mathrm{kg/m^3}$"],
        ["Specific heat",        r"$c_p$",      "963",  r"$\mathrm{J/(kg\!\cdot\!K)}$"],
        ["Thermal conductivity", r"$k$",        "151",  r"$\mathrm{W/(m\!\cdot\!K)}$"],
        ["Initial temperature",  r"$T_0$",      "540",  r"${}^\circ\mathrm{C}$"],
        ["HTC (quench water)",   r"$h$",       "5000",  r"$\mathrm{W/(m^2\!\cdot\!K)}$"],
    ]
    p.table(mat_h, mat_r, col_widths=[2.60, 1.00, 0.95, 1.85],
            row_height=0.215, fontsize=8.2)

    # ── Section 4 ─────────────────────────────────────────────────────────
    p.section("4.  FEM Reference Model", skip_before=0.0)

    p.text(
        "We did NOT implement FEM ourselves. All reference simulation data used "
        "in this project were extracted from the following paper "
        "(hereafter [2]):",
        size=9.2, extra_skip=0.04,
    )

    # citation box
    cit_h = 0.60
    ax_c = p._ax(cit_h)
    ax_c.add_patch(mpatches.FancyBboxPatch(
        (0, 0), 1, 1,
        boxstyle="round,pad=0.04", facecolor=LIGHT,
        edgecolor=MID_BLUE, linewidth=0.9,
        transform=ax_c.transAxes,
    ))
    ax_c.text(
        0.025, 0.55,
        ("\"Mitigating distortions in cast automotive subframes: "
         "A finite element simulation approach,\"\n"
         "International Journal of Advanced Manufacturing Technology, 2026.  "
         "DOI: 10.1007/s00170-026-17515-w"),
        fontsize=8.4, color="#333333",
        va="center", ha="left", transform=ax_c.transAxes,
        fontfamily="DejaVu Serif",
    )
    p.cursor += cit_h + 0.08

    p.text("From [2] we extracted three categories of data:",
           size=9.2, extra_skip=0.04)

    p.bullet([
        "(a)  A356 material parameters (Table\u00a01 of [2]): flow stress, "
        "hardening exponent, and strain-rate sensitivity as functions of "
        "temperature.",

        "(b)  Heat transfer coefficient curve h(T) (Figure\u00a06 of [2]): "
        "boiling-regime transitions \u2014 film boiling \u2192 nucleate "
        "boiling \u2192 forced convection as the part cools.",

        "(c)  Reference temperature histories (Figures\u00a07, 15\u201317 of [2]): "
        "used as ground truth for all L2 error computations in this project.",
    ], size=8.8, indent=0.22, gap=0.05)

    p.vspace(0.06)
    p.text(
        r"FEM runtime (Level 2, Bayesian, skip=1): "
        r"$21\;\mathrm{steps} \times 8.8\;\mathrm{s/step} = 184.4\;\mathrm{s}$ total.",
        size=9.0, extra_skip=0.04,
    )

    p.save(pdf)


# ════════════════════════════════════════════════════════════════════════════
# PAGE 3 — Three Key Innovations
# ════════════════════════════════════════════════════════════════════════════
def make_page3(pdf):
    p = Page(3)

    # ── Section 5 ─────────────────────────────────────────────────────────
    p.section("5.  Temporal Skip Operator  [our contribution]",
              skip_before=0.0)

    p.text(
        "Standard PINNs need one separate training run per FEM time step "
        "(21 runs, \u2248\u20093,800 s total). We designed a skip operator that "
        r"trains ONE network $f_\theta$ to predict $s$ time steps ahead from "
        r"any initial temperature field $T_{\mathrm{IC}}$. "
        "The predicted field is:",
        size=9.2, extra_skip=0.04,
    )
    p.text(
        r"$\hat{T}(t + s\,\Delta t) \;=\; T_{\mathrm{IC}} "
        r"+ \tau\cdot f_\theta\!\left(x,\;y,\;\tau,\;T_{\mathrm{IC}}\right)$",
        size=12.5, indent=1.00, extra_skip=0.04, linespacing=1.70,
    )
    p.text(
        r"where $\tau = t\,/\,(s\,\Delta t) \in [0,1]$ is the normalized time "
        r"coordinate.  At $\tau = 0$ the prediction exactly equals $T_{\mathrm{IC}}$, "
        "so the initial condition is enforced automatically\u2014without a "
        "penalty term. This residual formulation is inspired by [Lagaris et al., "
        "1998] and adapted here for the temporal skip setting.",
        size=9.0, extra_skip=0.08,
    )

    p.text("Table 2.  Temporal skip results (Level 2, Bayesian NAS).",
           size=8.5, color="#444444", extra_skip=0.04)
    sk_h = ["Skip  s", "Training Runs", "FEM Steps Saved", r"$L_2$ Error"]
    sk_r = [
        ["1  (baseline)", "21", " 0 %", "0.126"],
        ["2",             "11", "48 %", "0.108"],
        ["4",              "6", "71 %", "0.204"],
        ["6",              "4", "81 %", "0.294"],
    ]
    p.table(sk_h, sk_r, col_widths=[1.65, 1.45, 1.80, 1.50],
            row_height=0.225, fontsize=8.5)

    p.text(
        "Key finding: skip=2 reduces training by 48% and actually improves "
        "accuracy relative to skip=1. The improvement arises because fewer "
        "FEM interpolation errors accumulate across the 21 time steps.",
        size=9.0, extra_skip=0.04,
    )

    # ── Section 6 ─────────────────────────────────────────────────────────
    p.section("6.  Fourier Feature Embedding  [Tancik et al., 2020]")

    p.text(
        "Standard MLPs exhibit a \u201cspectral bias\u201d: they preferentially "
        "learn low-frequency patterns first [Rahaman et al., 2019]. "
        r"A356 quenching has a rapid early-cooling phase "
        r"($\Delta T \approx 200\,{}^\circ\mathrm{C}$ in the first 5 s)\u2014"
        "a high-frequency temporal signal on which standard PINNs converge slowly.",
        size=9.2, extra_skip=0.04,
    )
    p.text(
        r"Solution [3]: project the inputs $\mathbf{v}$ through random Fourier "
        "features before the MLP:",
        size=9.2, extra_skip=0.03,
    )
    p.text(
        r"$\gamma(\mathbf{v}) = \left[\sin(2\pi\mathbf{B}\mathbf{v}),\;"
        r"\cos(2\pi\mathbf{B}\mathbf{v})\right]$"
        r", $\quad \mathbf{B} \sim \mathcal{N}(0,\,\sigma^2)$",
        size=11.5, indent=0.90, extra_skip=0.04, linespacing=1.65,
    )
    p.text(
        r"We used $n_{\mathrm{fourier}} = 64$ features (output dimension = 128) "
        r"and $\sigma = 1.0$.  We implemented the FourierEmbedding class "
        "from scratch following [3].  The matrix B is sampled once at "
        "initialization and frozen during training.",
        size=9.0, extra_skip=0.04,
    )

    # ── Section 7 ─────────────────────────────────────────────────────────
    p.section("7.  Self-Adaptive Loss Weights  [Wang et al., 2022]")

    p.text(
        "The PINN loss combines three terms:",
        size=9.2, extra_skip=0.03,
    )
    p.text(
        r"$L_{\mathrm{total}} \;=\; "
        r"\lambda_{\mathrm{phys}}\,L_{\mathrm{phys}} "
        r"+ \lambda_{\mathrm{bc}}\,L_{\mathrm{bc}} "
        r"+ \lambda_{\mathrm{ic}}\,L_{\mathrm{ic}}$",
        size=12.0, indent=1.00, extra_skip=0.04, linespacing=1.65,
    )
    p.text(
        r"The three raw loss scales differ by up to $10^4$: "
        r"$L_{\mathrm{phys}} \sim 4\!\times\!10^7$, "
        r"$L_{\mathrm{bc}} \sim 17{,}333$, "
        r"$L_{\mathrm{ic}} \sim 520$.  "
        "Manual weight tuning is therefore highly problem-specific and "
        "requires expert knowledge.",
        size=9.0, extra_skip=0.04,
    )
    p.text(
        r"Solution [4, 5]: make each $\lambda$ learnable via softplus:",
        size=9.2, extra_skip=0.03,
    )
    p.text(
        r"$\lambda \;=\; \mathrm{softplus}(w)$"
        r", $\quad w$ trained jointly with the network weights at a lower "
        "learning rate",
        size=11.0, indent=0.90, extra_skip=0.04, linespacing=1.65,
    )
    p.text(
        r"We implemented the SelfAdaptiveWeights module. "
        r"Final learned values: $\lambda_{\mathrm{phys}} \approx 0.48$, "
        r"$\lambda_{\mathrm{bc}} \approx 9.28$, "
        r"$\lambda_{\mathrm{ic}} \approx 9.28$.  "
        "The boundary and IC terms receive \u223c19\u00d7 more weight than the "
        "PDE residual\u2014consistent with the physical intuition that an "
        "incorrect initial overshoot propagates errors through all subsequent "
        "time steps.",
        size=9.0, extra_skip=0.04,
    )

    p.save(pdf)


# ════════════════════════════════════════════════════════════════════════════
# PAGE 4 — Results
# ════════════════════════════════════════════════════════════════════════════
def make_page4(pdf):
    p = Page(4)

    # ── Section 8 ─────────────────────────────────────────────────────────
    p.section("8.  Nine-Level Progression", skip_before=0.0)

    p.text("Table 3.  Summary of all nine levels.",
           size=8.5, color="#444444", extra_skip=0.04)

    lvl_h = ["Level", "Focus", r"Best $L_2$", "Train Time", "Key Innovation"]
    lvl_r = [
        ["L1",  "Single-shot 2D",    "0.076",             "232 s",
         "Baseline PINN + NAS"],
        ["L2",  "Temporal Skip",      "0.108 (s=2)",       " 91 s",
         "Skip operator (48% faster)"],
        ["L3",  "Hybrid FEM",         "\u223c0.12",        "190 s",
         "Adaptive threshold skip"],
        ["L4",  "Distortion",         "MAE=14.4\u00b0C",   "240 s",
         "Mechanical coupling"],
        ["L5",  "L-BFGS Refinement",  "0.030",             "240 s",
         "Adam \u2192 L-BFGS two-stage"],
        ["L6",  "Poisson Benchmark",  "\u223c0.018",        "200 s",
         "Generalisation to other PDEs"],
        ["L7a", "Temporal Analysis",  "\u223c0.025",        "220 s",
         "Time-skip regime analysis"],
        ["L7b", "Multi-Domain",       "\u223c0.022",        "230 s",
         "5 domain geometries"],
        ["L8",  "3D MCO",             "MAE=5.5\u00b0C",    "613 s",
         "3D + MCO adaptive weights"],
        ["L9",  "SA + Fourier",       "0.014",             "444 s",
         "SA weights + Fourier features"],
    ]
    p.table(lvl_h, lvl_r,
            col_widths=[0.56, 1.62, 1.22, 0.96, 2.04],
            row_height=0.215, fontsize=7.8)

    # ── Section 9 ─────────────────────────────────────────────────────────
    p.section("9.  Level 9 Highlight \u2014 Best Result", skip_before=0.0)

    p.text("Table 4.  Level 9 detailed results.",
           size=8.5, color="#444444", extra_skip=0.04)

    l9_h = ["Variant", "Optimizer", "Dim", r"Best $L_2$", "Train Time", "Params"]
    l9_r = [
        ["SA+Fourier", "Bayesian", "2D", "0.0253",  "482 s", "111,439"],
        ["SA+Fourier", "NSGA-II",  "2D", "0.0137*", "444 s",  "67,015"],
        ["SA+Fourier", "NSGA-III", "2D", "0.0668",  "412 s",  "21,151"],
        ["SA+Fourier", "Bayesian", "3D", "0.247",   "596 s", "111,439"],
        ["SA-only",    "Bayesian", "2D", "0.0151",  "404 s",  "92,564"],
        ["SA-only",    "NSGA-II",  "2D", "0.0397",  "378 s",  "47,890"],
    ]
    p.table(l9_h, l9_r,
            col_widths=[1.35, 1.00, 0.55, 1.00, 1.00, 1.50],
            row_height=0.215, fontsize=8.0)

    p.text(
        r"*  Best result: $L_2 = 0.0137$ (SA+Fourier, NSGA-II, 2D). "
        "This is 4\u00d7 better than the Level 5 reference (0.055) and "
        "9\u00d7 better than FEM skip=1 (0.126).",
        size=8.5, indent=0.06, extra_skip=0.05,
    )
    p.text(
        r"3D results: Bayesian NAS achieves $L_2 = 0.247$, but NSGA-II and "
        r"NSGA-III fail ($L_2 > 0.7$) because the NAS architecture search "
        "was performed in 2D and did not identify networks deep or wide enough "
        "for 3D inputs. The planned next step is to re-run NAS directly in 3D.",
        size=9.0, extra_skip=0.05,
    )
    p.text(
        "Inference time after training: \u223c0.01 s vs FEM 184 s "
        "(18,400\u00d7 speedup at inference).",
        size=9.0, extra_skip=0.10,
    )

    # ── figures ───────────────────────────────────────────────────────────
    img1 = os.path.join(PLOTS, "fem_pinn_summary_table.png")
    img2 = os.path.join(PLOTS, "fig1_2d_comparison.png")
    avail_h = p.ch - p.cursor - 0.08
    img_h   = min(2.05, avail_h)

    exists1 = os.path.exists(img1)
    exists2 = os.path.exists(img2)

    if exists1 and exists2 and img_h > 0.5:
        half_w = (p.cw - 0.14) / 2
        try:
            im1 = plt.imread(img1)
            im2 = plt.imread(img2)
            ax1 = p._ax(img_h, x_offset=0.0, width=half_w)
            ax1.imshow(im1, aspect="auto")
            ax2 = p._ax(img_h, x_offset=half_w + 0.14, width=half_w)
            ax2.imshow(im2, aspect="auto")
            p.cursor += img_h + 0.04
            p.text(
                "Left: Level 9 summary table (L2 per variant).  "
                "Right: 2D temperature field comparison (FEM vs PINN, NSGA-II best).",
                size=7.8, color="#555555",
            )
        except Exception:
            p.image(img1, height=img_h,
                    caption="Figure: Level 9 summary table.")
    elif exists1 and img_h > 0.5:
        p.image(img1, height=img_h,
                caption="Figure: Level 9 summary table.")
    elif exists2 and img_h > 0.5:
        p.image(img2, height=img_h,
                caption="Figure: 2D temperature field comparison (FEM vs PINN).")

    p.save(pdf)


# ════════════════════════════════════════════════════════════════════════════
# PAGE 5 — References
# ════════════════════════════════════════════════════════════════════════════
def make_page5(pdf):
    p = Page(5)

    p.section("References", skip_before=0.0)

    refs = [
        ("[1]",
         "M. Raissi, P. Perdikaris, G.E. Karniadakis, \u201cPhysics-informed "
         "neural networks: A deep learning framework for solving forward and "
         "inverse problems involving nonlinear partial differential equations,\u201d "
         "Journal of Computational Physics, vol.\u2009378, pp.\u2009686\u2013707, 2019.  "
         "DOI: 10.1016/j.jcp.2018.10.045"),

        ("[2]",
         "Mortensen et al., \u201cMitigating distortions in cast automotive "
         "subframes: A finite element simulation approach,\u201d "
         "International Journal of Advanced Manufacturing Technology, 2026.  "
         "DOI: 10.1007/s00170-026-17515-w"),

        ("[3]",
         "M. Tancik, P. Srinivasan, B. Mildenhall, S. Fridovich-Keil, "
         "N. Raghavan, U. Singhal, R. Ramamoorthi, J. Barron, R. Ng, "
         "\u201cFourier Features Let Networks Learn High Frequency Functions in "
         "Low Dimensional Domains,\u201d Advances in Neural Information Processing "
         "Systems (NeurIPS), vol.\u200933, pp.\u20097537\u20137547, 2020."),

        ("[4]",
         "S. Wang, Y. Teng, P. Perdikaris, \u201cUnderstanding and Mitigating "
         "Gradient Flow Pathologies in Physics-Informed Neural Networks,\u201d "
         "SIAM Journal on Scientific Computing, vol.\u200943, no.\u20095, "
         "pp.\u2009A3055\u2013A3081, 2021.  DOI: 10.1137/20M1318043"),

        ("[5]",
         "S. Wang, S. Sankaran, P. Perdikaris, \u201cRespecting Causality for "
         "Training Physics-Informed Neural Networks,\u201d Computer Methods in "
         "Applied Mechanics and Engineering, vol.\u2009421, p.\u2009116813, 2024.  "
         "DOI: 10.1016/j.cma.2024.116813"),

        ("[6]",
         "K. Deb, A. Pratap, S. Agarwal, T. Meyarivan, \u201cA fast and elitist "
         "multiobjective genetic algorithm: NSGA-II,\u201d IEEE Transactions on "
         "Evolutionary Computation, vol.\u20096, no.\u20092, pp.\u2009182\u2013197, 2002.  "
         "DOI: 10.1109/4235.996017"),

        ("[7]",
         "K. Deb, H. Jain, \u201cAn Evolutionary Many-Objective Optimization "
         "Algorithm Using Reference-Point-Based Nondominated Sorting Approach, "
         "Part I: Solving Problems with Box Constraints,\u201d IEEE Transactions on "
         "Evolutionary Computation, vol.\u200918, no.\u20094, pp.\u2009577\u2013601, 2014.  "
         "DOI: 10.1109/TEVC.2013.2281535"),

        ("[8]",
         "J. Snoek, H. Larochelle, R.P. Adams, \u201cPractical Bayesian "
         "Optimization of Machine Learning Algorithms,\u201d Advances in Neural "
         "Information Processing Systems (NeurIPS), vol.\u200925, "
         "pp.\u20092951\u20132959, 2012."),

        ("[9]",
         "X. Glorot, Y. Bengio, \u201cUnderstanding the difficulty of training "
         "deep feedforward neural networks,\u201d Proceedings of the 13th "
         "International Conference on Artificial Intelligence and Statistics "
         "(AISTATS), pp.\u2009249\u2013256, 2010."),
    ]

    tag_x   = p._fx(0.0)
    body_x  = p._fx(0.42)
    fs_ref  = 8.7
    line_h  = fs_ref / 72.0 * 1.55

    for tag, body in refs:
        y_fig = p._fy(p.cursor + line_h * 0.15)
        # tag in navy bold
        p.fig.text(
            tag_x, y_fig, tag,
            fontsize=fs_ref, color=NAVY, fontweight="bold",
            va="top", ha="left", fontfamily="DejaVu Serif",
        )
        # body in normal body color
        p.fig.text(
            body_x, y_fig, body,
            fontsize=fs_ref - 0.3, color=BODY,
            va="top", ha="left", fontfamily="DejaVu Serif",
            wrap=True,
        )
        # estimate lines needed (rough: ~85 chars per line at body_x position)
        n_lines = max(1, len(body) // 85)
        p.cursor += line_h * (n_lines + 0.85)

    p.save(pdf)


# ════════════════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════════════════
def main():
    os.makedirs(BASE, exist_ok=True)
    with PdfPages(OUT) as pdf:
        make_page1(pdf)
        make_page2(pdf)
        make_page3(pdf)
        make_page4(pdf)
        make_page5(pdf)

        d = pdf.infodict()
        d["Title"]    = (
            "NAS-MCO-PINNs: A Nine-Level Framework for Physics-Informed "
            "Neural Network Optimization in Industrial Thermal Simulation"
        )
        d["Author"]   = "IKT464 Student"
        d["Subject"]  = "IKT464 Advanced ICT Project Progress Report — March 2026"
        d["Keywords"] = ("PINN NAS FEM quenching A356 Fourier "
                         "self-adaptive loss weights temporal skip")

    print(f"PDF written to: {OUT}")


if __name__ == "__main__":
    main()
