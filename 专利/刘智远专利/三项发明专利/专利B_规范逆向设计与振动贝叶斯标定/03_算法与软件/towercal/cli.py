# -*- coding: utf-8 -*-
"""命令行入口。

python -m towercal.cli extract  --tower suspension --ins 5.2
python -m towercal.cli prior    --tower suspension --ins 5.2 --out prior.json
python -m towercal.cli sensors  --tower suspension --ins 5.2 --n 8
python -m towercal.cli demo     --tower suspension --ins 5.2 --out demo.json   # 合成振动数据端到端标定
python -m towercal.cli calibrate --graph g.json --acc acc.npy --fs 20 --nodes 9,15,186 --out post.json

--graph 可读入 towerkit.TrussGraph JSON（任何来源的杆件级桁架模型）；--tower 使用 towerkit 预置合成塔。
"""
from __future__ import annotations

import argparse
import json

import numpy as np

from . import bayes, check, design, excitation, extract, pipeline, sensors  # noqa: F401
from .model import ORDER


def _graph(a):
    import towerkit as tk
    if a.graph:
        g = tk.TrussGraph.load_json(a.graph)
    else:
        g = tk.build_tower(a.tower)
    if a.ins:
        for at in g.meta.get("attach", []):
            if at["kind"] == "conductor":
                at["insulator_len"] = a.ins
    return g


def _dump(obj, path):
    s = json.dumps(obj, ensure_ascii=False, indent=1, default=lambda o: o.tolist() if hasattr(o, "tolist") else str(o))
    if path:
        open(path, "w", encoding="utf-8").write(s)
    else:
        print(s[:4000])


def main(argv=None):
    ap = argparse.ArgumentParser(prog="towercal", description="规范逆向设计 + 振动贝叶斯标定")
    ap.add_argument("cmd", choices=["extract", "prior", "sensors", "demo", "calibrate"])
    ap.add_argument("--tower", default="suspension")
    ap.add_argument("--graph")
    ap.add_argument("--ins", type=float)
    ap.add_argument("--n", type=int, default=8)
    ap.add_argument("--scen", type=int, default=12)
    ap.add_argument("--samples", type=int, default=400)
    ap.add_argument("--acc"); ap.add_argument("--fs", type=float, default=20.0); ap.add_argument("--nodes")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out")
    a = ap.parse_args(argv)
    g = _graph(a)
    if a.cmd == "extract":
        _dump(extract.extract_design_input(g).to_dict(), a.out)
        return
    di, pt, prior = pipeline.prepare(g, n_scen=a.scen, seed=a.seed)
    if a.cmd == "prior":
        _dump({"design_input": di.to_dict(), "groups": prior["groups"], "map": prior["map"],
               "pmf_nonzero": {gr: {ORDER[j]: float(p) for j, p in enumerate(prior["pmf"][k]) if p > 1e-3}
                               for k, gr in enumerate(prior["groups"])}}, a.out)
        return
    if a.cmd == "sensors":
        sel, ld = pipeline.place_sensors(pt, prior["map"], a.n)
        _dump({"efi_nodes": sel, "logdet": ld, "xyz": pt.X[sel].tolist(),
               "empirical_nodes": sensors.empirical_nodes(g, a.n)}, a.out)
        return
    rm = pipeline.reduced_model(pt, prior["map"])
    mix = pipeline.mixture_prior(pt, prior)
    if a.cmd == "demo":
        rng = np.random.default_rng(a.seed)
        jt = np.array([ORDER.index(prior["map"][gr]) for gr in pt.groups])
        jt = np.clip(jt + rng.choice([-1, 0, 0, 0, 1], len(jt)), 0, len(ORDER) - 1)
        tht = (0.8, 10.0)
        fem = pt.as_femodel({gr: ORDER[j] for gr, j in zip(pt.groups, jt)}, tht)
        sel, _ = pipeline.place_sensors(pt, prior["map"], a.n)
        t, acc, _, _ = excitation.ambient_response(fem, sensors.node_dofs(sel), seed=a.seed)
        y, _ = excitation.MemsNoise(seed=a.seed).apply(t, acc)
        fs = 1 / (t[1] - t[0])
    else:
        y = np.load(a.acc); fs = a.fs
        sel = [int(s) for s in a.nodes.split(",")]
    modes, info = pipeline.identify(y, fs)
    res = pipeline.calibrate(pt, rm, modes, sel, mix, n=a.samples, seed=a.seed)
    mj, k, v = pipeline.map_theta(res, len(pt.groups))
    sc = design.Scenario(kV=di.voltage_kV, tower_type=di.tower_type)
    disp, ratio = check.design_response(pt, di, sc, check.sections_from_index(pt, mj), (k, v))
    out = {"identified": [{"f": m["f"], "zeta": m["zeta"]} for m in modes], "sensor_nodes": sel,
           "posterior_map": check.sections_from_index(pt, mj), "kappa_median": k, "logkv_median": v,
           "kappa_90": np.percentile(res["kappa"], [5, 95]).tolist(),
           "logkv_90": np.percentile(res["logkv"], [5, 95]).tolist(),
           "design_top_disp_m": disp, "max_stress_ratio": float(ratio.max()),
           "n_members_ratio_gt_1": int((ratio > 1).sum()), "tmcmc_stages": res["stages"]}
    if a.cmd == "demo":
        out["group_hit_rate"] = float(np.mean(mj == jt))
    _dump(out, a.out)


if __name__ == "__main__":
    main()
