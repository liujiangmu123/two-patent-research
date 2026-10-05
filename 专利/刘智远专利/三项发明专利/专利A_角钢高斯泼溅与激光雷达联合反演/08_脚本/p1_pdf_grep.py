# -*- coding: utf-8 -*-
"""从已下载 PDF 中抽取文本并按关键词输出上下文（用于核实规格参数与标准条文）。

用法：.venv\\Scripts\\python.exe p1_pdf_grep.py <pdf文件名前缀> <关键词1> [关键词2 ...] [--ctx 120] [--head 1500]
"""
import re
import sys
from pathlib import Path

import fitz  # PyMuPDF

sys.stdout.reconfigure(encoding="utf-8")
DOC_DIR = Path(__file__).resolve().parent.parent / "01_调研与查新" / "文献"


def main():
    args = sys.argv[1:]
    ctx, head = 120, 0
    if "--ctx" in args:
        i = args.index("--ctx"); ctx = int(args[i + 1]); del args[i:i + 2]
    if "--head" in args:
        i = args.index("--head"); head = int(args[i + 1]); del args[i:i + 2]
    prefix, kws = args[0], args[1:]
    for pdf in sorted(DOC_DIR.glob(prefix + "*.pdf")):
        with fitz.open(pdf) as d:
            text = "\n".join(p.get_text() for p in d)
        text_flat = re.sub(r"[ \t]+", " ", text)
        print(f"===== {pdf.name}  页数 {len(d) if False else ''} 字符 {len(text_flat)}")
        if head:
            print(text_flat[:head])
        for kw in kws:
            for m in list(re.finditer(re.escape(kw), text_flat))[:12]:
                s = max(0, m.start() - ctx); e = min(len(text_flat), m.end() + ctx)
                print(f"--- [{kw}] …{text_flat[s:e]}…".replace("\n", " "))


if __name__ == "__main__":
    main()
