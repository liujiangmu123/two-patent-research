# -*- coding: utf-8 -*-
"""专利B 仿真验证：PTM 统一截面基线 / 仅逆向设计 / 仅振动修正（无信息先验）/ 逆向设计+振动贝叶斯（本发明）；
测点优化（EfI）vs 经验布置；噪声敏感性。所有数字由本脚本运行得到并写入 ../数据/。

运行：python run_sim.py [--quick]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, "..", "..", "03_算法与软件")))
import towercal  # noqa: E402,F401  (设置 towerkit 路径)
import towerkit as tk  # noqa: E402
from towercal import bayes, check, design, excitation, extract, model, pipeline, sensors  # noqa: E402
from towercal.model import ORDER, CAT_A, CAT_I, CAT_J  # noqa: E402

DATA = os.path.normpath(os.path.join(HERE, "..", "数据"))
os.makedirs(DATA, exist_ok=True)

PTM_UNIFORM = {"main": "L140x10", "diagonal": "L70x5", "auxiliary": "L50x4"}
ASSESS = dict(v0=31.0, ice=0.015)            # 复核工况（提高风速与覆冰，使部分杆件进入临界区）
N_SENS = 8
TOWERS = {
    "suspension": dict(ins=5.2, neighbor=None),
    "tension": dict(ins=2.6, neighbor=[(-380.0 * np.cos(np.radians(15)), -380.0 * np.sin(np.radians(15))),
                                        (420.0 * np.cos(np.radians(15)), -420.0 * np.sin(np.radians(15)))]),
}


def make_graph(kind, ins):
    g = tk.build_tower(kind)
    for a in g.meta["attach"]:
        if a["kind"] == "conductor":
            a["insulator_len"] = ins
            a["insulator_orient"] = "horizontal" if kind == "tension" else "vertical"
    return g


def truth_sample(g, di, pt, rng):
    """真值：隐藏设计情景下的规范设计 + 施工偏差（±1 档 20%/±2 档 4%）+ 连接刚度折减 + 基础柔度。"""
    sc = design.sample_scenarios(di, 1, rng)[0]
    sc.v0 = float(rng.uniform(23.0, 30.0))
    _, gs, _ = design.reverse_design(g, di, sc, pt=pt)
    j = np.array([ORDER.index(gs[gr]) for gr in pt.groups])
    dev = rng.choice([-2, -1, 0, 1, 2], size=len(j), p=[0.02, 0.10, 0.76, 0.10, 0.02])
    j = np.clip(j + dev, 0, len(ORDER) - 1)
    theta = (float(rng.uniform(0.70, 0.95)), float(rng.uniform(9.5, 10.8)))
    return j, theta, sc


def secs_of(pt, j):
    return {gr: ORDER[int(k)] for gr, k in zip(pt.groups, j)}


def ptm_index(pt):
    return np.array([ORDER.index(PTM_UNIFORM[c]) for c in pt.gcat])


def nearest_index(A):
    return np.array([int(np.argmin(np.abs(CAT_A - a))) for a in A])


# ---------------------------------------------------------------------- 评价
class Evaluator:
    def __init__(self, pt, di, j_true, th_true, comp_nodes):
        self.pt, self.di = pt, di
        self.jt, self.tht = j_true, th_true
        self.sc_d = design.Scenario(kV=di.voltage_kV, tower_type=di.tower_type, span_h=di.span_h,
                                    span_v=di.span_v, angle_deg=di.line_angle_deg, **ASSESS)
        self.dofs = sensors.node_dofs(comp_nodes)
        self.f_t, phi = pt.modes(secs_of(pt, j_true), *th_true, n=10)
        self.phi_t = phi[self.dofs]
        self.disp_t, self.ratio_t = check.design_response(pt, di, self.sc_d, secs_of(pt, j_true), th_true)
        self.H = float(pt.X[:, 2].max())

    def response(self, j, th):
        return check.design_response(self.pt, self.di, self.sc_d, secs_of(self.pt, j), th)

    def __call__(self, j, th, j_lo=None, j_hi=None, disp_ci=None, th_samples=None):
        pt = self.pt
        f, phi = pt.modes(secs_of(pt, j), *th, n=14)
        M = sensors.mac_matrix(self.phi_t, phi[self.dofs])
        k = M.argmax(1)
        ferr = np.abs(f[k] - self.f_t) / self.f_t
        macs = M[np.arange(len(k)), k]
        disp, ratio = self.response(j, th)
        fail_t, fail_e = self.ratio_t > 1.0, ratio > 1.0
        crit = self.ratio_t > 0.8
        out = {
            "group_hit": float(np.mean(j == self.jt)), "group_within1": float(np.mean(np.abs(j - self.jt) <= 1)),
            "freq_err_mean_6": float(ferr[:6].mean()), "freq_err_max_6": float(ferr[:6].max()),
            "mac_mean_6": float(macs[:6].mean()), "mac_min_6": float(macs[:6].min()),
            "disp_true": self.disp_t, "disp_est": disp, "disp_err": float(abs(disp - self.disp_t) / self.disp_t),
            "ratio_err_mean": float(np.mean(np.abs(ratio - self.ratio_t))),
            "ratio_err_crit": float(np.mean(np.abs(ratio[crit] - self.ratio_t[crit]))) if crit.any() else 0.0,
            "misjudge_rate": float(np.mean(fail_t != fail_e)),
            "missed_fail": int(np.sum(fail_t & ~fail_e)), "false_fail": int(np.sum(~fail_t & fail_e)),
            "n_fail_true": int(fail_t.sum()),
            "disp_verdict_ok": bool((disp > self.H / 100) == (self.disp_t > self.H / 100)),
            "kappa": float(th[0]), "logkv": float(th[1]),
        }
        if j_lo is not None:
            out["coverage_groups"] = float(np.mean((j_lo <= self.jt) & (self.jt <= j_hi)))
            out["ci_width_groups"] = float(np.mean(j_hi - j_lo))
        if disp_ci is not None:
            out["disp_ci"] = list(map(float, disp_ci))
            out["coverage_disp"] = bool(disp_ci[0] <= self.disp_t <= disp_ci[1])
        if th_samples is not None:
            lo, hi = np.percentile(th_samples, [5, 95], axis=0)
            out["coverage_kappa"] = bool(lo[0] <= self.tht[0] <= hi[0])
            out["coverage_logkv"] = bool(lo[1] <= self.tht[1] <= hi[1])
        return out


def posterior_disp_ci(ev, res, G, rng, n=30):
    idx = rng.choice(len(res["samples"]), size=n, replace=False)
    d = []
    for i in idx:
        th = res["samples"][i]
        j = np.clip(np.rint(th[:G]).astype(int), 0, len(ORDER) - 1)
        d.append(ev.response(j, (th[G], th[G + 1]))[0])
    return np.percentile(d, [5, 95])


# ---------------------------------------------------------------------- 仅振动（常规修正）：统一截面 × 类别缩放
def vib_only_scale(pt, rm, modes, sel, seed, n):
    j0 = ptm_index(pt)
    cats = ["main", "diagonal", "auxiliary"]
    cidx = np.array([cats.index(c) for c in pt.gcat])
    A0, I0, J0 = CAT_A[j0], CAT_I[j0], CAT_J[j0]

    def to_props(th):
        s = np.exp(th[:3])[cidx]
        return A0 * s, I0 * s ** 2, J0 * s ** 2      # 同类角钢 I ∝ A²（几何相似）近似

    dofs = sensors.node_dofs(sel)
    lik = bayes.ModalLikelihood(rm, modes, rm.free_index(dofs), n_model=16, to_props=to_props)
    pr = bayes.ScalePrior(3)
    th, ll, st, _ = bayes.tmcmc(lik.loglik, pr, n=n, rng=seed)
    med = np.median(th, 0)
    j = nearest_index(to_props(med)[0])
    lo = nearest_index(to_props(np.percentile(th, 5, 0))[0])
    hi = nearest_index(to_props(np.percentile(th, 95, 0))[0])
    return j, (float(med[3]), float(med[4])), np.minimum(lo, hi), np.maximum(lo, hi), th[:, 3:5], st


# ---------------------------------------------------------------------- 单次试验
def run_trial(kind, g, di, pt, prior, mix, rm, seed, n_tm, noise=None, layouts=("efi", "emp"), methods=True):
    rng = np.random.default_rng(1000 + seed)
    jt, tht, sc_t = truth_sample(g, di, pt, rng)
    comp_nodes = [i for i, t in enumerate(g.ntype) if t in ("corner", "arm_tip", "peak_tip") and g.nodes[i, 2] > 5]
    ev = Evaluator(pt, di, jt, tht, comp_nodes)
    fem_t = pt.as_femodel(secs_of(pt, jt), tht)
    G = len(pt.groups)
    rec = {"kind": kind, "seed": seed, "theta_true": tht, "truth_scenario": sc_t.to_dict(),
           "f_true": ev.f_t[:8].tolist(), "n_fail_true": int((ev.ratio_t > 1).sum()), "methods": {}, "layouts": {}}
    pmap = np.array([ORDER.index(prior["map"][gr]) for gr in pt.groups])
    sel_efi, ld_efi = pipeline.place_sensors(pt, prior["map"], N_SENS)
    sel_emp = sensors.empirical_nodes(g, N_SENS)
    obs = {}
    for lay, sel in (("efi", sel_efi), ("emp", sel_emp)):
        if lay not in layouts:
            continue
        dofs = sensors.node_dofs(sel)
        t, acc, _, _ = excitation.ambient_response(fem_t, dofs, U10=float(rng.uniform(6, 12)), duration=600.0,
                                                   dt=0.05, n_modes=24, zeta=float(rng.uniform(0.01, 0.025)),
                                                   seed=seed)
        nz = noise or excitation.MemsNoise()
        nz.seed = seed
        y, _ = nz.apply(t, acc)
        modes, info = pipeline.identify(y, 20.0)
        f_t, phi_t = pt.modes(secs_of(pt, jt), *tht, n=14)
        matched = []
        for m in modes:
            macs = [sensors.mac(m["phi"], phi_t[dofs, r]) for r in range(14)]
            r = int(np.argmax(macs))
            matched.append({"f": m["f"], "zeta": m["zeta"], "true_mode": r, "f_true": float(f_t[r]),
                            "mac": float(macs[r])})
        good = [x for x in matched if x["mac"] > 0.9 and abs(x["f"] - x["f_true"]) / x["f_true"] < 0.02]
        _, phi_p = pt.modes(prior["map"], 0.85, 10.2, n=8)
        rec["layouts"][lay] = {"nodes": [int(s) for s in sel], "n_identified": len(modes),
                               "n_valid": len(good), "n_true_modes_found": len({x["true_mode"] for x in good}),
                               "freq_id_err_mean": float(np.mean([abs(x["f"] - x["f_true"]) / x["f_true"]
                                                                  for x in good])) if good else None,
                               "mac_id_mean": float(np.mean([x["mac"] for x in good])) if good else None,
                               "fim_logdet": float(sensors.efi_nodes(phi_p, sel, len(sel))[1]),
                               "max_offdiag_mac": sensors.offdiag_mac(phi_p[dofs]), "modes": matched}
        obs[lay] = (modes, sel)
    if not methods:
        res = pipeline.calibrate(pt, rm, *obs["efi"], mix, n=n_tm, seed=seed)
        mj, k, v = pipeline.map_theta(res, G)
        rec["methods"]["proposed"] = ev(mj, (k, v), res["lo"], res["hi"], th_samples=np.column_stack([res["kappa"], res["logkv"]]))
        return rec
    # 1 PTM 统一截面基线
    rec["methods"]["ptm_uniform"] = ev(ptm_index(pt), (1.0, 11.5))
    # 2 仅规范逆向设计（先验众数，名义 κ=1、刚性基础）
    rec["methods"]["reverse_only"] = ev(pmap, (1.0, 11.5))
    # 3a 仅振动修正（统一截面 + 类别缩放 + κ + k_v，均匀先验）
    modes, sel = obs["efi"]
    jv, thv, lo, hi, ths, st = vib_only_scale(pt, rm, modes, sel, seed, n_tm)
    rec["methods"]["vib_only"] = ev(jv, thv, lo, hi, th_samples=ths)
    # 3b 仅振动修正（逐组无信息均匀先验）
    res_u = pipeline.calibrate(pt, rm, modes, sel, bayes.uniform_pmf(pt.gcat), n=n_tm, seed=seed)
    mj, k, v = pipeline.map_theta(res_u, G)
    rec["methods"]["vib_only_groupwise"] = ev(mj, (k, v), res_u["lo"], res_u["hi"],
                                              th_samples=np.column_stack([res_u["kappa"], res_u["logkv"]]))
    # 4 本发明：逆向设计混合先验 + 振动贝叶斯（EfI 测点）
    for lay in layouts:
        modes, sel = obs[lay]
        res = pipeline.calibrate(pt, rm, modes, sel, mix, n=n_tm, seed=seed)
        mj, k, v = pipeline.map_theta(res, G)
        dci = posterior_disp_ci(ev, res, G, rng)
        key = "proposed" if lay == "efi" else "proposed_emp_layout"
        rec["methods"][key] = ev(mj, (k, v), res["lo"], res["hi"], disp_ci=dci,
                                 th_samples=np.column_stack([res["kappa"], res["logkv"]]))
        rec["methods"][key]["tmcmc_stages"] = res["stages"]
    return rec


def summarize(trials, keys):
    out = {}
    for m in keys:
        rows = [t["methods"][m] for t in trials if m in t["methods"]]
        if not rows:
            continue
        s = {}
        for k, v in rows[0].items():
            if isinstance(v, bool) or (isinstance(v, (int, float)) and not isinstance(v, bool)):
                arr = np.array([float(r[k]) for r in rows if k in r])
                s[k] = {"mean": float(arr.mean()), "std": float(arr.std()), "min": float(arr.min()),
                        "max": float(arr.max())}
        s["n"] = len(rows)
        out[m] = s
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--trials", type=int, default=4)
    args = ap.parse_args()
    n_tm = 300 if args.quick else 500
    ntr = 1 if args.quick else args.trials
    T0 = time.time()
    all_trials, setup = [], {}
    sens = []
    for kind, cfg in TOWERS.items():
        t0 = time.time()
        g = make_graph(kind, cfg["ins"])
        di, pt, prior = pipeline.prepare(g, neighbor_xy=cfg["neighbor"], n_scen=12 if args.quick else 16, seed=7)
        mix = pipeline.mixture_prior(pt, prior)
        rm = pipeline.reduced_model(pt, prior["map"])
        # 代理模型精度：在 3 个随机参数点比较降阶与全模型前 8 阶频率
        rr = np.random.default_rng(3)
        errs = []
        for _ in range(3):
            th = mix.sample(1, rr)[0]
            G = len(pt.groups)
            j = np.clip(np.rint(th[:G]).astype(int), 0, len(ORDER) - 1)
            ff, _ = pt.modes(secs_of(pt, j), th[G], th[G + 1], n=8)
            fr, _ = rm.eig(CAT_A[j], CAT_I[j], CAT_J[j], th[G], th[G + 1], n=8)
            errs.append(float(np.max(np.abs(fr - ff) / ff)))
        setup[kind] = {"design_input": di.to_dict(), "n_groups": len(pt.groups), "n_members": g.n_members,
                       "n_nodes": g.n_nodes, "rom_dim": rm.r, "rom_freq_err_max": max(errs),
                       "prior_build_s": time.time() - t0,
                       "prior_entropy_mean": float(np.mean(-np.sum(prior["pmf"] * np.log(prior["pmf"] + 1e-300), 1))),
                       "map_sections_sample": dict(list(prior["map"].items())[:6])}
        print(kind, "setup", round(time.time() - t0, 1), "s", flush=True)
        for s in range(ntr):
            t1 = time.time()
            rec = run_trial(kind, g, di, pt, prior, mix, rm, seed=s + (100 if kind == "tension" else 0), n_tm=n_tm)
            all_trials.append(rec)
            print(kind, s, round(time.time() - t1, 1), "s",
                  {m: round(v["group_hit"], 2) for m, v in rec["methods"].items()}, flush=True)
        if kind == "suspension":
            # 噪声敏感性：噪声底 / 同步误差
            for lab, nz in (("低噪声 5µg", excitation.MemsNoise(noise_density_ug=5.0)),
                            ("基准 25µg/0.5ms", excitation.MemsNoise()),
                            ("高噪声 100µg", excitation.MemsNoise(noise_density_ug=100.0)),
                            ("同步误差 5ms", excitation.MemsNoise(sync_std_ms=5.0)),
                            ("同步误差 20ms", excitation.MemsNoise(sync_std_ms=20.0))):
                for s in range(1 if args.quick else 2):
                    rec = run_trial(kind, g, di, pt, prior, mix, rm, seed=50 + s, n_tm=n_tm, noise=nz,
                                    layouts=("efi",), methods=False)
                    sens.append({"case": lab, "seed": 50 + s, "layout": rec["layouts"]["efi"],
                                 "proposed": rec["methods"]["proposed"]})
                    print("sens", lab, s, rec["layouts"]["efi"]["n_valid"], flush=True)
    keys = ["ptm_uniform", "reverse_only", "vib_only", "vib_only_groupwise", "proposed", "proposed_emp_layout"]
    summ = {"all": summarize(all_trials, keys)}
    for kind in TOWERS:
        summ[kind] = summarize([t for t in all_trials if t["kind"] == kind], keys)
    lay = {}
    for l in ("efi", "emp"):
        rows = [t["layouts"][l] for t in all_trials]
        lay[l] = {k: float(np.mean([r[k] for r in rows if r[k] is not None]))
                  for k in ("n_valid", "n_true_modes_found", "freq_id_err_mean", "mac_id_mean", "fim_logdet",
                            "max_offdiag_mac")}
    out = {"setup": setup, "trials": all_trials, "summary": summ, "layouts": lay, "sensitivity": sens,
           "runtime_s": time.time() - T0, "n_tmcmc": n_tm, "assess_scenario": ASSESS, "ptm_uniform": PTM_UNIFORM}
    with open(os.path.join(DATA, "sim_results.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1, default=lambda o: o.tolist() if hasattr(o, "tolist") else str(o))
    print("done", round(time.time() - T0, 1), "s")


if __name__ == "__main__":
    main()
