# -*- coding: utf-8 -*-
"""专利E 仿真验证总脚本（可分任务并行运行，结果写入 ../数据/）。

用法（项目根目录）：
  .venv\\Scripts\\python.exe -u <本脚本> calib            # 采样带亚像素位移噪声标定（梯度法、相位法；不同带长）
  .venv\\Scripts\\python.exe -u <本脚本> main             # 5 个随机场景：本发明 + 人工靶点(+SEREP) + 全部采样带 SOBI；seed0 保存作图数据
  .venv\\Scripts\\python.exe -u <本脚本> ablA|ablB|ablC|ablD  # 消融与敏感性（每任务若干变体 × 3 个场景）
  .venv\\Scripts\\python.exe -u <本脚本> merge            # 合并为 ../数据/results.json 与 ../关键结果摘要.json
"""
import glob
import json
import os
import pickle
import sys
import time
from dataclasses import replace

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SIM = os.path.dirname(HERE)
DATA = os.path.join(SIM, "数据")
os.makedirs(DATA, exist_ok=True)
sys.path.insert(0, os.path.join(SIM, "..", "03_算法与软件"))
from trussvid import pipeline as PL  # noqa: E402
from trussvid import synth as SY  # noqa: E402

LOGF = None
BASE = PL.ExpCfg()
SEEDS_MAIN = (0, 1, 2, 3, 4)
SEEDS_ABL = (0, 1, 2)


def log(*a):
    s = " ".join(str(x) for x in a)
    print(s, flush=True)
    if LOGF:
        with open(LOGF, "a", encoding="utf-8") as fh:
            fh.write(s + "\n")


def jsonable(o):
    if isinstance(o, dict):
        return {str(k): jsonable(v) for k, v in o.items() if not str(k).startswith("_")}
    if isinstance(o, (list, tuple)):
        return [jsonable(v) for v in o]
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    return o


def save(name, obj):
    with open(os.path.join(DATA, name), "w", encoding="utf-8") as fh:
        json.dump(jsonable(obj), fh, ensure_ascii=False, indent=1)
    log("写出", name)


VARIANTS = {
    "仅背景点补偿（无联合补偿）": dict(joint_shake=False),
    "无自振补偿": dict(shake_comp="none"),
    "背景点+陀螺融合": dict(shake_comp="fusion"),
    "无残余时间偏差校正": dict(sync_corr=False),
    "软件授时(±10 ms)+校正": dict(tau_ms=(0.0, 12.0, -8.0)),
    "软件授时(±10 ms)无校正": dict(tau_ms=(0.0, 12.0, -8.0), sync_corr=False),
    "两相机(夹角90°)": dict(n_cams=2, azimuths_deg=(20.0, 110.0)),
    "两相机(夹角30°)": dict(n_cams=2, azimuths_deg=(20.0, 50.0)),
    "单相机(方位0°)": dict(n_cams=1, azimuths_deg=(0.0,)),
    "不白化": dict(whiten=False),
    "不重加权": dict(reweight=False),
    "相位法位移估计": dict(method="phase"),
    "采样带噪声×2": dict(band_noise_scale=2.0),
    "大气湍流×2": dict(turb_urad=6.0),
    "帧率25fps": dict(fps=25.0),
    "距离150m": dict(distance=150.0),
    "风速6m/s": dict(U10=6.0),
    "记录600s": dict(duration=600.0),
}
GROUPS = {
    "ablA": ["仅背景点补偿（无联合补偿）", "无自振补偿", "背景点+陀螺融合", "无残余时间偏差校正", "软件授时(±10 ms)+校正"],
    "ablB": ["软件授时(±10 ms)无校正", "两相机(夹角90°)", "两相机(夹角30°)", "单相机(方位0°)"],
    "ablC": ["不白化", "不重加权", "相位法位移估计", "采样带噪声×2", "大气湍流×2"],
    "ablD": ["帧率25fps", "距离150m", "风速6m/s", "记录600s"],
}


def slim(r):
    keys = ("label", "n_eval", "eval_modes", "n_freq_id", "n_freq_1pct", "n_matched", "n_mac80", "n_mac90",
            "mac_mean_all", "mac_per_true_mode", "f_err_mean", "f_err_max", "zeta_err_mean", "cond", "tau_true_ms",
            "tau_est_ms", "n_obs", "cams", "per_mode", "mac_vs_nominal", "t_s", "f_true", "zeta_true")
    return {k: r.get(k) for k in keys}


def task_calib():
    out = {}
    for method in ("gradient", "phase"):
        for bl in (12, 24, 48):
            out[f"{method}_带长{bl}"] = SY.calibrate_band_noise(method=method, band_len=bl, n_trials=600)
            log(method, bl, {k: round(v["std_px"], 4) for k, v in out[f"{method}_带长{bl}"].items()})
    save("calib.json", out)


def task_main():
    out = {}
    for s in SEEDS_MAIN:
        cfg = replace(BASE, seed=s)
        tr = PL.TruthCache.get(cfg.U10, cfg.duration, cfg.fps, cfg.seed)
        log(f"== seed{s}  真值频率 {np.round(tr.freq[:12], 3).tolist()}  评价模态 {[k + 1 for k in tr.info['eval_modes']]}")
        r = PL.run(cfg, baselines=True, keep=(s == 0), log=log)
        if s == 0:
            ar = r.pop("_arrays")
            n = len(tr.g.nodes)
            figd = {"modes": ar["modes"], "shapes": ar["shapes"], "Phi": ar["Phi"], "Phi_true": ar["Phi_true"],
                    "f_nom": ar["f_nom"], "match": ar["match"], "Q": ar["Q"][:6000], "Y0": ar["Y0"][:6000],
                    "nodes": tr.g.nodes, "mi": tr.g.ends()[0], "mj": tr.g.ends()[1], "cat": list(tr.g.cat),
                    "freq": tr.freq, "zeta": tr.zeta, "eval_modes": tr.info["eval_modes"],
                    "eff_mass": tr.info["eff_mass"], "fps": cfg.fps,
                    "samples": [{"uv": S.uv, "nrm": S.nrm, "member": S.member, "width_px": S.width_px} for S in ar["samples"]],
                    "cams": [{"C": c.C, "R": c.R, "f": c.f, "W": c.W, "H": c.H, "name": c.name} for c in ar["cams"]],
                    "om_res": [o[:6000] for o in ar["om_res"]], "q_true": tr.q[:6000], "t": tr.t[:6000]}
            pickle.dump(figd, open(os.path.join(DATA, "_figdata_main.pkl"), "wb"))
            log("写出 _figdata_main.pkl")
        out[f"seed{s}"] = {"本发明": slim(r), "人工靶点": r["baselines"]["人工靶点"], "盲源分离": r["baselines"]["盲源分离"],
                           "truth": {"freq": tr.freq[:12].tolist(), "zeta": tr.zeta[:12].tolist(),
                                     "eval_modes": [k + 1 for k in tr.info["eval_modes"]],
                                     "eff_mass": np.round(np.asarray(tr.info["eff_mass"])[:12], 4).tolist()}}
        save("main.json", out)
        PL.TruthCache._c.clear()


def task_abl(group):
    out = {}
    for s in SEEDS_ABL:
        for nm in GROUPS[group]:
            cfg = replace(BASE, seed=s, label=nm, **VARIANTS[nm])
            log(f"== {nm} seed{s}")
            r = PL.run(cfg, log=log)
            out.setdefault(nm, {})[f"seed{s}"] = slim(r)
            save(f"{group}.json", out)
        PL.TruthCache._c.clear()


def agg(rs, key):
    v = [r[key] for r in rs if r.get(key) is not None and not (isinstance(r[key], float) and np.isnan(r[key]))]
    return (float(np.mean(v)), float(np.std(v))) if v else (None, None)


def task_merge():
    res = {}
    for f in ["calib.json", "main.json"] + [f"{g}.json" for g in GROUPS]:
        p = os.path.join(DATA, f)
        if os.path.exists(p):
            res[f[:-5]] = json.load(open(p, encoding="utf-8"))
    save("results.json", res)
    key = {}
    M = res.get("main", {})
    if M:
        P = [v["本发明"] for v in M.values()]
        T = [v["人工靶点"] for v in M.values()]
        B = [v["盲源分离"] for v in M.values()]
        key["场景数"] = len(P)
        key["评价模态数"] = P[0]["n_eval"]
        for nm, rs in (("本发明", P), ("人工靶点", T)):
            for k in ("n_freq_1pct", "n_mac90", "n_mac80", "mac_mean_all", "f_err_mean", "zeta_err_mean"):
                m, s = agg(rs, k)
                if m is not None:
                    key[f"{nm}_{k}_均值"] = round(m, 4); key[f"{nm}_{k}_标准差"] = round(s, 4)
        m, s = agg(B, "n_freq_1pct")
        key["盲源分离_n_freq_1pct_均值"] = round(m, 3) if m is not None else None
        # 逐阶 MAC 均值
        per = np.array([r["mac_per_true_mode"] for r in P])
        key["本发明_逐阶MAC均值"] = np.round(per.mean(0), 3).tolist()
        pt = np.array([r["mac_per_true_mode"] for r in T])
        key["人工靶点SEREP_逐阶MAC均值"] = np.round(pt.mean(0), 3).tolist()
        key["人工靶点局部_逐阶MAC均值"] = np.round(np.array([r["mac_local_per_true_mode"] for r in T]).mean(0), 3).tolist()
        key["评价模态"] = P[0]["eval_modes"]
        key["相机自振残余_μrad_均值"] = round(float(np.mean([c["shake_res_urad"] for r in P for c in r["cams"]])), 3)
        key["背景点补偿后残余_μrad_均值"] = round(float(np.mean([c["shake_res_bg_urad"] for r in P for c in r["cams"]])), 3)
        key["时间偏差估计误差_ms_均值"] = round(float(np.mean([abs(a - b) for r in P for a, b in
                                                     zip(r["tau_est_ms"][1:], r["tau_true_ms"][1:])])), 4)
        key["每相机采样带数"] = [c["n_bands"] for c in P[0]["cams"]]
        key["地面采样距离_mm"] = round(P[0]["cams"][0]["gsd_mm"], 2)
    for g in GROUPS:
        for nm, d in res.get(g, {}).items():
            rs = list(d.values())
            for k in ("n_freq_1pct", "n_mac90", "mac_mean_all"):
                m, s = agg(rs, k)
                if m is not None:
                    key[f"消融_{nm}_{k}"] = round(m, 3)
    save("../关键结果摘要.json", key)


TASKS = {"calib": task_calib, "main": task_main, "merge": task_merge}
for _g in GROUPS:
    TASKS[_g] = (lambda g: (lambda: task_abl(g)))(_g)

if __name__ == "__main__":
    task = sys.argv[1] if len(sys.argv) > 1 else "main"
    LOGF = os.path.join(DATA, f"run_log_{task}.txt")
    open(LOGF, "w", encoding="utf-8").close()
    t0 = time.time()
    TASKS[task]()
    log(f"任务 {task} 完成，用时 {time.time() - t0:.0f}s")
