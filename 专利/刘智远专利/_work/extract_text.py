# -*- coding: utf-8 -*-
"""Extract text, metadata and figures from the pylon truss modeler paper."""
import sys
from pathlib import Path

import fitz  # PyMuPDF

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
PDF = ROOT / "A_Novel_Power_Pylon_Truss_Modeler_for_LoD3_Reconstruction_From_ULS_Data_Bridging_the_Gap_Between_Visualization_and_Simulation.pdf"
OUT = Path(__file__).resolve().parent

doc = fitz.open(PDF)
print("pages:", doc.page_count)
print("metadata:", doc.metadata)

lines = []
for i, page in enumerate(doc):
    lines.append(f"\n===== PAGE {i + 1} =====\n")
    # sort=True gives reading order that handles two-column layout reasonably
    lines.append(page.get_text("text", sort=False))
(OUT / "paper_text.txt").write_text("".join(lines), encoding="utf-8")

# Render each page to PNG for visual inspection of figures/tables
img_dir = OUT / "pages"
img_dir.mkdir(exist_ok=True)
for i, page in enumerate(doc):
    pix = page.get_pixmap(dpi=110)
    pix.save(img_dir / f"page_{i + 1:02d}.png")
print("done")
