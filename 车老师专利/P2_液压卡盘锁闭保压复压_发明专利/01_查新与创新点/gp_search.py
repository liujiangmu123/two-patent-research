# -*- coding: utf-8 -*-
"""Google Patents 公开检索接口批量检索（只传检索式，不传项目资料）。
请求间隔 >=25 s；遇 503/429 等待 300 s 后重试一次。结果写 检索原始数据/gp_<序号>.json 与 gp_汇总.json。
用法：.venv\\Scripts\\python.exe 01_查新与创新点\\gp_search.py [起始序号]
"""
import json
import os
import sys
import time
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "检索原始数据")
os.makedirs(OUT, exist_ok=True)

Q = [
    # 英文
    ("E01", "(chuck) (\"rotary cylinder\") (\"check valve\") (\"clamping pressure\") (detect OR monitor OR determine)"),
    ("E02", "(chuck) (\"rotary cylinder\") (\"check valve\") (\"rotary joint\" OR \"distributor\") (\"pressure sensor\")"),
    ("E03", "(chuck) (\"clamping force\") (monitor OR monitoring) (\"rotary joint\" OR \"rotary union\") (pressure) (leakage)"),
    ("E04", "(\"check valve\") (\"cracking pressure\" OR \"opening pressure\") (\"pressure rise\" OR \"pressure increase\") (slope OR gradient OR \"rate of change\") (determine OR detect)"),
    ("E05", "(\"trapped pressure\" OR \"locked pressure\" OR \"holding pressure\") (\"check valve\") (estimate OR determine) (\"rate of pressure\" OR slope OR gradient)"),
    ("E06", "(accumulator) (\"pre-charge\" OR precharge) (\"rate of pressure change\" OR \"pressure gradient\") (transition OR kink OR inflection)"),
    ("E07", "(chuck) (centrifugal) (\"clamping force\" OR \"gripping force\") (\"spindle speed\" OR rotational speed) (pressure) (minimum OR lower limit)"),
    ("E08", "(chuck) (hydraulic) (\"check valve\") (\"rotary joint\" OR \"rotary union\") (depressurize OR \"pressure relief\" OR unload) (energy OR leakage)"),
    ("E09", "(clamping fixture OR pallet) (\"check valve\") (decoupled OR uncoupled OR disconnected) (pressure) (monitor OR check) (recouple OR reconnect OR docking)"),
    ("E10", "(\"pilot operated check valve\" OR \"load holding valve\") (\"load pressure\") (estimate OR determine) (\"pump pressure\") (opening OR open)"),
    ("E11", "(chuck OR \"clamping cylinder\") (\"check valve\") (pressure) (\"flow rate\" OR \"flow control\") (repressurize OR \"re-pressurize\" OR replenish OR recharge) (interval OR timing)"),
    ("E12", "(rotating cylinder OR \"rotary cylinder\") (\"pressure\") (wireless OR telemetry OR inductive OR \"slip ring\") (\"clamping force\" OR \"clamping pressure\")"),
    ("E13", "(\"leakage rate\") (\"check valve\") (cylinder) (pressure decay) (estimate) (\"refill\" OR \"replenish\") (volume)"),
    # 中文
    ("C01", "(卡盘) (回转油缸) (单向阀) (夹紧力 OR 夹紧压力) (检测 OR 监测)"),
    ("C02", "(卡盘) (回转接头 OR 配油器 OR 旋转接头) (泄漏) (卸压 OR 泄压 OR 中位) (单向阀 OR 液压锁)"),
    ("C03", "(夹紧) (单向阀 OR 液压锁) (保压) (补压 OR 复压 OR 补油) (压力传感器) (间隔 OR 周期 OR 时间)"),
    ("C04", "(单向阀) (开启压力) (压力上升 OR 升压) (斜率 OR 拐点 OR 突变)"),
    ("C05", "(蓄能器) (预充压力 OR 充气压力) (拐点 OR 斜率 OR 转折) (检测 OR 判断)"),
    ("C06", "(卡盘) (离心力) (夹紧力) (转速) (压力) (补偿 OR 下限)"),
    ("C07", "(回转油缸 OR 旋转油缸) (压力) (无线 OR 滑环 OR 非接触) (夹紧力)"),
    ("C08", "(液压缸) (封闭腔 OR 锁闭腔) (压力) (间接) (测量 OR 估算) (单向阀)"),
    ("C09", "(卡盘) (夹紧) (泄漏量) (估算 OR 计算) (补油) (压力)"),
    # 日文
    ("J01", "(チャック) (回転シリンダ) (逆止弁 OR チェック弁) (把持力 OR 把持圧) (検出)"),
    ("J02", "(逆止弁) (開弁圧 OR クラッキング圧) (圧力上昇) (検出 OR 判定)"),
    ("J03", "(チャック) (把持力) (遠心力) (回転数) (油圧) (補正 OR 下限)"),
    ("J04", "(回転シリンダ) (ロータリジョイント OR 回転継手) (漏れ) (圧力) (保持 OR ロック)"),
]


def fetch(q):
    inner = "q=" + q + "&num=20"
    url = "https://patents.google.com/xhr/query?url=" + urllib.parse.quote(inner, safe="") + "&exp="
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (patent search, low rate)"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def brief(js):
    out = []
    try:
        for cl in js["results"]["cluster"]:
            for r in cl.get("result", []):
                p = r.get("patent", {})
                out.append({k: p.get(k) for k in ("publication_number", "title", "assignee", "priority_date",
                                                  "filing_date", "publication_date", "snippet", "inventor")})
    except Exception as e:
        out.append({"error": str(e)})
    return out


def main(start=0):
    summ_f = os.path.join(OUT, "gp_汇总.json")
    summ = json.load(open(summ_f, encoding="utf-8")) if os.path.exists(summ_f) else {}
    for i, (qid, q) in enumerate(Q):
        if i < start or (qid in summ and "error" not in summ[qid]):
            continue
        for attempt in range(2):
            try:
                js = fetch(q)
                res = brief(js)
                summ[qid] = {"q": q, "total": js.get("results", {}).get("total_num_results"), "results": res,
                             "time": time.strftime("%Y-%m-%d %H:%M:%S")}
                print(qid, summ[qid]["total"], flush=True)
                break
            except Exception as e:
                print(qid, "error", e, flush=True)
                if attempt == 0:
                    time.sleep(300)
                else:
                    summ[qid] = {"q": q, "error": str(e)}
        json.dump(summ, open(summ_f, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        time.sleep(25)
    print("done", flush=True)


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 0)
