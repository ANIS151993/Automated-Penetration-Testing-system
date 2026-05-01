PentAI Pro — Complete LaTeX Source Package
==========================================

Paper Title:
  Self-Hosted LLM Orchestration for Autonomous Penetration Testing
  with Three-Layer Scope Enforcement and
  Tamper-Evident Cryptographic Audit Chains

Author: Md. Anisur Rahman Chowdhury (MARC)
Email:  engr.aanis@gmail.com

─── FILES ───────────────────────────────────────────────────────────
  pentai_ieee.tex   — Main LaTeX source (IEEE two-column conference)
  pentai_ieee.bib   — BibTeX companion file (all 12 references)
  pentai_ieee.pdf   — Compiled PDF (6 pages, ready to submit)
  IEEEtran.cls      — IEEE conference class file (v1.8b)
  compile.sh        — Shell compile script (Linux/macOS)
  README.txt        — This file

─── FIGURES ─────────────────────────────────────────────────────────
  All figures are drawn with TikZ/pgfplots directly inside the .tex
  file — NO external image files are required.

  Fig. 1  System Architecture        (TikZ block diagram)
  Fig. 2  Phase Latency              (pgfplots xbar)
  Fig. 3  Tool Execution Times       (pgfplots ybar)
  Fig. 4  LLM Output Token Counts    (pgfplots xbar, dual series)
  Fig. 5  Tool-Vulnerability Heatmap (pure TikZ, green palette)

─── HOW TO COMPILE ──────────────────────────────────────────────────
  Option A — Command line:
    bash compile.sh

  Option B — Overleaf (recommended for online editing):
    1. Create a new Overleaf project
    2. Upload pentai_ieee.tex, pentai_ieee.bib, IEEEtran.cls
    3. Set compiler to pdfLaTeX
    4. Click Compile

  Option C — VS Code with LaTeX Workshop extension:
    Open pentai_ieee.tex and press Ctrl+Alt+B

─── DEPENDENCIES ────────────────────────────────────────────────────
  LaTeX packages used (all included in TeX Live / MiKTeX):
    IEEEtran, inputenc, fontenc, microtype, graphicx, amsmath,
    amssymb, booktabs, xcolor, pgfplots, tikz, listings, url,
    hyperref, cleveref, balance, cite
