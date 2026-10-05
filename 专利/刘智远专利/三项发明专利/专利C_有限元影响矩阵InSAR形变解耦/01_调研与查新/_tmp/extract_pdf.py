# -*- coding: utf-8 -*-
"""临时脚本：用 pymupdf 提取专利C 文献目录下 PDF 文本到 _tmp/txt，并输出页数与字数。"""
import pathlib
import fitz

base = pathlib.Path(__file__).resolve().parent.parent
src_dir = base / "文献"
out_dir = pathlib.Path(__file__).resolve().parent / "txt"
out_dir.mkdir(exist_ok=True)
for i, pdf in enumerate(sorted(src_dir.glob("*.pdf")), 1):
    doc = fitz.open(str(pdf))
    text = "\n".join(page.get_text() for page in doc)
    tag = f"C{i:02d}"
    (out_dir / f"{tag}.txt").write_text(text, encoding="utf-8")
    print(tag, pdf.name, "pages=", doc.page_count, "chars=", len(text))
