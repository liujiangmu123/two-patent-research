# -*- coding: utf-8 -*-
"""Round-2 supplementary Google Patents queries for patent 1 (keywords only; no project data sent).
Spacing >= 7 s, one 60 s pause on 503 then skip. Appends to 检索原始数据/search_raw_round2.json."""
import html
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1] / "检索原始数据"
OUT = ROOT / "search_raw_round2.json"
CNT = ROOT / "_req_count.json"

QUERIES = [
    # id, q, after, cpc
    ("R2-01", "杆塔 点云 杆件 置信度", "20180101", None),
    ("R2-02", "杆塔 点云 对称 镜像 补全", "20180101", None),
    ("R2-03", "无人机 带电 安全距离 视点 点云 杆塔 航线", "20180101", None),
    ("R2-04", "下一最佳视点 无人机 激光雷达 重建", "20180101", None),
    ("R2-05", "点云 完整性 评估 补飞 航线 自动 生成 杆塔", "20180101", None),
    ("R2-06", "两台激光雷达 倾斜 安装 无人机 挂载 扫描", "20180101", None),
    ("R2-07", '"next best view" (lidar OR "laser scanner") (UAV OR drone) (tower OR pylon OR truss)', "20180101", None),
    ("R2-08", '"point cloud" (tower OR pylon OR truss) symmetry (completion OR mirror) (asymmetric OR damage OR deformation)', "20180101", None),
    ("R2-09", "杆塔 多期 点云 拓扑 杆件 变化 检测", "20180101", None),
    ("R2-10", "杆塔 无人机", "20180101", "G01S17/89"),
    ("R2-11", "(transmission tower OR pylon) (UAV OR drone) (lidar OR laser) (coverage OR viewpoint) planning", "20180101", None),
    ("R2-12", "激光 点云 点密度 预测 入射角 遮挡 航线 杆塔", "20180101", None),
]


def query(q, after, cpc=None, num=30):
    inner = f"q={q}&after=priority:{after}&num={num}"
    if cpc:
        inner += f"&cpc={cpc}"
    url = "https://patents.google.com/xhr/query?url=" + urllib.parse.quote(inner, safe="") + "&exp="
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=45) as r:
        data = json.loads(r.read().decode("utf-8"))
    rows = []
    clean = lambda s: re.sub(r"<[^>]+>", "", html.unescape(s or "")).strip()
    for cl in data.get("results", {}).get("cluster", []):
        for item in cl.get("result", []):
            p = item.get("patent", {})
            rows.append({
                "no": p.get("publication_number"), "title": clean(p.get("title")),
                "assignee": clean(p.get("assignee")), "prio": p.get("priority_date"),
                "pub": p.get("publication_date"), "snippet": clean(p.get("snippet"))[:300],
            })
    return data.get("results", {}).get("total_num_results"), rows


def main():
    ids = set(sys.argv[1:])
    res = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else []
    done = {r["id"] for r in res if r.get("rows")}
    cnt = json.loads(CNT.read_text(encoding="utf-8"))
    for qid, q, after, cpc in QUERIES:
        if (ids and qid not in ids) or qid in done:
            continue
        rec = {"id": qid, "q": q, "after": after, "cpc": cpc, "date": time.strftime("%Y-%m-%d")}
        for attempt in range(2):
            cnt["search"] += 1
            try:
                total, rows = query(q, after, cpc)
                rec.update(total=total, rows=rows)
                print(f"{qid} ok total={total} rows={len(rows)}")
                break
            except Exception as e:
                rec.update(error=str(e))
                print(f"{qid} FAIL {e}")
                if "503" in str(e) and attempt == 0:
                    time.sleep(60)
                    continue
                break
        res = [r for r in res if r["id"] != qid] + [rec]
        OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
        cnt["log"].append({"id": qid, "ok": "rows" in rec, "date": rec["date"]})
        CNT.write_text(json.dumps(cnt, ensure_ascii=False, indent=1), encoding="utf-8")
        time.sleep(7)


if __name__ == "__main__":
    main()
