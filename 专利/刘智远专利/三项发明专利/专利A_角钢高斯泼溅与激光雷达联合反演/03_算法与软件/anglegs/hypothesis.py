# -*- coding: utf-8 -*-
"""逐杆件离散假设检验（局部渲染残差比较）：肢朝向 {0°,90°,180°,270°} × 偏心假设、存在/不存在。

对杆件 e：
  1) 以“包络体”（沿节点连线、半径≈1.15·b+偏心+余量）在全部射线中检索可能受 e 影响的射线子集 R_e；
  2) 生成各假设 H 的面元（其余杆件不变），与 R_e 上既有配对（剔除 e 的现有面元）按深度在线归并、合成；
  3) 在 R_e 上计算逐射线负对数似然之和 ℓ(H)，取 Δ=ℓ(H)−ℓ(H0) 最小且小于 −max(τ, τ_rel·ℓ(H0)) 的假设执行。
全部假设 × 全部子射线在一个 numba 并行核函数（fused.hyp_eval）中计算。
该检验把连续优化难以跨越的 90°/180° 肢朝向翻转、偏心与朝向的相互补偿、以及“以肢宽收缩代替杆件缺失”的
局部极小，转化为显式的模型比较。
"""
from __future__ import annotations

import numpy as np

from . import fused as FU
from .raycast import build_pairs
from .surfels import Layout, generate_np, sigmoid

B_CAT = {"main": 0.14, "diagonal": 0.075, "auxiliary": 0.056}
_Z1 = np.zeros(1)
_Z2 = np.zeros((1, 3))


def _member_layout(lay: Layout, e, off, cnt):
    sl = slice(off, off + cnt)
    return Layout(lay.mi[e:e + 1], lay.mj[e:e + 1], lay.r[e:e + 1], np.zeros(cnt, np.int64), lay.sk[sl], lay.sleg[sl],
                  lay.sp[sl], lay.sK[sl], lay.P, lay.kind)


def _rays_terms(prob, P):
    """各观测项的射线（numpy）、截止距离与足迹参数。"""
    out = {}
    if prob.cam is not None:
        o, d = (np.asarray(a) for a in prob.cam_rays(P))
        out["cam"] = (o, d, np.full(prob.cam.n, 400.0), np.zeros(prob.cam.n), prob.cam.sigk, prob.cam.e1, prob.cam.e2)
    if prob.ret is not None:
        L = prob.ret
        out["ret"] = (L.o, L.d, L.dmeas + 0.35, np.zeros(L.n), np.full(L.n, L.sig_div), L.e1, L.e2)
    if prob.free is not None:
        L = prob.free
        out["free"] = (L.o, L.d, np.where(L.dmeas > 0, L.dmeas - 0.3, 300.0), np.zeros(L.n), np.full(L.n, L.sig_div),
                       L.e1, L.e2)
    return out


def _gauge(b):
    return float(np.clip(np.round(0.55 * b / 0.005) * 0.005, 0.02, 0.07))


FLIP_MIN_B = 0.063      # 肢朝向翻转检验的最小肢宽（m）：约 8 像素（28 m、8 mm 地面采样距离）
FLIP_MIN_L = 2.5        # 最小杆长（m）


def _hypotheses(cat, b, phi, d1, d2, lg, pi, hyps, length=10.0):
    """返回 [(名称, (b, φ, δ1, δ2, logit))]，第 0 个为现状。
    肢朝向翻转仅对肢宽 ≥ FLIP_MIN_B 且杆长 ≥ FLIP_MIN_L 的杆件检验（小规格短杆的翻转证据不足，取设计默认朝向）；
    偏心假设（准距规则）对全部非主材检验。"""
    H = [("H0", (b, phi, d1, d2, lg))]
    is_main = cat == "main"
    if "rot90" in hyps and pi >= 0.5 and not is_main:
        g = _gauge(b)
        h = 0.5 * b
        flips = ((0, phi, None), (90, phi + np.pi / 2, (d2, -(d1 + h))),
                 (180, phi + np.pi, (-(d1 + h), -(d2 + h))), (270, phi - np.pi / 2, (-(d2 + h), d1)))
        if not (b >= FLIP_MIN_B and length >= FLIP_MIN_L):
            flips = flips[:1]
        for k, ph, cen in flips:
            dv = {"0": (0.0, 0.0), "g1": (-g, 0.0), "g2": (0.0, -g)}
            if k != 0:
                dv["cur"] = (d1, d2)
                dv["c"] = (float(np.clip(cen[0], -0.12, 0.12)), float(np.clip(cen[1], -0.12, 0.12)))
            for dn, (a1, a2) in dv.items():
                H.append((f"rot{k}_{dn}", (b, ph, a1, a2, lg)))
    if "toggle" in hyps:
        if pi >= 0.5:
            H.append(("absent", (b, phi, d1, d2, -7.0)))
        else:
            b0 = B_CAT.get(cat, 0.07)
            g0 = _gauge(b0)
            for nm, ph in (("present", phi), ("present90", phi + np.pi / 2), ("present180", phi + np.pi),
                           ("present270", phi - np.pi / 2)):
                H.append((nm, (b0, ph, 0.0, 0.0, 3.0)))
                H.append((nm + "_g1", (b0, ph, -g0, 0.0, 3.0)))
                H.append((nm + "_g2", (b0, ph, 0.0, -g0, 3.0)))
    return H


def member_tests(prob, x, members=None, hyps=("rot90", "toggle"), tau=25.0, tau_rel=0.012, log=None):
    """返回 (更新后的参数向量, {e: 检验结果})。"""
    lay = prob.lay
    cfg = prob.cfg
    P = {k: np.asarray(v) for k, v in prob.split(x).items()}
    S = generate_np(lay, P["V"], P["b"], P["phi"], P["d1"], P["d2"], P["logit"],
                    P.get("E") if cfg.indep_ends else None)
    S = {k: np.ascontiguousarray(v) for k, v in S.items()}
    alb = np.ascontiguousarray(np.asarray(P["app"])[lay.sm])
    counts = np.bincount(lay.sm, minlength=lay.n_members)
    offs = np.concatenate([[0], np.cumsum(counts)[:-1]])
    terms = _rays_terms(prob, P)
    pi = np.asarray(sigmoid(P["logit"]))
    ext = np.asarray(P["ext"])
    cats = getattr(prob, "cats", ["diagonal"] * lay.n_members)
    members = np.arange(lay.n_members) if members is None else members
    results = {}
    xn = x.copy()
    sl = prob.sl
    code = {"cam": 0, "ret": 1, "free": 2}
    for e in members:
        e = int(e)
        off, cnt = int(offs[e]), int(counts[e])
        b, phi, d1, d2, lg = (float(P[k][e]) for k in ("b", "phi", "d1", "d2", "logit"))
        Le = float(np.linalg.norm(P["V"][lay.mj[e]] - P["V"][lay.mi[e]]))
        H = _hypotheses(cats[e], b, phi, d1, d2, lg, pi[e], hyps, length=Le)
        if len(H) == 1:
            continue
        ml = _member_layout(lay, e, off, cnt)
        Sm = [generate_np(ml, P["V"], np.array([c[0]]), np.array([c[1]]), np.array([c[2]]), np.array([c[3]]),
                          np.array([c[4]])) for _, c in H]
        hS = {k: np.ascontiguousarray(np.concatenate([s[k] for s in Sm])) for k in Sm[0]}
        # 包络体检索射线子集
        vi, vj = P["V"][lay.mi[e]], P["V"][lay.mj[e]]
        Lm = float(np.linalg.norm(vj - vi))
        u = (vj - vi) / Lm
        nenv = max(2, int(np.ceil(Lm / 0.5)))
        skk = (np.arange(nenv) + 0.5) / nenv
        env_mu = vi[None] + skk[:, None] * (vj - vi)[None]
        bmax = max(b, B_CAT.get(cats[e], 0.08))
        rad_env = 1.15 * bmax + 0.06 + 0.08
        tot = np.zeros(len(H))
        nray = 0
        for key, rt in terms.items():
            o, d, tmax, s0, sk, e1, e2 = rt
            pr = build_pairs(env_mu, np.repeat(u[None], nenv, 0), np.full(nenv, 0.6 * Lm / nenv),
                             np.full(nenv, rad_env), o, d, tmax, s0, sk, maxk=1)
            R = np.flatnonzero((pr.end - pr.start) > 0)
            if len(R) == 0:
                continue
            nray += len(R)
            fp = True if key == "cam" else bool(cfg.footprint)
            skp = sk[R] if fp else np.zeros(len(R))
            hp = build_pairs(hS["mu"], hS["t1"], 3 * hS["s1"], 3 * hS["s2"] + cfg.margin, o[R], d[R], tmax[R], s0[R],
                             skp, maxk=min(512, cfg.maxk * len(H)))
            base = prob.pairs[key][0]
            out = np.zeros((len(H), len(R)))
            if key == "cam":
                K = prob.K["cam"]
                args_t = (K.mask[R], K.gray[R], K.sky[R], K.valid[R], K.wp, _Z1, 1.0, 0.0, 0.0, 1.0, _Z1, 0.0)
                w = cfg.w_cam
            elif key == "ret":
                K = prob.K["ret"]
                args_t = (_Z1, _Z1, _Z1, _Z1, 0.0, K.dmeas[R], K.sigr, K.wret, K.wfree, K.eps, _Z1, 0.0)
                w = 1.0
            else:
                K = prob.K["free"]
                args_t = (_Z1, _Z1, _Z1, _Z1, 0.0, _Z1, 1.0, 0.0, K.wfree, 1.0, K.ground[R], K.pdet)
                w = 1.0
            FU.hyp_eval(code[key], len(H), len(R), base.start[R], base.end[R], base.ps, base.tc, off, off + cnt,
                        hp.start, hp.end, hp.ps, hp.tc, cnt,
                        S["mu"], S["t1"], S["t2"], S["s1"], S["s2"], S["alpha"], alb,
                        hS["mu"], hS["t1"], hS["t2"], hS["s1"], hS["s2"], hS["alpha"], float(P["app"][e]),
                        np.ascontiguousarray(o[R]), np.ascontiguousarray(d[R]), np.ascontiguousarray(e1[R]),
                        np.ascontiguousarray(e2[R]), np.ascontiguousarray(s0[R]), np.ascontiguousarray(skp), fp,
                        prob.sun, float(ext[7]), float(ext[8]), *args_t, out)
            tot += w * out.sum(1)
        if nray == 0:
            continue
        dl = tot[1:] - tot[0]
        # 判决门限：绕截面形心 180° 翻转在轮廓上严格不可辨（点反射使各视向投影宽度不变），只能靠明暗与激光距离区分，
        # 故其门限加倍；肢宽小于 63 mm 的小规格杆件门限放大 1.5 倍。取“Δ + 门限”最负者，且须小于 0。
        base_thr = max(tau, tau_rel * abs(tot[0])) * (1.5 if b < 0.063 else 1.0)
        mult = np.array([2.0 if nm.startswith("rot180") else 1.0 for nm, _ in H[1:]])
        margin = dl + base_thr * mult
        kbest = int(np.argmin(margin))
        best, bestd = H[kbest + 1][0], float(dl[kbest])
        accepted = bool(margin[kbest] < 0)
        results[e] = {"best": best, "delta": bestd, "base": float(tot[0]), "accepted": bool(accepted), "n_rays": nray}
        if accepted:
            bb, ph, dd1, dd2, lgv = H[kbest + 1][1]
            ph = (ph + np.pi) % (2 * np.pi) - np.pi
            prob.init["phi"][e] = ph            # 连续优化的朝向先验中心随之更新
            xn[sl["phi"].start + e] = ph
            xn[sl["logit"].start + e] = lgv
            xn[sl["b"].start + e] = bb
            xn[sl["d1"].start + e] = dd1
            xn[sl["d2"].start + e] = dd2
    if log:
        acc = [k for k, v in results.items() if v["accepted"]]
        kinds = {}
        for k in acc:
            nm = results[k]["best"].split("_")[0]
            kinds[nm] = kinds.get(nm, 0) + 1
        log(f"  逐杆件假设检验：检验 {len(results)} 根，接受 {len(acc)} 根 {kinds}")
    return xn, results
