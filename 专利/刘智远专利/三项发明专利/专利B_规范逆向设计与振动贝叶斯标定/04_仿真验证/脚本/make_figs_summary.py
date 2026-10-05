# -*- coding: utf-8 -*-
"""读取 ../数据/sim_results.json，生成图（SimHei）与 关键结果摘要.json。"""
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

plt.rcParams["font.sans-serif"] = ["SimHei"]
plt.rcParams["axes.unicode_minus"] = False
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
D = json.load(open(os.path.join(ROOT, "数据", "sim_results.json"), encoding="utf-8"))
FIG = os.path.join(ROOT, "图"); os.makedirs(FIG, exist_ok=True)
S = D["summary"]["all"]
NAMES = {"ptm_uniform": "PTM统一截面", "reverse_only": "仅逆向设计", "vib_only": "仅振动(缩放修正)",
         "vib_only_groupwise": "仅振动(逐组均匀先验)", "proposed": "本发明", "proposed_emp_layout": "本发明+经验测点"}
KEYS = [k for k in NAMES if k in S]


def m(k, met):
    return S[k][met]["mean"] if met in S[k] else np.nan


def sd(k, met):
    return S[k][met]["std"] if met in S[k] else 0


metrics = [("group_hit", "截面组识别率"), ("freq_err_mean_6", "前6阶频率误差"), ("mac_mean_6", "前6阶MAC"),
           ("disp_err", "塔顶位移相对误差"), ("ratio_err_crit", "临界杆件应力比误差"), ("misjudge_rate", "验算结论误判率")]
fig, axs = plt.subplots(2, 3, figsize=(14, 7.5))
for ax, (met, lab) in zip(axs.ravel(), metrics):
    v = [m(k, met) for k in KEYS]; e = [sd(k, met) for k in KEYS]
    ax.bar(range(len(KEYS)), v, yerr=e, color=["#999", "#6a9", "#c96", "#d88", "#36c", "#8ad"][:len(KEYS)], capsize=3)
    ax.set_xticks(range(len(KEYS))); ax.set_xticklabels([NAMES[k] for k in KEYS], rotation=30, ha="right", fontsize=8)
    ax.set_title(lab)
    for i, x in enumerate(v):
        ax.text(i, x, f"{x:.3f}", ha="center", va="bottom", fontsize=7)
fig.tight_layout(); fig.savefig(os.path.join(FIG, "图1_方法对比.png"), dpi=150); plt.close(fig)

L = D["layouts"]
fig, axs = plt.subplots(1, 4, figsize=(13, 3.4))
for ax, (k, lab) in zip(axs, [("n_valid", "有效识别模态数"), ("fim_logdet", "Fisher信息 log det"),
                              ("max_offdiag_mac", "最大非对角 AutoMAC"), ("freq_id_err_mean", "识别频率误差")]):
    ax.bar([0, 1], [L["efi"][k], L["emp"][k]], color=["#36c", "#c96"])
    ax.set_xticks([0, 1]); ax.set_xticklabels(["有效独立法", "经验布置"]); ax.set_title(lab)
fig.tight_layout(); fig.savefig(os.path.join(FIG, "图2_测点优化对比.png"), dpi=150); plt.close(fig)

sens = D["sensitivity"]
cases = list(dict.fromkeys(s["case"] for s in sens))
fig, ax = plt.subplots(1, 2, figsize=(10, 3.6))
ax[0].bar(range(len(cases)), [np.mean([s["layout"]["n_valid"] for s in sens if s["case"] == c]) for c in cases])
ax[0].set_title("有效识别模态数"); ax[1].bar(range(len(cases)),
                                       [np.mean([s["proposed"]["misjudge_rate"] for s in sens if s["case"] == c]) for c in cases])
ax[1].set_title("本发明验算误判率")
for a in ax:
    a.set_xticks(range(len(cases))); a.set_xticklabels(cases, rotation=25, ha="right", fontsize=8)
fig.tight_layout(); fig.savefig(os.path.join(FIG, "图3_噪声与同步误差敏感性.png"), dpi=150); plt.close(fig)

# 关键结果摘要
key = {"来源": "04_仿真验证/数据/sim_results.json（run_sim.py 生成）", "试验数": {k: S[k]["n"] for k in KEYS},
       "tmcmc样本数": D["n_tmcmc"], "总耗时_s": round(D["runtime_s"], 1),
       "降阶代理": {k: {"维数": v["rom_dim"], "频率最大误差": round(v["rom_freq_err_max"], 4),
                    "杆件数": v["n_members"], "截面组数": v["n_groups"]} for k, v in D["setup"].items()},
       "设计输入提取": {k: {kk: v["design_input"][kk] for kk in ("voltage_kV", "voltage_conf", "tower_type",
                                                            "line_angle_deg", "call_height", "span_h")}
                    for k, v in D["setup"].items()},
       "方法对比_均值": {NAMES[k]: {lab: round(m(k, met), 4) for met, lab in metrics + [
           ("group_within1", "截面组±1档识别率"), ("coverage_groups", "截面组90%后验覆盖率"),
           ("coverage_kappa", "κ后验覆盖率"), ("coverage_logkv", "基础刚度后验覆盖率"),
           ("coverage_disp", "塔顶位移90%区间覆盖率")] if not np.isnan(m(k, met))} for k in KEYS},
       "测点优化": {"有效独立法": {k: round(v, 4) for k, v in L["efi"].items()},
                "经验布置": {k: round(v, 4) for k, v in L["emp"].items()}},
       "噪声敏感性": {c: {"有效模态数": float(np.mean([s["layout"]["n_valid"] for s in sens if s["case"] == c])),
                     "误判率": round(float(np.mean([s["proposed"]["misjudge_rate"] for s in sens if s["case"] == c])), 4),
                     "截面组识别率": round(float(np.mean([s["proposed"]["group_hit"] for s in sens if s["case"] == c])), 4)}
                 for c in cases}}
json.dump(key, open(os.path.join(ROOT, "关键结果摘要.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps(key, ensure_ascii=False, indent=1))
