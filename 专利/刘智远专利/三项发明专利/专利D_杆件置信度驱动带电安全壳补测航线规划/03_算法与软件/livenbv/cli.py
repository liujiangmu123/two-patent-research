# -*- coding: utf-8 -*-
"""命令行：python -m livenbv.cli run --variant combined --kv 220 --sigma 0.5 --method proposed
          python -m livenbv.cli shell --kv 500 --sigma 0.5"""
import argparse
import json

import numpy as np


def main(argv=None):
    ap = argparse.ArgumentParser(prog="livenbv")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="合成塔端到端补测仿真")
    r.add_argument("--variant", default="standard", choices=["standard", "highlow", "missing", "occluded", "combined"])
    r.add_argument("--kv", type=float, default=220.0)
    r.add_argument("--sigma", type=float, default=0.5, help="定位误差 1σ (m)")
    r.add_argument("--method", default="proposed", choices=["none", "uniform", "geo_nbv", "proposed", "all"])
    r.add_argument("--seed", type=int, default=0)
    r.add_argument("--out", default=None, help="结果 JSON 路径")
    s = sub.add_parser("shell", help="打印安全壳半径构成")
    s.add_argument("--kv", type=float, default=220.0)
    s.add_argument("--sigma", type=float, default=0.5)
    a = ap.parse_args(argv)
    if a.cmd == "shell":
        from .safety import SafetyShell
        sh = SafetyShell([], kv=a.kv, sigma_pos=a.sigma)
        print(json.dumps({"kv": a.kv, "d_min_DLT409": sh.d_min, "k_sigma": sh.k_sigma * sh.sigma_pos,
                          "gust": sh.gust_drift, "r_uav": sh.r_uav, "radius": sh.radius}, ensure_ascii=False))
        return
    from . import pipeline as P
    ctx = P.Context(a.variant, seed=a.seed, kv=a.kv, sigma_pos=a.sigma)
    fns = {"none": P.run_none, "uniform": P.run_uniform, "geo_nbv": lambda c: P.run_nbv(c, False),
           "proposed": lambda c: P.run_nbv(c, True)}
    ms = fns if a.method == "all" else {a.method: fns[a.method]}
    out = {k: f(ctx)["metrics"] for k, f in ms.items()}
    txt = json.dumps(out, ensure_ascii=False, indent=1, default=lambda x: x.tolist() if isinstance(x, np.ndarray) else float(x))
    print(txt)
    if a.out:
        open(a.out, "w", encoding="utf-8").write(txt)


if __name__ == "__main__":
    main()
