# -*- coding: utf-8 -*-
"""专利C 仿真验证：三方法对比 + Monte Carlo + 检测率/虚警 + PS 数量/噪声敏感性 + 消融 + S1/FC1 对比。
运行：python run_sim.py  （约数分钟；热场缓存于 ../数据/_epochs_*.npz）
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "03_算法与软件"))
from fiminsar import invert as INV  # noqa: E402
from fiminsar import model as MD  # noqa: E402
from fiminsar import sim as S  # noqa: E402

DATA = HERE.parent / "数据"
DATA.mkdir(exist_ok=True)
VZ = [2, 5, 8, 11]
N_MC = 16
DIFF_THR_MM = 3.0           # 差异沉降报警阈值（末景最大腿间差）


def get_epochs(M, sat):
    f = DATA / f"_epochs_{sat}.npz"
    if f.exists():
        z = np.load(f, allow_pickle=True)
        return S.Epochs(geoms=list(S.SC.geometries(sat)), **{k: z[k] for k in z.files})
    ep = S.build_epochs(M, sat=sat, n_per_geom=30, seed=11)
    np.savez_compressed(f, **{k: getattr(ep, k) for k in ep.__dataclass_fields__ if k != "geoms"})
    return ep


def legs_draw(rng, settled=True):
    if not settled:
        return (0.0, 0.0, 0.0, 0.0)
    v = rng.uniform(-3, 0, 4)
    v[rng.integers(4)] = rng.uniform(-15, -6)
    return tuple(v)


def evaluate(M, ep, sc, methods=("proposed", "rigid", "empirical"), opt=None):
    d = S.synthesize(M, ep, sc)
    idx = [E.index for E in d["epochs"]]
    Bt = sc.B[idx]
    last = int(np.argmax([E.t for E in d["epochs"]]))
    base_xy = M.X[M.base, :2]
    out = {"assoc": d["assoc"]}
    for name in methods:
        if name == "proposed":
            r, th = S.method_proposed(M, d, opt)
            Be, std = r.b, r.b_std
        elif name == "rigid":
            Be, th, r = S.method_rigid(M, d); std = None
        else:
            Be, th = S.method_empirical(M, d, ep); std = None
        e = (Be - Bt)[:, VZ] * 1e3
        tilt_t, _ = INV.foundation_tilt(base_xy, Bt[last, VZ])
        tilt_e, _ = INV.foundation_tilt(base_xy, Be[last, VZ])
        diff_e = float(np.ptp(Be[last, VZ]) * 1e3)
        out[name] = {"rmse_leg": np.sqrt((e ** 2).mean(0)).tolist(), "rmse": float(np.sqrt((e ** 2).mean())),
                     "final_err": e[last].tolist(), "tilt_true": tilt_t, "tilt_err": abs(tilt_e - tilt_t),
                     "top_tilt_err": abs(INV.top_tilt(M, Be[last]) - INV.top_tilt(M, Bt[last])),
                     "thermal_expl": S.thermal_explained(d, th), "diff_est": diff_e,
                     "diff_true": float(np.ptp(Bt[last, VZ]) * 1e3)}
        if std is not None:
            out[name]["std_final_mm"] = (std[last, VZ] * 1e3).tolist()
            z = e[last] / (std[last, VZ] * 1e3)
            out[name]["cover95"] = float(np.mean(np.abs(z) < 1.96))
    return out, d


def agg(runs, key, sub):
    v = np.array([r[key][sub] for r in runs], float)
    return {"mean": float(v.mean()), "ci95": float(1.96 * v.std(ddof=1) / np.sqrt(len(v))) if len(v) > 1 else 0.0}


def main():
    t0 = time.time()
    M = MD.build_model("suspension")
    res = {"tower": {"H_m": M.H, "nodes": int(M.g.n_nodes), "members": int(M.g.n_members)}}
    ep = get_epochs(M, "FC1")
    res["epochs"] = {"FC1": int(len(ep.t)), "span_d": float(ep.t.max() - ep.t.min())}
    th_amp = []
    print("epochs ready", time.time() - t0)

    # ---------------- 1 主对比 Monte Carlo（沉降场景）+ 无沉降（虚警）
    runs, nulls, one = [], [], None
    for s in range(N_MC):
        rng = np.random.default_rng(100 + s)
        B = S.settlement_truth(ep.t, legs_draw(rng), onset=rng.uniform(120, 260), rng=rng)
        o, d = evaluate(M, ep, S.Scenario(B=B, seed=1000 + s))
        runs.append(o)
        if one is None:
            one = (B, d)
            th_amp = float(np.max(np.abs(np.concatenate([E.th_true_rel for E in d["epochs"]]))) * 1e3)
        B0 = S.settlement_truth(ep.t, legs_draw(rng, False), rng=rng)
        o0, _ = evaluate(M, ep, S.Scenario(B=B0, seed=5000 + s))
        nulls.append(o0)
    meth = ("proposed", "rigid", "empirical")
    res["main"] = {}
    for mname in meth:
        det = np.mean([r[mname]["diff_est"] > DIFF_THR_MM for r in runs])
        fa = np.mean([r[mname]["diff_est"] > DIFF_THR_MM for r in nulls])
        res["main"][mname] = {k: agg(runs, mname, k) for k in ("rmse", "tilt_err", "top_tilt_err", "thermal_expl")}
        res["main"][mname]["rmse_null"] = agg(nulls, mname, "rmse")
        res["main"][mname]["detect_rate"] = float(det)
        res["main"][mname]["false_alarm"] = float(fa)
    res["main"]["proposed"]["cover95"] = agg(runs, "proposed", "cover95")
    res["main"]["thermal_LOS_amp_mm"] = th_amp
    res["main"]["tilt_true_mean_permille"] = float(np.mean([r["proposed"]["tilt_true"] for r in runs]))
    res["main"]["assoc"] = runs[0]["assoc"]
    res["main"]["n_mc"] = N_MC; res["main"]["diff_thr_mm"] = DIFF_THR_MM
    print("main done", time.time() - t0)

    # 时序示例
    B, d = one
    r, _ = S.method_proposed(M, d)
    Br, _, _ = S.method_rigid(M, d)
    Bem, _ = S.method_empirical(M, d, ep)
    idx = [E.index for E in d["epochs"]]; o = np.argsort([E.t for E in d["epochs"]])
    ts = {"t": np.array([E.t for E in d["epochs"]])[o].tolist(),
          "true": (B[idx][o][:, VZ] * 1e3).tolist(), "proposed": (r.b[o][:, VZ] * 1e3).tolist(),
          "proposed_std": (r.b_std[o][:, VZ] * 1e3).tolist(),
          "rigid": (Br[o][:, VZ] * 1e3).tolist(), "empirical": (Bem[o][:, VZ] * 1e3).tolist()}
    (DATA / "时序示例.json").write_text(json.dumps(ts), encoding="utf-8")

    # ---------------- 2 敏感性：PS 数量、噪声
    def sweep(param, values, nrep=6):
        tab = []
        for v in values:
            rr = []
            for s in range(nrep):
                rng = np.random.default_rng(300 + s)
                B = S.settlement_truth(ep.t, legs_draw(rng), onset=200, rng=rng)
                kw = {"n_ps": 12, "noise": 1.0, "with_cr": True}
                kw[param] = v
                if param == "n_ps":
                    kw["with_cr"] = False
                o, _ = evaluate(M, ep, S.Scenario(B=B, seed=7000 + s, **kw))
                rr.append(o)
            tab.append({"value": v, **{m: agg(rr, m, "rmse")["mean"] for m in meth}})
        return tab
    res["sens_nps_noCR"] = sweep("n_ps", [3, 5, 8, 12, 20])
    res["sens_noise"] = sweep("noise", [0.5, 1.0, 2.0, 3.0, 5.0])
    print("sens done", time.time() - t0)

    # ---------------- 3 消融
    ab = {}
    for name, sc_kw, opt in [("完整", {}, INV.Options()),
                             ("无日照热基ψ2", {}, INV.Options(use_solar=False)),
                             ("无风列", {}, INV.Options(estimate_wind=False)),
                             ("无夹持CR", {"with_cr": False}, INV.Options()),
                             ("无平滑先验", {}, INV.Options(lam_b=1e4))]:
        rr = []
        for s in range(8):
            rng = np.random.default_rng(100 + s)
            B = S.settlement_truth(ep.t, legs_draw(rng), onset=rng.uniform(120, 260), rng=rng)
            o, _ = evaluate(M, ep, S.Scenario(B=B, seed=1000 + s, **sc_kw), methods=("proposed",), opt=opt)
            rr.append(o)
        ab[name] = {k: agg(rr, "proposed", k)["mean"] for k in ("rmse", "tilt_err", "thermal_expl")}
    res["ablation"] = ab
    print("ablation done", time.time() - t0)

    # ---------------- 4 Sentinel-1 晨昏轨道几何
    ep1 = get_epochs(M, "S1")
    rr = []
    for s in range(8):
        rng = np.random.default_rng(100 + s)
        B = S.settlement_truth(ep1.t, legs_draw(rng), onset=rng.uniform(120, 260), rng=rng)
        o, _ = evaluate(M, ep1, S.Scenario(B=B, seed=1000 + s))
        rr.append(o)
    res["S1"] = {m: {k: agg(rr, m, k)["mean"] for k in ("rmse", "tilt_err", "thermal_expl")} for m in meth}

    # ---------------- 5 D 最优布设（4 只 CR，候选：下段主材角点，升降轨两行）
    lv = np.asarray(M.g.meta["levels"])
    candn = [i for i, t in enumerate(M.g.ntype) if t == "corner" and M.X[i, 2] < lv[8] + 0.1]
    geo = S.SC.geometries("FC1")
    Hc = np.array([[g.los @ M.point_rows([q])[0] @ M.Gb for g in geo] for q in candn])
    R = np.diag([1 / 0.004 ** 2 if j not in VZ else 1e-6 for j in range(12)])
    sel, Mi = INV.d_optimal(Hc, 4, R=R, sigma=1e-3)
    emp = [candn.index(c) for c in sorted(candn, key=lambda q: -M.X[q, 2])[:4]]   # 经验：最高一层四角
    Me = R + sum(Hc[c].T @ Hc[c] for c in emp) / 1e-6
    sd_opt = np.sqrt(np.diag(np.linalg.inv(Mi)))[VZ] * 1e3; sd_emp = np.sqrt(np.diag(np.linalg.inv(Me)))[VZ] * 1e3
    res["dopt"] = {"sel_z": M.X[[candn[c] for c in sel], 2].tolist(), "emp_z": M.X[[candn[c] for c in emp], 2].tolist(),
                   "sd_opt_mm": sd_opt.tolist(), "sd_emp_mm": sd_emp.tolist(),
                   "reduction": float(1 - sd_opt.mean() / sd_emp.mean())}
    res["runtime_s"] = time.time() - t0
    (DATA / "结果.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(res, ensure_ascii=False, indent=1)[:3000])


if __name__ == "__main__":
    main()
