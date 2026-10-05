# -*- coding: utf-8 -*-
"""专利D 仿真验证：5 种塔变体 × 4 种方法 + 停止判据对比（固定 4 轮）+ 电压等级/定位误差安全壳扫描。
输出：../数据/*.json、../图/*.png、../关键结果摘要.json、../../06_附图/无标注版/图5/6/9。"""
import json
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
PD = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(PD, "03_算法与软件"))

from livenbv import pipeline as P  # noqa: E402
from livenbv.safety import SafetyShell, min_distance_dlt409  # noqa: E402

DATA = os.path.join(PD, "04_仿真验证", "数据")
os.makedirs(DATA, exist_ok=True)
VARIANTS = ["standard", "highlow", "missing", "occluded", "combined"]
KEYS = ["coverage", "n_low", "n_low_main", "node_rmse", "node_rmse_observed", "tip_err_pct", "f_err_pct",
        "weighted_deficit", "path_m", "time_s", "n_views", "rounds", "violations", "violations_naive_full_height",
        "stop_reason", "missing_detected", "missing_total", "false_missing", "sym_counts", "min_live_dist"]


def pick(m):
    return {k: m[k] for k in KEYS if k in m}


def main():
    t0 = time.time()
    allres = {}
    keep = {}
    for v in VARIANTS:
        ctx = P.Context(v, seed=0)
        r = {"none": P.run_none(ctx), "uniform": P.run_uniform(ctx), "geo_nbv": P.run_nbv(ctx, False),
             "proposed": P.run_nbv(ctx, True)}
        fixed = P.run_nbv(ctx, True, force_rounds=4, verbose=False)
        allres[v] = {k: pick(x["metrics"]) for k, x in r.items()}
        allres[v]["proposed_fixed4"] = pick(fixed["metrics"])
        allres[v]["history_proposed"] = r["proposed"]["history"]
        allres[v]["history_fixed4"] = fixed["history"]
        allres[v]["shell_radius"] = ctx.shell.radius
        allres[v]["n_candidates"] = int(len(ctx.cand.pos)); allres[v]["n_rejected"] = int(len(ctx.rejected))
        if v in ("combined", "standard"):
            keep[v] = (ctx, r)
        print(v, "done", f"{time.time() - t0:.0f}s")
    # 安全壳参数表
    shell_tab = []
    for kv in (110, 220, 330, 500, 750, 1000):
        for sg in (0.05, 0.5, 1.5):
            s = SafetyShell([], kv=kv, sigma_pos=sg)
            shell_tab.append({"kv": kv, "sigma": sg, "d_min": min_distance_dlt409(kv), "radius": s.radius})
    allres["shell_table"] = shell_tab
    # 安全壳鲁棒性：500 kV + σ=1.5 m 下 combined 塔的本发明（候选更少）
    ctx5 = P.Context("combined", seed=0, kv=500.0, sigma_pos=1.5)
    r5 = P.run_nbv(ctx5, True)
    allres["combined_500kV_sigma1.5"] = pick(r5["metrics"]) | {"shell_radius": ctx5.shell.radius,
                                                               "n_candidates": int(len(ctx5.cand.pos))}
    allres["runtime_s"] = time.time() - t0
    with open(os.path.join(DATA, "results.json"), "w", encoding="utf-8") as f:
        json.dump(allres, f, ensure_ascii=False, indent=1, default=float)
    # 绘图数据
    import pickle
    ctx, r = keep["combined"]
    dump = {"prior_nodes": ctx.sc.prior.nodes, "mi": np.asarray(ctx.sc.prior.mi), "mj": np.asarray(ctx.sc.prior.mj),
            "cat": np.asarray(ctx.sc.prior.cat), "live": ctx.sc.live, "radius": ctx.shell.radius,
            "cand": ctx.cand.pos, "rejected": ctx.rejected, "w": ctx.w,
            "c_init": r["none"]["res"].c, "c_prop": r["proposed"]["res"].c, "c_geo": r["geo_nbv"]["res"].c,
            "path_prop": r["proposed"]["path"], "views_prop": ctx.cand.pos[r["proposed"]["views"]],
            "path_geo": r["geo_nbv"]["path"], "path_uni": r["uniform"]["path"],
            "init_path": ctx.init_tr.pos, "home": P.HOME}
    with open(os.path.join(DATA, "plot_combined.pkl"), "wb") as f:
        pickle.dump(dump, f)
    print("total", time.time() - t0)


if __name__ == "__main__":
    main()
