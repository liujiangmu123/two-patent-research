# -*- coding: utf-8 -*-
"""只读：导出 PDF 指定页文本到标准输出（调研用临时脚本，完成后删除）。
用法：python dump_pdf_pages.py <pdf> <起始页1基> <结束页1基>"""
import sys

import pymupdf

sys.stdout.reconfigure(encoding="utf-8")
p = sys.argv[1]
a, b = int(sys.argv[2]), int(sys.argv[3])
doc = pymupdf.open(p)
print("pages", doc.page_count)
for i in range(a - 1, min(b, doc.page_count)):
    print(f"===== page {i + 1} =====")
    print(doc[i].get_text())
