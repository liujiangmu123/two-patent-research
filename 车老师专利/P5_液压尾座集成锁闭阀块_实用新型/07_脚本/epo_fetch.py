# -*- coding: utf-8 -*-
r"""P5 查新：从 EPO 公开服务器（data.epo.org publication-server）下载 EP 公开/授权文本 PDF，抽取首页著录项目与权利要求。

Google Patents 在本次检索中连续返回 503，EP 文献改由 EPO 官方服务器取全文。请求间隔 ≥20 s。
用法：.venv\Scripts\python.exe 07_脚本\epo_fetch.py EP2761189:B1 EP1462681:A2 ...
输出：01_查新与创新点\文献\<号><种类>.pdf；01_查新与创新点\检索原始结果\epo_<号><种类>.json（首页文本、权利要求前 3000 字）
"""
import json
import os
import re
import sys
import time
import urllib.request

import pymupdf

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PDFDIR = os.path.join(ROOT, "01_查新与创新点", "文献")
RAW = os.path.join(ROOT, "01_查新与创新点", "检索原始结果")
os.makedirs(PDFDIR, exist_ok=True)
os.makedirs(RAW, exist_ok=True)


def fetch(pn, kind):
    url = "https://data.epo.org/publication-server/rest/v1.2/patents/%sNW%s/document.pdf" % (pn, kind)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
    b = urllib.request.urlopen(req, timeout=90).read()
    fn = os.path.join(PDFDIR, pn + kind + ".pdf")
    with open(fn, "wb") as fh:
        fh.write(b)
    doc = pymupdf.open(fn)
    pages = [p.get_text() for p in doc]
    full = "\n".join(pages)
    m = re.search(r"(Patentansprüche|Claims|Revendications)\s*\n", full)
    claims = full[m.start():m.start() + 3000] if m else ""
    # 英文权利要求（B 文献三语）
    me = re.search(r"\nClaims\s*\n", full)
    claims_en = full[me.start():me.start() + 3000] if me else ""
    out = {"公开号": pn + kind, "来源": url, "页数": doc.page_count, "首页": pages[0][:2500], "权利要求_原文前3000字": claims,
           "权利要求_英文前3000字": claims_en, "读取时间": time.strftime("%Y-%m-%d %H:%M"), "PDF本地": "文献/" + pn + kind + ".pdf"}
    with open(os.path.join(RAW, "epo_%s%s.json" % (pn, kind)), "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    return out


if __name__ == "__main__":
    for i, a in enumerate(sys.argv[1:]):
        if i:
            time.sleep(20)
        pn, kind = a.split(":")
        try:
            o = fetch(pn, kind)
            print(pn + kind, "ok", o["页数"], "pages | claims", len(o["权利要求_原文前3000字"]), flush=True)
        except Exception as e:  # noqa: BLE001
            print(pn + kind, "ERR", e, flush=True)
