#!/bin/bash
# Compile pentai_ieee.tex to PDF (run twice for cross-references)
# Requires: pdflatex (TeX Live or MiKTeX)
# On Overleaf: just upload all files and click Compile.

pdflatex -interaction=nonstopmode pentai_ieee.tex
pdflatex -interaction=nonstopmode pentai_ieee.tex
echo "Done. Output: pentai_ieee.pdf"
