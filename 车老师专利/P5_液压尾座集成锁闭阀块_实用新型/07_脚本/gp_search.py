# -*- coding: utf-8 -*-
r"""P5 查新：Google Patents xhr 检索（请求间隔 ≥25 s，遇 503 等 300 s 后重试一次）。

用法：.venv\Scripts\python.exe 07_脚本\gp_search.py [查询组名...]
输出：01_查新与创新点\检索原始结果\gp_<组名>.json（每条：公开号、标题、申请人、优先权日、公开日、摘要片段）
"""
import json
import os
import sys
import time
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "01_查新与创新点", "检索原始结果")
os.makedirs(OUT, exist_ok=True)

# 检索式（Google Patents 语法：括号内为同义词 OR，空格为 AND）
QUERIES = {
    "Q01_缸装阀块_负载保持": "(cylinder) (valve block OR manifold) (mounted directly OR directly mounted OR flange mounted) (load holding OR blocking valve OR hose burst) (pressure sensor OR pressure transducer)",
    "Q02_缸装阀块_两腔座阀": "(hydraulic cylinder) (valve block) (both chambers OR piston side and rod side) (poppet valve OR seat valve) (cartridge) (pressure sensor)",
    "Q03_阀块_温度传感器套管": "(hydraulic) (valve block OR manifold) (temperature sensor) (thermowell OR sleeve OR protective tube) (pressure sensor) (cylinder)",
    "Q04_尾座油缸_阀块": "(tailstock) (hydraulic cylinder) (valve block OR manifold OR solenoid valve) (pressure sensor)",
    "Q05_中文_油缸集成阀块": "(油缸 OR 液压缸) (阀块 OR 集成块) (直接安装 OR 固定安装 OR 安装于缸筒) (液压锁 OR 锁紧阀 OR 保压) (压力传感器)",
    "Q06_中文_插装座阀集成块": "(插装 OR 螺纹插装) (座阀 OR 锥阀 OR 球阀) (集成块 OR 阀块) (油缸 OR 液压缸) (保压) (压力传感器)",
    "Q07_中文_温度传感器阀块": "(阀块 OR 集成块) (温度传感器) (压力传感器) (油缸 OR 液压缸) (测压接头 OR 排气)",
    "Q08_中文_尾座油缸": "(尾座 OR 尾架) (油缸 OR 液压缸) (阀块 OR 电磁阀) (保压 OR 锁紧) (压力传感器 OR 压力继电器)",
    "Q09_日文_シリンダ直付け": "(シリンダ) (バルブブロック OR マニホールド) (直付け OR 一体 OR 取り付け) (圧力センサ) (保持)",
    "Q10_死容积_刚度": "(hydraulic cylinder) (valve) (dead volume OR trapped volume OR oil volume between valve and cylinder) (stiffness OR natural frequency) (mounted on cylinder)",
    "Q11_阻尼孔螺塞_阀块": "(orifice plug OR orifice insert OR replaceable orifice) (manifold OR valve block) (cylinder) (poppet valve) (tank)",
    "Q12_中文_双腔锁闭阀块": "(液压缸) (无杆腔 AND 有杆腔) (阀块) (电磁球阀 OR 电磁座阀 OR 二通插装阀) (压力传感器)",
}


def query(q, num=20):
    inner = "q=" + urllib.parse.quote(q) + "&num=%d" % num
    url = "https://patents.google.com/xhr/query?url=" + urllib.parse.quote(inner) + "&exp="
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                                               "Accept": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=60).read().decode("utf-8"))


def run(name, q):
    for attempt in range(2):
        try:
            j = query(q)
            break
        except Exception as e:  # noqa: BLE001
            print(name, "ERR", e, flush=True)
            if "503" in str(e) and attempt == 0:
                time.sleep(300)
                continue
            return None
    res = []
    for cl in j.get("results", {}).get("cluster", []):
        for x in cl.get("result", []):
            p = x.get("patent", {})
            res.append({k: p.get(k) for k in ("publication_number", "title", "assignee", "inventor", "priority_date",
                                               "filing_date", "publication_date", "grant_date", "snippet", "language")})
    out = {"查询": q, "检索时间": time.strftime("%Y-%m-%d %H:%M"), "总数": j.get("results", {}).get("total_num_results"),
           "结果": res}
    with open(os.path.join(OUT, "gp_%s.json" % name), "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    print(name, "ok", len(res), flush=True)
    return out


if __name__ == "__main__":
    names = sys.argv[1:] or list(QUERIES)
    for i, n in enumerate(names):
        if i:
            time.sleep(25)
        run(n, QUERIES[n])
