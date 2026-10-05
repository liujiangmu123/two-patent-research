# -*- coding: utf-8 -*-
"""Prior-art scan via the public Google Patents query endpoint (keywords only, no project data sent)."""
import html
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
OUT = Path(__file__).resolve().parent / "patent_hits.md"

QUERIES = [
    ('"transmission tower" "point cloud" (member OR truss OR "angle steel") reconstruct', "20190101"),
    ("输电塔 点云 杆件 重建", "20190101"),
    ("铁塔 点云 主材 斜材", "20190101"),
    ("杆塔 点云 有限元 模型", "20190101"),
    ("输电塔 点云 桁架 节点", "20190101"),
    ("输电塔 点云 对称 补全", "20190101"),
    ("输电塔 点云 数字孪生 力学", "20200101"),
    ("角钢 点云 截面 规格 识别", "20190101"),
    ("输电塔 InSAR 形变", "20180101"),
    ("杆塔 冻土 基础 形变 监测", "20180101"),
    ("输电塔 倾斜 点云 多期", "20190101"),
    ("输电塔 基础 沉降 有限元 反演", "20190101"),
    ('"lattice tower" "point cloud" "finite element"', "20180101"),
    ('"truss" "point cloud" "structural graph" OR "wireframe" member node', "20200101"),
]


def query(q, after, num=30):
    inner = f"q={q}&after=priority:{after}&num={num}"
    url = "https://patents.google.com/xhr/query?url=" + urllib.parse.quote(inner, safe="") + "&exp="
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=40) as r:
        data = json.loads(r.read().decode("utf-8"))
    rows = []
    for cl in data.get("results", {}).get("cluster", []):
        for item in cl.get("result", []):
            p = item.get("patent", {})
            clean = lambda s: re.sub(r"<[^>]+>", "", html.unescape(s or "")).strip()
            rows.append({
                "no": p.get("publication_number"), "title": clean(p.get("title")),
                "assignee": clean(p.get("assignee")), "prio": p.get("priority_date"),
                "pub": p.get("publication_date"), "snippet": clean(p.get("snippet"))[:260],
            })
    return data.get("results", {}).get("total_num_results"), rows


def main():
    seen = set()
    lines = ["# Google Patents 查新扫描（自动）\n"]
    for q, after in QUERIES:
        try:
            total, rows = query(q, after)
        except Exception as e:  # network hiccup: record and continue
            lines.append(f"\n## {q}\n\n查询失败：{e}\n")
            print("FAIL", q, e)
            continue
        lines.append(f"\n## {q}（优先权≥{after}，命中 {total}）\n")
        for r in rows:
            mark = "" if r["no"] not in seen else "（重复）"
            seen.add(r["no"])
            lines.append(f"- {r['no']} | {r['prio']} | {r['assignee']} | {r['title']}{mark}\n  - {r['snippet']}")
        print(f"{total:>5}  {q}")
        time.sleep(1.5)
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print("saved", OUT.name, "unique", len(seen))


if __name__ == "__main__":
    main()
