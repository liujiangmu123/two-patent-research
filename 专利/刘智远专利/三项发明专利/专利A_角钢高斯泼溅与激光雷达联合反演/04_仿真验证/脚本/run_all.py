# -*- coding: utf-8 -*-
"""专利A 仿真验证总脚本（可分任务并行运行，结果写入 ../数据/）。

用法（项目根目录）：
  .venv\\Scripts\\python.exe -u <本脚本> main        # seed1：场景、PTM 式基线、本发明（含置信度）、有限元、校准、多期变化检测
  .venv\\Scripts\\python.exe -u <本脚本> abl1|abl1b|abl2|abl2b|abl3   # seed1：消融（每任务 2 个变体）
  .venv\\Scripts\\python.exe -u <本脚本> seed2|seed3|seed4            # 其他场景：PTM 式基线 + 本发明（重复性、外推校准）
  .venv\\Scripts\\python.exe -u <本脚本> sens_d0.025|sens_d0.1|sens_r40  # 激光点密度与影像地面采样距离敏感性
  .venv\\Scripts\\python.exe -u <本脚本> merge       # 合并为 ../数据/results.json 与 ../关键结果摘要.json
"""
import copy
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
from anglegs import pipeline as PL  # noqa: E402
from anglegs import synth as SY  # noqa: E402
from anglegs.optimize import Stage  # noqa: E402
from anglegs.surfels import sigmoid  # noqa: E402

LOGF = None


def log(*a):
    s = " ".join(str(x) for x in a)
    print(s, flush=True)
    if LOGF:
        with open(LOGF, "a", encoding="utf-8") as fh:
            fh.write(s + "\n")


def save(name, obj):
    with open(os.path.join(DATA, name), "w", encoding="utf-8") as fh:
        json.dump(PL.to_jsonable(obj), fh, ensure_ascii=False, indent=1)
    log("写出", name)


def scene_info(scene):
    U = scene.U
    return {"preset": scene.sc.preset, "seed": scene.sc.seed, "nodes": int(len(U.nodes_true)),
            "members_design": int(U.g_design.n_members), "members_universe": int(U.n_members),
            "members_true": int(U.exist.sum()), "damaged": U.damaged, "false_neg": U.false_neg,
            "spurious": int(U.is_cand.sum() - len(U.false_neg)), "asym_nodes": U.asym_nodes,
            "rotated_members": int(np.sum(np.abs(((U.phi - scene.init["phi"]) + np.pi) % (2 * np.pi) - np.pi) > 0.5)),
            "gauge_eccentric_members": int(np.sum(np.hypot(U.d1, U.d2) > 0.015)),
            "H_m": float(U.nodes_true[:, 2].max()), "lidar": scene.lidar_stats, "camera": scene.cam_stats,
            "ext_true": {"omega_mrad": (1e3 * scene.ext_true.omega).tolist(), "lever_m": scene.ext_true.lever.tolist(),
                         "dt_ms": 1e3 * scene.ext_true.dt},
            "baseline": scene.base_info, "t_build_s": scene.t_build}


def run_named(scene, name, fisher=0):
    t0 = time.time()
    log(f"== {name}")
    r = PL.run_variant(scene, PL.VARIANTS[name], log=log, fisher_M=fisher)
    log(f"   {name}: RMSEn={r['metrics']['RMSEn_m']:.4f} 肢宽MAE={r['metrics']['width_MAE_mm']:.2f}mm "
        f"朝向正确率={r['metrics']['orient_correct_rate']:.3f} 偏心误差={r['metrics']['delta_err_mm']:.1f}mm "
        f"AUC={r['metrics']['exist_AUC']:.4f}  {time.time() - t0:.0f}s")
    return r


def task_main():
    sc = PL.SceneCfg(seed=1)
    scene = PL.Scene(sc, log=log)
    r_ptm, r_init = PL.ptm_metrics(scene)
    run = run_named(scene, "本发明", fisher=48)
    fe = PL.fe_compare(scene, {"本发明": run})
    cal = PL.calibration(scene, run)
    log("校准", cal)
    # 多期变化检测（权利要求：以前期结果为初值，仅优化节点与存在概率）
    chg = change_detection(scene, run)
    out = {"scene": scene_info(scene), "初始": r_init, "PTM 式基线": r_ptm, "本发明": run["metrics"],
           "本发明_hist": [{k: v for k, v in h.items() if k != "detail"} for h in run["hist"]],
           "有限元": fe, "置信度校准": cal, "多期变化检测": chg, "fisher_t_s": run.get("t_fisher")}
    save("main.json", out)
    U = scene.U
    figd = {"P": run["P"], "b_snap": run["b_snap"], "present": run["present"], "b_cont": run["b_cont"],
            "conf": run["conf"], "node_cov": run["node_cov"], "V_base": scene.V_base, "V_noisy": scene.V_noisy,
            "U": {"nodes_true": U.nodes_true, "mi": U.mi, "mj": U.mj, "cat": U.cat, "part": U.part, "exist": U.exist,
                  "in_init": U.in_init, "is_cand": U.is_cand, "b": U.b, "phi": U.phi, "d1": U.d1, "d2": U.d2,
                  "r": U.r, "damaged": U.damaged, "false_neg": U.false_neg, "sec": U.sec},
            "init_phi": scene.init["phi"], "points": scene.points[::4],
            "cam_uv_sample": None}
    pickle.dump(figd, open(os.path.join(DATA, "_figdata_main.pkl"), "wb"))
    log("写出 _figdata_main.pkl")


def change_detection(scene, run):
    """第二期：一根斜材缺失、一个横担节点位移 6 cm；以前期结果为初值复测。"""
    U1 = scene.U
    U2 = copy.deepcopy(U1)
    present1 = run["present"]
    cand = [e for e in range(U1.n_members) if U1.exist[e] and present1[e] and U1.cat[e] == "diagonal"
            and U1.part[e] == "body" and 15 < U1.nodes_true[U1.mi[e], 2] < 40]
    rng = np.random.default_rng(77)
    lost = int(rng.choice(cand))
    U2.exist[lost] = False
    arm_nodes = sorted(set(U1.mi[np.array(U1.part) == "arm"]) | set(U1.mj[np.array(U1.part) == "arm"]))
    moved = int(arm_nodes[len(arm_nodes) // 3])
    U2.nodes_true = U1.nodes_true.copy()
    U2.nodes_true[moved] += np.array([0.0, 0.03, -0.05])
    P1 = run["P"]
    init2 = dict(V=P1["V"].copy(), b=run["b_snap"].copy(), phi=P1["phi"].copy(), d1=P1["d1"].copy(),
                 d2=P1["d2"].copy(), logit=np.where(present1, 3.0, -7.0))
    sc2 = replace(scene.sc, seed=scene.sc.seed + 50)
    scene2 = PL.Scene(sc2, log=log, U=U2, init_override=init2, cams_seed_offset=5)
    stages = (Stage("复测 S1 配准（截面与规格继承）", ("V", "app", "ext"), 40, 0.012, False, 1),
              Stage("复测 S3 存在与节点", ("V", "logit", "app", "ext"), 50, 0.0, False, 1, "all"),
              Stage("复测 S4 微调", ("V", "phi", "d1", "d2", "app", "ext"), 30, 0.0, False, 1))
    cfg = replace(PL.VARIANTS["本发明"], label="复测")
    r2 = PL.run_variant(scene2, cfg, log=log, stages=stages, fisher_M=32)
    P2 = r2["P"]
    dV = np.linalg.norm(P2["V"] - P1["V"], axis=1)
    sig = r2["conf"]["sig_v"]
    flag_nodes = np.flatnonzero(dV > np.maximum(3 * np.hypot(sig, run["conf"]["sig_v"]), 0.02))
    lost_flag = [int(e) for e in np.flatnonzero(present1 & ~r2["present"])]
    return {"lost_member": lost, "moved_node": moved, "moved_disp_m": [0.0, 0.03, -0.05],
            "detected_lost": lost in lost_flag, "flagged_lost_members": lost_flag,
            "detected_moved": moved in flag_nodes.tolist(), "flagged_nodes": flag_nodes.tolist(),
            "moved_node_est_disp_m": float(dV[moved]), "moved_node_sigma_m": float(sig[moved]),
            "false_node_flags": int(len(set(flag_nodes.tolist()) - {moved})),
            "false_member_flags": int(len(set(lost_flag) - {lost})), "metrics_epoch2": r2["metrics"]}


def task_abl(names, tag):
    sc = PL.SceneCfg(seed=1)
    scene = PL.Scene(sc, log=log)
    out = {}
    for nm in names:
        r = run_named(scene, nm)
        out[nm] = r["metrics"]
        out[nm + "_hist"] = [{k: v for k, v in h.items() if k != "detail"} for h in r["hist"]]
        if nm in ("仅激光（降级模式）", "圆柱基元"):
            out[nm + "_有限元"] = PL.fe_compare(scene, {nm: r})[nm]
        save(f"{tag}.json", out)


def _z_stats(scene, r):
    """保存节点马氏距离平方与肢宽标准化误差，供合并时以 seed1 的膨胀系数检验外推覆盖率。"""
    U = scene.U
    V = r["P"]["V"]
    err = V - U.nodes_true
    used = np.zeros(len(V), bool)
    used[U.mi[U.exist]] = True; used[U.mj[U.exist]] = True
    z2 = np.array([e @ np.linalg.solve(C, e) for e, C in zip(err, r["node_cov"])])[used]
    ex = U.exist & r["present"]
    bz = (r["b_cont"][ex] - U.b[ex]) / np.maximum(r["conf"]["sig_b"][ex], 1e-6)
    return {"node_z2": z2.tolist(), "width_z": bz.tolist()}


def task_seed(s):
    """重复性 + 置信度外推校准（膨胀系数 κ 取 seed1 主实验值，在合并步骤计算覆盖率）。"""
    scene = PL.Scene(PL.SceneCfg(seed=s), log=log)
    r_ptm, r_init = PL.ptm_metrics(scene)
    r = run_named(scene, "本发明", fisher=48)
    fe = PL.fe_compare(scene, {"本发明": r})
    cal = PL.calibration(scene, r)
    log("校准", cal)
    out = {f"seed{s}": {"scene": scene_info(scene), "初始": r_init, "PTM 式基线": r_ptm, "本发明": r["metrics"],
                        "有限元": fe, "置信度校准": cal, "z": _z_stats(scene, r)}}
    save(f"seed_{s}.json", out)


def task_sens(which):
    if which.startswith("d"):
        decim = float(which[1:])
        scene = PL.Scene(PL.SceneCfg(seed=1, decim=decim), log=log)
        r_ptm, _ = PL.ptm_metrics(scene)
        r = run_named(scene, "本发明")
        out = {f"激光抽取{decim}": {"density_pts_m2": scene.lidar_stats["density_pts_m2"], "PTM 式基线": r_ptm,
                                  "本发明": r["metrics"]}}
    else:
        rad = float(which[1:])
        scene = PL.Scene(PL.SceneCfg(seed=1, radius=rad), log=log)
        r_ptm, _ = PL.ptm_metrics(scene)
        r = run_named(scene, "本发明")
        out = {f"环绕半径{rad:g}m": {"gsd_mm": rad / scene.cams[0].f * 1000, "PTM 式基线": r_ptm, "本发明": r["metrics"]}}
    save(f"sens_{which}.json", out)


def task_merge():
    import glob
    res = {}
    for f in ("main.json", "abl1.json", "abl1b.json", "abl2.json", "abl2b.json", "abl3.json", "abl4.json"):
        p = os.path.join(DATA, f)
        if os.path.exists(p):
            res[f[:-5]] = json.load(open(p, encoding="utf-8"))
    res["seeds"] = {}
    for p in sorted(glob.glob(os.path.join(DATA, "seed_*.json"))):
        res["seeds"].update(json.load(open(p, encoding="utf-8")))
    res["sens"] = {}
    for p in sorted(glob.glob(os.path.join(DATA, "sens_*.json"))):
        res["sens"].update(json.load(open(p, encoding="utf-8")))
    # 外推校准：以 seed1 的 κ 检验其余场景
    cal1 = res.get("main", {}).get("置信度校准", {})
    for k, v in res["seeds"].items():
        z = v.pop("z", None)
        if z and cal1:
            z2 = np.asarray(z["node_z2"]); bz = np.asarray(z["width_z"])
            v["置信度校准"]["kappa_ext"] = cal1["kappa"]
            v["置信度校准"]["coverage95_ext"] = float(np.mean(z2 / cal1["kappa"] ** 2 < 7.815))
            v["置信度校准"]["width_kappa_ext"] = cal1["width_kappa"]
            v["置信度校准"]["width_coverage95_ext"] = float(np.mean(np.abs(bz) / cal1["width_kappa"] < 1.96))
    save("results.json", res)
    M = res.get("main", {})
    key = {}
    if M:
        b, o = M["PTM 式基线"], M["本发明"]
        key.update({
            "节点RMSE_PTM_m": round(b["RMSEn_m"], 4), "节点RMSE_本发明_m": round(o["RMSEn_m"], 4),
            "节点RMSE降幅": round(1 - o["RMSEn_m"] / b["RMSEn_m"], 3),
            "肢宽MAE_PTM_mm": round(b["width_MAE_mm"], 1), "肢宽MAE_本发明_mm": round(o["width_MAE_mm"], 1),
            "肢宽档正确率": round(o["width_class_acc"], 3), "肢宽档±1正确率": round(o["width_class_acc_pm1"], 3),
            "朝向正确率_本发明": round(o["orient_correct_rate"], 3), "朝向正确率_初始": round(M["初始"]["orient_correct_rate"], 3),
            "偏心误差_初始_mm": round(M["初始"]["delta_err_mm"], 1), "偏心误差_本发明_mm": round(o["delta_err_mm"], 1),
            "存在AUC": round(o["exist_AUC"], 4), "缺材识别": f"{o['damaged_removed']}/{o['damaged_total']}",
            "漏检补回": f"{o['falseneg_recovered']}/{o['falseneg_total']}",
            "伪候选剔除": f"{o['spurious_rejected']}/{o['spurious_total']}",
            "NGED_本发明": round(o["NGED_all"], 4), "NGED_PTM": round(b["NGED_all"], 4),
        })
        fe = M["有限元"]
        key["塔顶位移误差_PTM"] = round(fe["PTM 式基线"]["tip_err_rel"], 3)
        key["塔顶位移误差_本发明"] = round(fe["本发明"]["tip_err_rel"], 3)
        key["频率最大误差_PTM"] = round(fe["PTM 式基线"]["freq_err_rel_max"], 3)
        key["频率最大误差_本发明"] = round(fe["本发明"]["freq_err_rel_max"], 3)
        key.update({f"校准_{k}": (round(v, 3) if isinstance(v, float) else v) for k, v in M["置信度校准"].items()})
        ch = M["多期变化检测"]
        key["复测_缺失杆件检出"] = ch["detected_lost"]
        key["复测_位移节点检出"] = ch["detected_moved"]
        key["复测_误报节点数"] = ch["false_node_flags"]
        key["复测_误报杆件数"] = ch["false_member_flags"]
    for g in ("abl1", "abl1b", "abl2", "abl2b", "abl3", "abl4"):
        for k, v in res.get(g, {}).items():
            if isinstance(v, dict) and "RMSEn_m" in v:
                key[f"消融_{k}_RMSEn_m"] = round(v["RMSEn_m"], 4)
                key[f"消融_{k}_肢宽MAE_mm"] = round(v["width_MAE_mm"], 2)
                key[f"消融_{k}_朝向正确率"] = round(v["orient_correct_rate"], 3)
                key[f"消融_{k}_存在AUC"] = round(v["exist_AUC"], 4)
    sd = res.get("seeds", {})
    if sd and M:
        allr = [M] + [sd[k] for k in sorted(sd)]
        for nm, kk in (("RMSEn_m", "节点RMSE"), ("width_MAE_mm", "肢宽MAE_mm"), ("orient_correct_rate", "朝向正确率"),
                       ("exist_AUC", "存在AUC")):
            a = np.array([r["本发明"][nm] for r in allr]); b = np.array([r["PTM 式基线"][nm] for r in allr])
            key[f"多场景_{kk}_本发明_均值"] = round(float(a.mean()), 4); key[f"多场景_{kk}_本发明_标准差"] = round(float(a.std()), 4)
            key[f"多场景_{kk}_PTM_均值"] = round(float(b.mean()), 4)
        key["多场景_场景数"] = len(allr)
        cov = [sd[k]["置信度校准"].get("coverage95_ext") for k in sorted(sd)]
        key["外推校准_节点95覆盖率"] = [round(c, 3) for c in cov if c is not None]
    save("../关键结果摘要.json", key)


TASKS = {
    "main": task_main,
    "abl1": lambda: task_abl(["仅激光（降级模式）", "仅影像"], "abl1"),
    "abl1b": lambda: task_abl(["圆柱基元", "独立端点（不共享节点）"], "abl1b"),
    "abl2": lambda: task_abl(["无足迹模型", "无负证据"], "abl2"),
    "abl2b": lambda: task_abl(["无对称软先验", "无外参时间标定"], "abl2b"),
    "abl3": lambda: task_abl(["无逐杆件假设检验", "无朝向可观测性门控"], "abl3"),
    "abl4": lambda: task_abl(["仅激光无足迹模型", "仅激光无负证据"], "abl4"),
    "seed2": lambda: task_seed(2), "seed3": lambda: task_seed(3), "seed4": lambda: task_seed(4),
    "sens_d0.025": lambda: task_sens("d0.025"), "sens_d0.1": lambda: task_sens("d0.1"),
    "sens_r40": lambda: task_sens("r40"),
    "merge": task_merge,
}

if __name__ == "__main__":
    task = sys.argv[1] if len(sys.argv) > 1 else "main"
    LOGF = os.path.join(DATA, f"run_log_{task}.txt")
    open(LOGF, "w", encoding="utf-8").close()
    t0 = time.time()
    TASKS[task]()
    log(f"任务 {task} 完成，用时 {time.time() - t0:.0f}s")
