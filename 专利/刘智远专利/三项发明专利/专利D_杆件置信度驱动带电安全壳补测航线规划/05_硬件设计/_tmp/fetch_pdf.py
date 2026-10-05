# -*- coding: utf-8 -*-
"""临时脚本：下载公开标准征求意见稿 PDF 并抽取含关键字的文本段（用后删除）。"""
import os
import re
import sys
import urllib.request

import fitz  # PyMuPDF

url, out, *keys = sys.argv[1:]
here = os.path.dirname(os.path.abspath(__file__))
pdf = os.path.join(here, out)
if not os.path.exists(pdf):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as r, open(pdf, "wb") as f:
        f.write(r.read())
doc = fitz.open(pdf)
print("pages", doc.page_count)
txt = []
for i, p in enumerate(doc):
    t = p.get_text()
    txt.append((i + 1, t))
with open(pdf + ".txt", "w", encoding="utf-8") as f:
    for i, t in txt:
        f.write(f"\n=== page {i} ===\n{t}")
for i, t in txt:
    for k in keys:
        for m in re.finditer(k, t):
            s = max(0, m.start() - 300)
            print(f"--- p{i} [{k}] ---")
            print(t[s:m.end() + 900])
            break
