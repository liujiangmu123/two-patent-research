# -*- coding: utf-8 -*-
"""开发诊断：在收敛解附近对单根杆件扫描肢朝向 φ（偏心取现值/真值/零），检查可辨识性。"""
import os
import pickle
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "03_算法与软件"))
from anglegs import hypothesis as HY  # noqa: E402
from anglegs import pipeline as PL  # noqa: E402
from anglegs.optimize import Problem  # noqa: E402
from anglegs.surfels import generate_np, make_layout  # noqa: E402

sc = PL.SceneCfg(seed=1)
scene = PL.Scene(sc, log=lambda *a: None)
U = scene.U
D = pickle.load(open(os.path.join(HERE, "_diag.pkl"), "rb"))
P = D["P"]
cfg = PL.VARIANTS["本发明"]
lay = make_layout(scene.init["V"], U.mi, U.mj)
prob = Problem(lay, len(U.nodes_true), scene.init, scene.cam, scene.ret, scene.free, cfg, scene.sym, U.is_cand)
prob.cats = list(U.cat)
x = prob.pack({k: P[k] for k in prob.sl})
prob.repair(x)
members = [int(a) for a in sys.argv[1:]] or [62, 73, 146, 162, 225, 230, 245, 254]
S = generate_np(lay, P["V"], P["b"], P["phi"], P["d1"], P["d2"], P["logit"])
S["appidx"] = prob.app_idx
counts = np.bincount(lay.sm, minlength=lay.n_members)
offs = np.concatenate([[0], np.cumsum(counts)[:-1]])
terms = HY._rays_terms(prob, {k: P[k] for k in prob.sl})
for e in members:
    off, cnt = int(offs[e]), int(counts[e])
    ml = HY._member_layout(lay, e, off, cnt)
    vi, vj = P["V"][lay.mi[e]], P["V"][lay.mj[e]]
    Lm = np.linalg.norm(vj - vi); u = (vj - vi) / Lm
    nenv = max(2, int(np.ceil(Lm / 0.5))); skk = (np.arange(nenv) + 0.5) / nenv
    env_mu = vi[None] + skk[:, None] * (vj - vi)[None]
    subsets = {}
    from anglegs.raycast import build_pairs
    for key, rt in terms.items():
        o, d, tmax, s0, sk, e1, e2 = rt
        pr = build_pairs(env_mu, np.repeat(u[None], nenv, 0), np.full(nenv, 0.6 * Lm / nenv),
                         np.full(nenv, 1.15 * max(P["b"][e], 0.08) + 0.1), o, d, tmax, s0, sk, maxk=1)
        rays = np.flatnonzero((pr.end - pr.start) > 0)
        if len(rays):
            subsets[key] = rays

    def loss_for(b, phi, d1, d2, lg, only=None):
        Sm = generate_np(ml, P["V"], np.array([b]), np.array([phi]), np.array([d1]), np.array([d2]), np.array([lg]))
        nS = len(S["s1"])
        Sall = {k: np.concatenate([S[k], Sm[k]]) for k in ("mu", "t1", "t2", "s1", "s2", "alpha")}
        Sall["alpha"][off:off + cnt] = 0.0
        Sall["appidx"] = np.concatenate([S["appidx"], S["appidx"][off:off + cnt]])
        tot = {}
        for key, rays in subsets.items():
            loc, ps, tc = HY._subset_pairs(prob.pairs[key][0], rays, off, off + cnt)
            o, d, tmax, s0, sk, e1, e2 = terms[key]
            prn = build_pairs(Sm["mu"], Sm["t1"], 3 * Sm["s1"], 3 * Sm["s2"] + 0.06, o[rays], d[rays], tmax[rays],
                              s0[rays], sk[rays], maxk=48)
            loc = np.concatenate([loc, prn.pr]); ps = np.concatenate([ps, prn.ps + nS]); tc = np.concatenate([tc, prn.tc])
            tot[key] = HY._eval(prob, key, {k: P[k] for k in prob.sl}, Sall, rays, loc, ps, tc, terms[key], True)
        return tot
    phis = np.radians(np.arange(-180, 180, 15))
    rows = {}
    for lab, (d1, d2) in (("cur", (P["d1"][e], P["d2"][e])), ("true", (U.d1[e], U.d2[e])), ("zero", (0.0, 0.0))):
        L = [loss_for(P["b"][e], ph, d1, d2, P["logit"][e]) for ph in phis]
        rows[lab] = L
    tphi = np.degrees(U.phi[e]); ephi = np.degrees(P["phi"][e])
    print(f"=== member {e} {U.cat[e]} b_true={U.b[e]:.3f} b_est={P['b'][e]:.3f} phi_true={tphi:.0f} phi_est={ephi:.0f} "
          f"rays={ {k: len(v) for k, v in subsets.items()} }")
    for lab, L in rows.items():
        for key in L[0]:
            arr = np.array([l[key] for l in L])
            arr = arr - arr.min()
            print(f"  δ={lab:4s} {key:4s} argmin={np.degrees(phis[np.argmin(arr)]):6.0f}  " +
                  " ".join(f"{v:5.0f}" for v in arr))
