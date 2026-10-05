# -*- coding: utf-8 -*-
"""只读：在 docx 段落中检索关键词并打印命中段落（调研用临时脚本，完成后删除）。
用法：python grep_docx.py <docx> <kw1> [<kw2> ...]"""
import re
import sys

from docx import Document

sys.stdout.reconfigure(encoding="utf-8")
p = sys.argv[1]
kws = [k.lower() for k in sys.argv[2:]]
doc = Document(p)
paras = [x.text for x in doc.paragraphs]
print("paragraphs", len(paras))
for i, t in enumerate(paras):
    tl = t.lower()
    hit = [k for k in kws if k in tl]
    if hit:
        s = re.sub(r"\s+", " ", t).strip()
        print(f"--- [{i}] {hit}")
        print(s[:1500])
