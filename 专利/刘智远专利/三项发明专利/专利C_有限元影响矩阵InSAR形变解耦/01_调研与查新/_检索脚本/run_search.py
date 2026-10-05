# -*- coding: utf-8 -*-
"""专利2 查新：Google Patents 关键词检索（仅发送关键词，不发送项目数据）。

限速：每次请求间隔 >= 6.5 s；遇 503 暂停 90 s 后重试一次；本脚本请求上限 MAX_REQ。
结果写入 ../_raw/search_raw.json（逐条累积，可断点续跑）。
用法：.venv\\Scripts\\python.exe <本文件> [起始序号]
"""
import json
import sys
import time
import urllib.error
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOLS = HERE.parents[2] / "00_共享" / "工具"
sys.path.insert(0, str(TOOLS))
import patent_search  # noqa: E402

RAW = HERE.parent / "_raw"
RAW.mkdir(exist_ok=True)
OUT = RAW / "search_raw.json"
LOG = RAW / "request_log.json"   # 跨运行累计的请求计数（检索 + 详情共用，总上限 40）
TOTAL_CAP = 40
MAX_REQ = 26
GAP = 12


def _load_log():
    return json.loads(LOG.read_text(encoding="utf-8")) if LOG.exists() else {"used": 0, "events": []}


def _bump(log, what, status):
    log["used"] += 1
    log["events"].append({"t": time.strftime("%Y-%m-%d %H:%M:%S"), "what": what, "status": status})
    LOG.write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8")

QUERIES = [
    ("S01", "(输电塔 OR 铁塔 OR 杆塔) InSAR 有限元 沉降 反演", "20150101"),
    ("S02", "(输电塔 OR 铁塔 OR 杆塔) (永久散射体 OR PS点) 形变 温度", "20150101"),
    ("S03", "(输电塔 OR 铁塔 OR 杆塔) 角反射器", "20150101"),
    ("S04", "角反射器 (角钢 OR 抱箍 OR 夹持 OR 夹具) 安装", "20150101"),
    ("S05", "角反射器 升轨 降轨 (双向 OR 两个 OR 背靠背)", "20150101"),
    ("S06", "InSAR (影响矩阵 OR 单位位移 OR 格林函数) 结构 反演", "20150101"),
    ("S07", "InSAR 热膨胀 温度 形变 分离 (桥梁 OR 结构 OR 建筑)", "20150101"),
    ("S08", "InSAR 有限元 模型 (同化 OR 修正 OR 更新) 结构 形变", "20150101"),
    ("S09", "(塔腿 OR 杆塔基础) 不均匀沉降 有限元 (反演 OR 识别)", "20150101"),
    ("S10", "(输电塔 OR 铁塔) 日照 温度场 有限元", "20150101"),
    ("S11", "(输电塔 OR 杆塔 OR 塔基) (冻胀 OR 融沉) InSAR", "20150101"),
    ("S12", "点云 距离多普勒 散射 仿真 (铁塔 OR 塔 OR 桥梁) InSAR", "20150101"),
    ("S13", "InSAR 卡尔曼 (结构 OR 杆塔) 形变 预警 (应力 OR 倾斜)", "20150101"),
    ("S14", "(角反射器 OR 测点) 布设 优化 (Fisher OR 信息矩阵 OR D最优) 形变", "20150101"),
    ("S15", "(输电塔 OR 杆塔) 倾斜 InSAR 升轨 降轨", "20150101"),
    ("S16", "(输电塔 OR 杆塔) InSAR 杆件 应力 预警", "20150101"),
    ("S17", "(输电塔 OR 铁塔) 角钢 温度传感器 (阴面 OR 阳面 OR 夹持)", "20150101"),
    ("S18", '"transmission tower" InSAR "finite element"', "20150101"),
    ("S19", '"corner reflector" (pylon OR "lattice tower" OR "angle steel") (clamp OR bracket)', "20150101"),
    ("S20", '"persistent scatterer" "thermal expansion" structure', "20150101"),
    ("S21", 'InSAR "finite element" settlement inversion structure', "20150101"),
    ("S22", '"corner reflector" ascending descending dual', "20150101"),
    ("S23", '"synthetic aperture radar" interferometry bridge temperature "thermal dilation"', "20150101"),
    ("S24", "(杆塔 OR 铁塔) 塔脚 (地表 OR 周边) 相干点 InSAR 沉降", "20150101"),
    ("S25", "(SAR OR InSAR) 角反射器 杆塔 (冻土 OR 基础) 监测 装置", "20150101"),
]


def main():
    only = sys.argv[1:]  # 可指定检索式编号子集
    data = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    log = _load_log()
    nreq = 0
    fails_in_row = 0
    for qid, q, after in QUERIES:
        if only and qid not in only:
            continue
        if qid in data and data[qid].get("ok"):
            continue
        if nreq >= MAX_REQ or log["used"] >= TOTAL_CAP - 12:  # 为详情抓取预留 12 次
            print("reach cap, stop")
            break
        ok = False
        for attempt in (1, 2):
            nreq += 1
            try:
                total, rows = patent_search.query(q, after, 30)
                _bump(log, qid, "ok")
                data[qid] = {"q": q, "after": after, "date": str(date.today()), "ok": True,
                             "total": total, "rows": rows}
                print(f"{qid} total={total} n={len(rows)}", flush=True)
                ok = True
                break
            except urllib.error.HTTPError as e:
                _bump(log, qid, f"HTTP {e.code}")
                print(f"{qid} HTTP {e.code}", flush=True)
                data[qid] = {"q": q, "after": after, "date": str(date.today()), "ok": False,
                             "err": f"HTTP {e.code}"}
                if e.code == 503 and attempt == 1:
                    time.sleep(90)
                    continue
                break
            except Exception as e:  # noqa: BLE001
                _bump(log, qid, f"ERR {e}")
                print(f"{qid} FAIL {e}", flush=True)
                data[qid] = {"q": q, "after": after, "date": str(date.today()), "ok": False,
                             "err": str(e)}
                break
        OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        fails_in_row = 0 if ok else fails_in_row + 1
        if fails_in_row >= 2:
            print("two queries failed in a row, stop (circuit breaker)")
            break
        time.sleep(GAP)
    print("requests this run:", nreq, "total used:", log["used"])


if __name__ == "__main__":
    main()
