# -*- coding: utf-8 -*-
"""开发诊断：逐杆件误差分布（朝向、肢宽、偏心、存在）。"""
import os
import pickle
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "03_算法与软件"))
from anglegs import metrics as ME  # noqa: E402
from anglegs import pipeline as PL  # noqa: E402
from anglegs.surfels import sigmoid  # noqa: E402

LOG = print if os.environ.get("VERBOSE") else (lambda *a: None)
sc = PL.SceneCfg(seed=1)
scene = PL.Scene(sc, log=LOG)
U = scene.U
t0 = time.time()
from dataclasses import replace as _rep  # noqa: E402
cfg = PL.VARIANTS[sys.argv[1] if len(sys.argv) > 1 else "本发明"]
if os.environ.get("ITER"):
    cfg = _rep(cfg, iter_mult=float(os.environ["ITER"]))
run = PL.run_variant(scene, cfg, log=print)
m = run["metrics"]
print({k: (round(v, 4) if isinstance(v, float) else v) for k, v in m.items() if k not in ("topology", "ext_est")},
      f"{time.time() - t0:.0f}s")
P = run["P"]
pi = np.asarray(sigmoid(P["logit"]))
cat = np.array(U.cat)
print("damaged:", [(int(e), U.cat[e], U.part[e], round(float(pi[e]), 3), round(float(P["b"][e]), 3)) for e in U.damaged])
print("false neg:", [(int(e), round(float(pi[e]), 3)) for e in U.false_neg])
sp = np.flatnonzero(U.is_cand & ~np.isin(np.arange(U.n_members), U.false_neg))
print("spurious pi:", np.round(pi[sp], 3))
oe, _, _ = ME.opening_dir(P["V"], U.mi, U.mj, U.r, P["phi"])
ot, _, _ = ME.opening_dir(U.nodes_true, U.mi, U.mj, U.r, U.phi)
o0, _, _ = ME.opening_dir(scene.init["V"], U.mi, U.mj, U.r, scene.init["phi"])
ang = np.degrees(np.arccos(np.clip(np.sum(oe * ot, 1), -1, 1)))
ang0 = np.degrees(np.arccos(np.clip(np.sum(o0 * ot, 1), -1, 1)))
ex = U.exist & run["present"]
rot = np.abs(((U.phi - scene.init["phi"]) + np.pi) % (2 * np.pi) - np.pi) > 0.5
for c in ("main", "diagonal", "auxiliary"):
    for rr in (False, True):
        m = ex & (cat == c) & (rot == rr)
        if m.sum():
            print(f"{c:9s} rotated={rr}: n={m.sum():3d} init_err={np.median(ang0[m]):6.1f} est_err_med={np.median(ang[m]):6.1f} "
                  f"ok<20={np.mean(ang[m] < 20):.2f}  width_MAE={1000 * np.mean(np.abs(run['b_snap'][m] - U.b[m])):.1f}mm "
                  f"cont_MAE={1000 * np.mean(np.abs(P['b'][m] - U.b[m])):.1f}")
bad = np.flatnonzero(ex & (ang > 45))
print("bad orient examples:", [(int(e), U.cat[e], U.part[e], round(float(ang0[e])), round(float(ang[e])), round(float(U.b[e]), 3))
                               for e in bad[:15]])
pickle.dump({"P": P, "b_snap": run["b_snap"], "present": run["present"], "hist": run["hist"]},
            open(os.path.join(HERE, "_diag.pkl"), "wb"))
# 假设检验的 Δ 分布：真值确需翻转 vs 不需翻转
rotneed = {int(e): bool(rot[e]) for e in range(U.n_members)}
dt_true = U.d1[:, None] * ME.opening_dir(U.nodes_true, U.mi, U.mj, U.r, U.phi)[1] + \
    U.d2[:, None] * ME.opening_dir(U.nodes_true, U.mi, U.mj, U.r, U.phi)[2]
_, n1e, n2e = ME.opening_dir(P["V"], U.mi, U.mj, U.r, P["phi"])
de = P["d1"][:, None] * n1e + P["d2"][:, None] * n2e
derr = 1000 * np.linalg.norm(de - dt_true, axis=1)
for c in ("diagonal", "auxiliary"):
    m = ex & (cat == c)
    print(f"δ {c}: |δ_true| 均值 {1000 * np.mean(np.linalg.norm(dt_true[m], axis=1)):.1f} mm，误差 中位 {np.median(derr[m]):.1f} "
          f"均值 {np.mean(derr[m]):.1f} mm")
for h in run["hist"]:
    if "t_s" in h and "detail" in h:
        print(h["stage"], "耗时", h["t_s"], "s")
for h in run["hist"]:
    if "detail" not in h:
        continue
    det = h["detail"]
    good, badd = [], []
    for k, (best, dl, base) in det.items():
        k = int(k)
        if best and best.startswith("rot") and not best.startswith("rot0") and U.exist[k]:
            (good if rotneed[k] else badd).append((dl, base, U.b[k]))
    if good or badd:
        g = np.array(good) if good else np.zeros((0, 3)); bb = np.array(badd) if badd else np.zeros((0, 3))
        print(h["stage"], "需翻转者最优Δ分位:", np.round(np.percentile(g[:, 0], [10, 50, 90]), 1) if len(g) else "-",
              "不需翻转者最优Δ分位:", np.round(np.percentile(bb[:, 0], [10, 50, 90]), 1) if len(bb) else "-",
              "rel(需):", np.round(np.percentile(g[:, 0] / g[:, 1], [10, 50, 90]), 3) if len(g) else "-",
              "rel(不需):", np.round(np.percentile(bb[:, 0] / bb[:, 1], [10, 50, 90]), 3) if len(bb) else "-")
