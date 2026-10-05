# -*- coding: utf-8 -*-
"""专利1 查新检索（Google Patents xhr 查询接口，只发送关键词）。

纪律：请求间隔 >= 7 s；HTTP 503 暂停 90 s 后重试一次；本脚本请求上限 28 次
（另留 12 次给详情抓取，合计 <= 40）。
输出：01_调研与查新/检索原始数据/search_raw.json、search_raw.md
运行：.venv\\Scripts\\python.exe <本文件>
"""
import json
import sys
import time
import urllib.error
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
P1 = HERE.parent
TOOLS = P1.parent / "00_共享" / "工具"
sys.path.insert(0, str(TOOLS))
from patent_search import query  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")
OUT_DIR = P1 / "01_调研与查新" / "检索原始数据"
OUT_DIR.mkdir(parents=True, exist_ok=True)

QUERIES = [
    # ---- 中文 ----
    ("Q01", "无人机 激光雷达 杆塔 三维重建 航线", "20180101"),
    ("Q02", "无人机 激光 铁塔 补测 OR 补飞 OR 补扫", "20180101"),
    ("Q03", "无人机 点云 杆塔 自适应 航线 精细化", "20180101"),
    ("Q04", "双激光雷达 倾斜 无人机 载荷", "20180101"),
    ("Q05", "两个激光雷达 对称 倾斜 扫描 无人机", "20180101"),
    ("Q06", "激光雷达 扫描平面 旋转 调节 无人机 吊舱", "20180101"),
    ("Q07", "点云 缺失 区域 补飞 航线 无人机 重建", "20180101"),
    # 第2轮（首轮 Q02/Q04/Q05 含 OR 或泛词导致噪声，后续检索式改为精确词组合，并删去 Q15/Q21/Q26 以控制请求数）
    ("Q08", "点云 不确定性 视点 规划 无人机 三维重建", "20180101"),
    ("Q09", "下一最佳视点 激光 三维重建", "20180101"),
    ("Q10", "点云 置信度 杆件 输电塔", "20190101"),
    ("Q11", "铁塔 点云 对称 杆件 缺失 检测", "20190101"),
    ("Q12", "杆塔 点云 长短腿 重建", "20190101"),
    ("Q13", "输电线路 无人机 安全距离 航线 点云 带电", "20190101"),
    ("Q14", "机载 边缘计算 实时 点云 航线 调整 无人机", "20190101"),
    ("Q16", "激光雷达 倾斜 安装 无人机 杆塔 扫描", "20180101"),
    # ---- 英文 ----
    ("Q17", "UAV LiDAR \"transmission tower\" reconstruction \"flight path\" adaptive", "20180101"),
    ("Q18", "\"next best view\" UAV LiDAR reconstruction", "20180101"),
    ("Q19", "\"view planning\" \"point cloud\" uncertainty UAV structure inspection", "20180101"),
    ("Q20", "\"unmanned aerial vehicle\" \"two lidar\" tilted", "20180101"),
    ("Q22", "truss \"point cloud\" symmetry completion occlusion", "20180101"),
    ("Q23", "\"power line\" UAV LiDAR \"safety distance\" path planning tower", "20180101"),
    ("Q24", "UAV reconstruction \"point cloud\" rescan waypoint quality", "20180101"),
    ("Q25", "\"transmission tower\" \"point cloud\" confidence member", "20180101"),
]

MAX_REQ = 28          # 检索请求累计上限（跨多次运行累计，见 _req_count.json）
GAP = 10.0
COUNT_PATH = OUT_DIR / "_req_count.json"
SKIP = set(sys.argv[1:])  # 可在命令行传入要跳过的检索式编号


def _load_count():
    if COUNT_PATH.exists():
        return json.loads(COUNT_PATH.read_text(encoding="utf-8"))
    return {"search": 0, "detail": 0, "log": []}


def main():
    cnt = _load_count()
    raw_path = OUT_DIR / "search_raw.json"
    results = json.loads(raw_path.read_text(encoding="utf-8")) if raw_path.exists() else []
    done = {r["id"] for r in results if r.get("ok")}
    results = [r for r in results if r.get("ok")]          # 失败记录在重跑时覆盖
    consecutive_503 = 0
    for qid, q, after in QUERIES:
        if qid in done or qid in SKIP:
            continue
        if cnt["search"] >= MAX_REQ:
            print("达到请求上限，停止")
            break
        rec = {"id": qid, "q": q, "after": after, "date": date.today().isoformat()}
        for attempt in (1, 2):
            cnt["search"] += 1
            try:
                total, rows = query(q, after, num=30)
                rec.update(total=total, rows=rows, ok=True)
                consecutive_503 = 0
                print(f"{qid} 命中 {total} 返回 {len(rows)}  {q}", flush=True)
                break
            except urllib.error.HTTPError as e:
                rec.update(ok=False, error=f"HTTP {e.code}")
                print(f"{qid} HTTP {e.code}", flush=True)
                if e.code == 503:
                    consecutive_503 += 1
                if e.code == 503 and attempt == 1 and cnt["search"] < MAX_REQ:
                    time.sleep(90)
                    continue
                break
            except Exception as e:  # 网络异常：记录后继续
                rec.update(ok=False, error=str(e))
                print(f"{qid} FAIL {e}", flush=True)
                break
        cnt["log"].append({"id": qid, "ok": rec.get("ok", False), "date": rec["date"]})
        COUNT_PATH.write_text(json.dumps(cnt, ensure_ascii=False, indent=1), encoding="utf-8")
        results.append(rec)
        raw_path.write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
        if consecutive_503 >= 2:
            print("连续 503，暂停本轮检索（稍后重跑本脚本即可续检）", flush=True)
            break
        time.sleep(GAP)

    results.sort(key=lambda r: r["id"])
    lines = [f"# 专利1 检索原始结果（{date.today().isoformat()}，累计检索请求 {cnt['search']} 次）\n"]
    for r in results:
        lines.append(f"\n## {r['id']} {r['q']}（优先权≥{r['after']}，命中 {r.get('total', '失败:' + r.get('error', ''))}）\n")
        for x in r.get("rows", []):
            lines.append(f"- {x['no']} | {x['prio']} | {x['assignee']} | {x['title']}\n  - {x['snippet']}")
    (OUT_DIR / "search_raw.md").write_text("\n".join(lines), encoding="utf-8")
    print("完成，累计检索请求数", cnt["search"])


if __name__ == "__main__":
    main()
