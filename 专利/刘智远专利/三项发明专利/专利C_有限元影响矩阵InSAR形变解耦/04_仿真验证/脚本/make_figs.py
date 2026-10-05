# -*- coding: utf-8 -*-
"""由 ../数据/结果.json、时序示例.json 生成图（SimHei）与 关键结果摘要.json；黑白版另存 06_附图/无标注版/图9_仿真结果.png。"""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

plt.rcParams["font.sans-serif"] = ["SimHei"]
plt.rcParams["axes.unicode_minus"] = False
HERE = Path(__file__).resolve().parent
ROOTC = HERE.parents[1]
D = HERE.parent / "数据"; F = HERE.parent / "图"; F.mkdir(exist_ok=True)
R = json.loads((D / "结果.json").read_text(encoding="utf-8"))
TS = json.loads((D / "时序示例.json").read_text(encoding="utf-8"))
NAMES = {"proposed": "本发明影响矩阵联合反演", "rigid": "刚体倾斜模型", "empirical": "经验热胀阈值+单点"}
MS = {"proposed": ("k", "-", "o"), "rigid": ("0.35", "--", "s"), "empirical": ("0.6", ":", "^")}


def fig(bw: bool):
    fg, ax = plt.subplots(2, 2, figsize=(11, 8))
    t = np.array(TS["t"]); tr = np.array(TS["true"])
    a = ax[0, 0]
    L = int(np.argmin(tr[-1]))
    a.plot(t, tr[:, L], color="k", lw=2.2, label="真值")
    for m in NAMES:
        c, ls, mk = MS[m]
        a.plot(t, np.array(TS[m])[:, L], color=c if bw else None, ls=ls, marker=mk, ms=3, lw=1, label=NAMES[m])
    s = np.array(TS["proposed_std"])[:, L]
    a.fill_between(t, np.array(TS["proposed"])[:, L] - 2 * s, np.array(TS["proposed"])[:, L] + 2 * s,
                   color="0.85", label="本发明 ±2σ")
    a.set_xlabel("日序 / d"); a.set_ylabel(f"腿{L + 1} 竖向位移 / mm"); a.set_title("(a) 沉降腿时序反演"); a.legend(fontsize=8)
    a = ax[0, 1]
    keys = [("rmse", "沉降RMSE/mm"), ("tilt_err", "基础倾斜误差/‰×10")]
    x = np.arange(3); w = 0.35
    for k, (key, lab) in enumerate(keys):
        v = [R["main"][m][key]["mean"] * (10 if key == "tilt_err" else 1) for m in NAMES]
        e = [R["main"][m][key]["ci95"] * (10 if key == "tilt_err" else 1) for m in NAMES]
        a.bar(x + (k - 0.5) * w, v, w, yerr=e, capsize=3, color=["0.25", "0.7"][k], edgecolor="k",
              hatch=["", "//"][k], label=lab)
    a.set_xticks(x); a.set_xticklabels(["本发明", "刚体", "经验阈值"]); a.legend(fontsize=8)
    a.set_title(f"(b) {R['main']['n_mc']} 次蒙特卡洛（误差棒 95%CI）")
    for p, key, title, xl in ((ax[1, 0], "sens_nps_noCR", "(c) 自然PS数（无CR）敏感性", "每轨自然PS数"),
                              (ax[1, 1], "sens_noise", "(d) 噪声倍率敏感性", "噪声倍率")):
        tab = R[key]
        for m in NAMES:
            c, ls, mk = MS[m]
            p.plot([r["value"] for r in tab], [r[m] for r in tab], color=c if bw else None, ls=ls, marker=mk, label=NAMES[m])
        p.set_xlabel(xl); p.set_ylabel("沉降RMSE / mm"); p.set_title(title); p.set_yscale("log"); p.legend(fontsize=8)
        p.grid(alpha=0.3)
    fg.tight_layout()
    return fg


fig(False).savefig(F / "仿真结果_四联图.png", dpi=200)
f9 = ROOTC / "06_附图" / "无标注版" / "图9_仿真结果.png"
fig(True).savefig(f9, dpi=300)
fig(True).savefig(F / "仿真结果_黑白.png", dpi=200)

# 消融图
ab = R["ablation"]
fg, a = plt.subplots(figsize=(7, 3.5))
a.bar(list(ab), [v["rmse"] for v in ab.values()], color="0.5", edgecolor="k")
a.set_ylabel("沉降RMSE / mm"); a.set_title("消融实验（8 次蒙特卡洛均值）")
fg.tight_layout(); fg.savefig(F / "消融.png", dpi=200)

m = R["main"]
summ = {
    "合成塔": R["tower"], "景数_FC1式升降轨": R["epochs"],
    "各腿沉降RMSE_mm": {NAMES[k]: round(m[k]["rmse"]["mean"], 3) for k in NAMES},
    "基础倾斜误差_permille": {NAMES[k]: round(m[k]["tilt_err"]["mean"], 4) for k in NAMES},
    "塔顶倾斜误差_permille": {NAMES[k]: round(m[k]["top_tilt_err"]["mean"], 4) for k in NAMES},
    "热分量解释率": {NAMES[k]: round(m[k]["thermal_expl"]["mean"], 3) for k in NAMES},
    "差异沉降检测率": {NAMES[k]: m[k]["detect_rate"] for k in NAMES},
    "差异沉降虚警率": {NAMES[k]: m[k]["false_alarm"] for k in NAMES},
    "检测阈值_mm": m["diff_thr_mm"], "蒙特卡洛次数": m["n_mc"],
    "本发明95%区间覆盖率": round(m["proposed"]["cover95"]["mean"], 3),
    "热胀视线向最大幅值_mm": round(m["thermal_LOS_amp_mm"], 2),
    "Sentinel1晨昏几何_RMSE_mm": {NAMES[k]: round(R["S1"][k]["rmse"], 3) for k in NAMES},
    "消融_RMSE_mm": {k: round(v["rmse"], 3) for k, v in ab.items()},
    "D最优4只CR后验标准差降幅": round(R["dopt"]["reduction"], 3),
    "运行时间_s": round(R["runtime_s"], 1),
}
(HERE.parent / "关键结果摘要.json").write_text(json.dumps(summ, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps(summ, ensure_ascii=False, indent=1))
