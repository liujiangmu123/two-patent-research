# -*- coding: utf-8 -*-
"""Temporary: extract text of downloaded PDFs for reading (deleted after use)."""
import sys
from pathlib import Path
import pymupdf

sys.stdout.reconfigure(encoding="utf-8")
BASE = Path(__file__).resolve().parents[1] / "文献"
OUT = Path(__file__).resolve().parent
for pdf in sorted(BASE.glob("*.pdf")):
    try:
        doc = pymupdf.open(pdf)
        txt = "\n".join(page.get_text() for page in doc)
        (OUT / (pdf.stem + ".txt")).write_text(txt, encoding="utf-8")
        print(pdf.name, doc.page_count, len(txt))
    except Exception as e:
        print("FAIL", pdf.name, e)
