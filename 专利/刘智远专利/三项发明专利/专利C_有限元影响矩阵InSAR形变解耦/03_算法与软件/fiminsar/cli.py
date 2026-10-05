# -*- coding: utf-8 -*-
"""命令行：python -m fiminsar.cli {demo,influence,dopt} ..."""
from __future__ import annotations

import argparse
import json

import numpy as np

from . import invert as INV
from . import model as MD
from . import sim as S

VZ = [2, 5, 8, 11]


def cmd_influence(a):
    M = MD.build_model(a.tower)
    top = int(np.argmax(M.X[:, 2]))
    G = M.Gb.reshape(-1, 6, 12)[top, :3] * 1e3
    print(json.dumps({"tower": a.tower, "H": M.H, "nodes": M.g.n_nodes, "members": M.g.n_members,
                      "top_disp_mm_per_mm_leg_z": G[:, VZ].round(3).tolist(),
                      "top_thermal_mm_per_K": (M.GT1.reshape(-1, 6)[top, :3] * 1e3).round(4).tolist()}, indent=1))


def cmd_demo(a):
    M = MD.build_model(a.tower)
    ep = S.build_epochs(M, sat=a.sat, n_per_geom=a.epochs, seed=a.seed)
    B = S.settlement_truth(ep.t, tuple(a.legs), onset=ep.t.mean())
    d = S.synthesize(M, ep, S.Scenario(B=B, n_ps=a.nps, noise=a.noise, seed=a.seed + 1))
    r, th = S.method_proposed(M, d)
    idx = [E.index for E in d["epochs"]]
    last = int(np.argmax(r.times))
    tilt, _ = INV.foundation_tilt(M.X[M.base, :2], r.b[last, VZ])
    std_t = float(np.mean(r.b_std[last, VZ]) * 1e3 / np.ptp(M.X[M.base, 0]))
    out = {"final_leg_z_mm_est": (r.b[last, VZ] * 1e3).round(2).tolist(),
           "final_leg_z_mm_true": (B[idx][last, VZ] * 1e3).round(2).tolist(),
           "std_mm": (r.b_std[last, VZ] * 1e3).round(2).tolist(),
           "foundation_tilt_permille": round(tilt, 3),
           "top_tilt_permille": round(INV.top_tilt(M, r.b[last]), 3),
           "warning": INV.warning_level(INV.top_tilt(M, r.b[last]), std_t),
           "thermal_explained": round(S.thermal_explained(d, th), 3), "assoc": d["assoc"]}
    print(json.dumps(out, ensure_ascii=False, indent=1))
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=1)


def cmd_dopt(a):
    M = MD.build_model(a.tower)
    lv = np.asarray(M.g.meta["levels"])
    cand = [i for i, t in enumerate(M.g.ntype) if t == "corner" and M.X[i, 2] < lv[8] + 0.1]
    geo = S.SC.geometries(a.sat)
    Hc = np.array([[g.los @ M.point_rows([q])[0] @ M.Gb for g in geo] for q in cand])
    R = np.diag([1 / 0.004 ** 2 if j not in VZ else 1e-6 for j in range(12)])
    sel, Mi = INV.d_optimal(Hc, a.m, R=R, sigma=1e-3)
    print(json.dumps({"nodes": [cand[c] for c in sel], "xyz": M.X[[cand[c] for c in sel]].round(2).tolist(),
                      "post_std_mm": (np.sqrt(np.diag(np.linalg.inv(Mi)))[VZ] * 1e3).round(3).tolist()}, indent=1))


def main(argv=None):
    p = argparse.ArgumentParser(prog="fiminsar", description="有限元影响矩阵 InSAR 形变解耦与基础沉降反演")
    sp = p.add_subparsers(dest="cmd", required=True)
    q = sp.add_parser("influence", help="构建影响矩阵并打印塔顶影响系数"); q.add_argument("--tower", default="suspension")
    q.set_defaults(f=cmd_influence)
    q = sp.add_parser("demo", help="合成升降轨时序并反演")
    q.add_argument("--tower", default="suspension"); q.add_argument("--sat", default="FC1", choices=["FC1", "S1"])
    q.add_argument("--epochs", type=int, default=12); q.add_argument("--nps", type=int, default=12)
    q.add_argument("--noise", type=float, default=1.0); q.add_argument("--seed", type=int, default=0)
    q.add_argument("--legs", type=float, nargs=4, default=[-10, -2, -1, -2]); q.add_argument("--out")
    q.set_defaults(f=cmd_demo)
    q = sp.add_parser("dopt", help="D 最优角反射器布设"); q.add_argument("--tower", default="suspension")
    q.add_argument("--sat", default="FC1"); q.add_argument("-m", type=int, default=4); q.set_defaults(f=cmd_dopt)
    a = p.parse_args(argv)
    a.f(a)


if __name__ == "__main__":
    main()
