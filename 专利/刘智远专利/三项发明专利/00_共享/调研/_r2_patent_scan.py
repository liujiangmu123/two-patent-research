# -*- coding: utf-8 -*-
"""R2 prior-art scan: keyword queries only (no project data sent). Spacing >=7 s, stop 60 s on 503."""
import json
import sys
import time
import urllib.error
from pathlib import Path

TOOL = Path(r"h:\Axinjihua\02动画项目\05动画Harness工作台\专利文档资料\专利\刘智远专利\三项发明专利\00_共享\工具")
sys.path.insert(0, str(TOOL))
sys.stdout.reconfigure(encoding="utf-8")
from patent_search import query  # noqa: E402

OUT = Path(__file__).resolve().parent / "_R2_patent_raw.json"
MODE = sys.argv[1] if len(sys.argv) > 1 else "search"

QUERIES = [
    ("无人机 激光雷达 输电塔 有限元", "20190101"),
    ("输电塔 振动 非接触 测量", "20190101"),
    ("调频连续波 激光雷达 振动 测量", "20190101"),
    ("输电塔 模态 识别 模型修正", "20190101"),
    ("输电塔 截面 识别 点云 角钢", "20190101"),
    ("无人机 双 激光雷达 倾斜 扫描 吊舱", "20190101"),
    ("输电塔 振动 监测 加速度 无线 节点", "20190101"),
    ("毫米波雷达 输电塔 振动", "20190101"),
    ('"coherent lidar" OR "FMCW lidar" vibration structure "radial velocity"', "20190101"),
    ('"transmission tower" modal "model updating"', "20180101"),
    ('"laser doppler vibrometer" (UAV OR drone) structure vibration', "20180101"),
    ("杆塔 点云 安全距离 航线 补测", "20190101"),
    ("输电塔 视觉 振动 位移 模态", "20190101"),
    ("激光雷达 径向速度 点云 模态", "20190101"),
    ("铁塔 点云 设计 呼高 转角 规范 反演", "20190101"),
    ("格构塔 环境振动 有限元 修正 刚度 基础", "20180101"),
]


def run_search():
    res = []
    n = 0
    for q, after in QUERIES:
        n += 1
        try:
            total, rows = query(q, after, 20)
            res.append({"q": q, "after": after, "total": total, "rows": rows})
            print(f"{total}\t{q}", flush=True)
        except urllib.error.HTTPError as e:
            res.append({"q": q, "after": after, "error": str(e)})
            print("ERR", e.code, q, flush=True)
            if e.code == 503:
                time.sleep(60)
        except Exception as e:  # noqa: BLE001
            res.append({"q": q, "after": after, "error": str(e)})
            print("ERR", q, e, flush=True)
        time.sleep(7)
    OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print("requests", n, "saved", OUT, flush=True)


def run_detail(nums):
    from patent_detail import fetch
    out = Path(__file__).resolve().parent / "_R2_patent_detail.json"
    res = {}
    if out.exists():
        res = json.loads(out.read_text(encoding="utf-8"))
    for no in nums:
        try:
            res[no] = fetch(no)
            print("ok", no, res[no]["title"][:50], res[no]["status"], flush=True)
        except urllib.error.HTTPError as e:
            res[no] = {"error": str(e)}
            print("ERR", no, e, flush=True)
            if e.code == 503:
                time.sleep(60)
        except Exception as e:  # noqa: BLE001
            res[no] = {"error": str(e)}
            print("ERR", no, e, flush=True)
        time.sleep(7)
    out.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print("saved", out, flush=True)


if __name__ == "__main__":
    if MODE == "search":
        run_search()
    else:
        run_detail(sys.argv[2:])
