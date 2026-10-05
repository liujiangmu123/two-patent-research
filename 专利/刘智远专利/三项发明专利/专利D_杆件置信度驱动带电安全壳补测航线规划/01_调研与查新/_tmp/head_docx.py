# -*- coding: utf-8 -*-
"""只读：打印 docx 指定段落区间（调研用临时脚本，完成后删除）。
用法：python head_docx.py <docx> <起> <止>"""
import re
import sys

from docx import Document

sys.stdout.reconfigure(encoding="utf-8")
doc = Document(sys.argv[1])
a, b = int(sys.argv[2]), int(sys.argv[3])
for i, x in enumerate(doc.paragraphs[a:b], start=a):
    s = re.sub(r"\s+", " ", x.text).strip()
    if s:
        print(f"[{i}] {s[:1200]}")
