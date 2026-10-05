# -*- coding: utf-8 -*-
"""从前期 320 件 CN 专利扫描（_work/patent_hits.md）中筛出与专利2相关的条目（本地处理，无网络）。"""
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE.parents[3] / "_work" / "patent_hits.md"
OUT = HERE.parent / "_raw" / "hits_filtered.md"

KW = re.compile(r"InSAR|SAR|雷达|角反射|反射器|沉降|塔基|温度|热胀|影响矩阵|有限元|倾斜|冻土|形变|位移")


def main():
    text = SRC.read_text(encoding="utf-8")
    entries = re.split(r"\n(?=- [A-Z]{2}\d)", text)
    seen, rows = set(), []
    for e in entries:
        m = re.match(r"- ([A-Z]{2}\d+[A-Z]\d?)\s*\|\s*([^|]*)\|\s*([^|]*)\|\s*(.*)", e)
        if not m:
            continue
        no = m.group(1)
        if no in seen:
            continue
        head = m.group(4).split("\n")[0]
        snippet = " ".join(e.split("\n")[1:]).strip(" -")
        if KW.search(head + snippet):
            seen.add(no)
            rows.append(f"- {no} | {m.group(2).strip()} | {m.group(3).strip()} | {head.strip()}\n  - {snippet[:200]}")
    OUT.write_text(f"# 前期扫描中与专利2相关条目（{len(rows)} 件）\n\n" + "\n".join(rows), encoding="utf-8")
    print(len(rows))


if __name__ == "__main__":
    main()
