# -*- coding: utf-8 -*-
"""报告图 R1~R9（彩色 PNG 200 dpi）与专利附图 图16~18（黑白，PNG 400 dpi + SVG，宋体/黑体）。"""
import json, os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
import params as PR

for f in (r"C:\Windows\Fonts\simsun.ttc", r"C:\Windows\Fonts\simhei.ttf"):
    if os.path.exists(f):
        fm.fontManager.addfont(f)
plt.rcParams["font.sans-serif"] = ["SimHei"]
plt.rcParams["font.serif"] = ["SimSun"]
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["svg.fonttype"] = "none"

P = PR.load()
J = lambda n: json.load(open(os.path.join(PR.DATA, n + ".json"), encoding="utf-8"))
sc, st, en, va, ch = J("scen"), J("stiff"), J("energy"), J("validate"), J("chuck")
sens = J("sens") if os.path.exists(os.path.join(PR.DATA, "sens.json")) else None
mc = J("mc") if os.path.exists(os.path.join(PR.DATA, "mc.json")) else None
LB = {"M1s": "方案2 单腔锁闭+蓄能器", "M1b": "方案3 恒压减压供油", "M2": "方案4 本发明", "M2S": "消融：单腔锁闭+带控",
      "M0": "方案1 原系统", "M2h": "本发明(锁闭腔含软管)"}
C6 = "C6 综合(伸长57.5um+油温+0.1K/min+内泄漏×1)"


def save_r(fig, name):
    fig.tight_layout(); fig.savefig(os.path.join(PR.FIG_R, name), dpi=200); plt.close(fig)


# ------------------------------------------------ 报告图
def r_figs():
    for i, cn in enumerate(["C1 工件伸长57.5um(τ5min)", "C3 油温升+0.2K/min", "C4 油温降-0.2K/min", C6, "C7 长时保压1h(油温日变化-5K/h)"], 1):
        fig, ax = plt.subplots(2, 1, figsize=(8, 6), sharex=True)
        for s, o in sc["时程"][cn].items():
            t = np.array(o["t"]) / 60
            ax[0].plot(t, np.array(o["F_N"]) / 1e3, label=LB[s])
            if s in ("M2", "M1s"):
                ax[1].plot(t, o["p1_MPa"], label=LB[s] + " p1"); ax[1].plot(t, o["p2_MPa"], "--", label=LB[s] + " p2")
        for k in (0.95, 1.05, 1.25):
            ax[0].axhline(k * P["F0"] / 1e3, color="gray", lw=0.6, ls=":")
        ax[0].set_ylabel("顶尖推力 kN"); ax[0].legend(fontsize=8); ax[0].set_title(cn)
        ax[1].set_ylabel("腔压 MPa"); ax[1].set_xlabel("时间 min"); ax[1].legend(fontsize=7, ncol=2)
        save_r(fig, f"R{i}_工况_{cn.split()[0]}.png")
    # R6 刚度
    fig, ax = plt.subplots(1, 2, figsize=(10, 4))
    for s in ("M2", "M2h", "M2S", "M1s"):
        ax[0].plot(st["伸出量mm"], st["静刚度N_um"][s], label=LB[s])
    ax[0].set_xlabel("伸出量 mm"); ax[0].set_ylabel("顶尖静刚度 N/μm"); ax[0].legend(fontsize=8)
    for s in ("M2", "M2S", "M1s", "M1b"):
        ax[1].loglog(st["频率Hz"], st["动柔度um_N"][s], label=LB[s])
    ax[1].set_xlabel("频率 Hz"); ax[1].set_ylabel("动柔度 μm/N"); ax[1].legend(fontsize=8)
    save_r(fig, "R6_刚度.png")
    # R7 阶跃
    fig, ax = plt.subplots(figsize=(7, 4))
    for s in ("M2", "M2S", "M1s"):
        d = sc["切削力阶跃"][s]["1000"]; ax.plot(np.array(d["t"]) * 1e3, d["u"], label=LB[s])
    ax.set_xlabel("时间 ms"); ax.set_ylabel("顶尖位移 μm"); ax.set_title("1 kN 切削力阶跃（方案3 终值 %.0f μm 未画出）" % sc["切削力阶跃"]["M1b"]["1000"]["终值um"]); ax.legend()
    save_r(fig, "R7_切削力阶跃.png")
    # R8 能耗
    fig, ax = plt.subplots(figsize=(7, 4))
    ks = ["M0", "M1s", "M1b", "M2"]
    v = [en["单件循环"][k]["单件电能kWh"] * 1e3 for k in ks]
    ax.bar([LB[k] for k in ks], v, color=["#888", "#c66", "#69c", "#393"])
    for i, x in enumerate(v):
        ax.text(i, x, "%.1f" % x, ha="center", va="bottom")
    ax.set_ylabel("单件循环电能 Wh"); ax.set_yscale("log"); plt.xticks(fontsize=8)
    save_r(fig, "R8_能耗.png")
    # R9 卡盘
    fig, ax = plt.subplots(figsize=(7, 3.5))
    ax.plot(np.array(ch["时程"]["t"]) / 60, ch["时程"]["p_MPa"]); ax.set_xlabel("时间 min"); ax.set_ylabel("卡盘夹紧腔压力 MPa")
    ax.set_title("卡盘锁闭、回转接头卸压，60 s 复压，油温 −0.2 K/min")
    save_r(fig, "R9_卡盘复压.png")
    # R10 复位动态
    d = va["复位过程_动态对准静态"]
    fig, ax = plt.subplots(figsize=(7, 3.5))
    ax.plot(d["t"], np.array(d["Fh"]) / 1e3, label="液压推力 p1A1−p2A2"); ax.plot(d["t"], np.array(d["Fw"]) / 1e3, "--", label="顶尖推力")
    ax.set_xlabel("时间 s"); ax.set_ylabel("kN"); ax.legend(); ax.set_title("方案甲复位过程（V1、V4 开 0.30 s）")
    save_r(fig, "R10_复位动态.png")
    if sens:
        rows = sens["单因素"]
        fig, ax = plt.subplots(figsize=(9, 4.5))
        lab = [f'{r["参数"]}={r["值"]:g}' for r in rows]
        for s, m in (("M1s", "o"), ("M1b", "s"), ("M2", "^")):
            ax.plot(range(len(rows)), [r[s].get("最大偏差%", np.nan) for r in rows], m, label=LB[s])
        ax.set_xticks(range(len(rows))); ax.set_xticklabels(lab, rotation=75, fontsize=7)
        ax.set_ylabel("C6 工况最大推力偏差 %"); ax.legend()
        save_r(fig, "R11_敏感性.png")
    if mc:
        fig, ax = plt.subplots(figsize=(7, 4))
        for s in ("M1s", "M1b", "M2", "M2b"):
            dv = [max(r[s]["正偏差%"], -r[s]["负偏差%"]) for r in mc["样本"] if "错误" not in r[s]]
            ax.hist(dv, bins=60, histtype="step", label=LB.get(s, "本发明方案乙"), density=True)
        ax.set_xlabel("最大推力偏差 %"); ax.set_ylabel("概率密度"); ax.legend()
        save_r(fig, "R12_蒙特卡洛.png")


# ------------------------------------------------ 专利附图（黑白）
BW = dict(color="black")
STY = {"M1s": dict(ls="--", lw=1.0), "M1b": dict(ls=":", lw=1.2), "M2": dict(ls="-", lw=1.5), "M2S": dict(ls="-.", lw=1.0),
       "M0": dict(ls=(0, (5, 2, 1, 2, 1, 2)), lw=1.0), "M2h": dict(ls="-.", lw=1.0)}


def pfig():
    fig, ax = plt.subplots(figsize=(6.3, 4.2))
    for a in fig.axes:
        a.tick_params(labelsize=9)
    return fig, ax


def save_p(fig, ax, name, meta):
    for t in ax.get_xticklabels() + ax.get_yticklabels():
        t.set_fontfamily("SimSun")
    ax.xaxis.label.set_fontfamily("SimHei"); ax.yaxis.label.set_fontfamily("SimHei")
    leg = ax.get_legend()
    if leg:
        for t in leg.get_texts():
            t.set_fontfamily("SimSun")
    fig.tight_layout()
    b = os.path.join(PR.FIG_P, name)
    fig.savefig(b + ".png", dpi=400); fig.savefig(b + ".svg"); plt.close(fig)
    json.dump(meta, open(b + ".json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def p_figs():
    # 图16 综合工况推力时程
    fig, ax = pfig()
    for s in ("M1s", "M1b", "M2"):
        o = sc["时程"][C6][s]
        ax.plot(np.array(o["t"]) / 60, np.array(o["F_N"]) / 1e3, label={"M1s": "曲线1", "M1b": "曲线2", "M2": "曲线3"}[s], **BW, **STY[s])
    for k in (0.95, 1.05):
        ax.axhline(k * P["F0"] / 1e3, color="black", lw=0.5, ls=(0, (1, 3)))
    ax.set_xlabel("时间 t / min"); ax.set_ylabel("尾座顶紧力 F / kN"); ax.legend(frameon=False, fontsize=9)
    ax.set_xlim(0, 10)
    save_p(fig, ax, "图16", {"图号": 16, "图意": "额定工况（F0=6 kN，伸出 70 mm）工件热伸长 57.5 μm 与锁闭腔油温 +0.1 K/min 同时作用时顶紧力随时间变化",
                             "曲线1": "单腔锁闭+蓄能器", "曲线2": "恒压减压供油", "曲线3": "本发明", "细点线": "推力带 0.95F0、1.05F0",
                             "数据": "数据/scen.json 时程/" + C6})
    # 图17 静刚度 vs 伸出量
    fig, ax = pfig()
    for s, nm in (("M1s", "曲线1"), ("M2S", "曲线2"), ("M2", "曲线3")):
        ax.plot(st["伸出量mm"], st["静刚度N_um"][s], label=nm, **BW, **STY[s])
    ax.axhline(0, color="black", lw=0.5)
    ax.set_xlabel("尾座液压缸伸出量 x / mm"); ax.set_ylabel("顶尖轴向静刚度 K / (N/μm)"); ax.legend(frameon=False, fontsize=9)
    save_p(fig, ax, "图17", {"图号": 17, "图意": "顶尖轴向静刚度随尾座液压缸伸出量变化（含机械刚度 100 N/μm 串联）",
                             "曲线1": "单腔锁闭（软管连接）", "曲线2": "单腔锁闭（阀块直装）", "曲线3": "本发明双腔预压锁闭（阀块直装）",
                             "说明": "恒压减压供油低频刚度趋于 0，未画出", "数据": "数据/stiff.json"})
    # 图18 单件循环累计电能
    fig, ax = pfig()
    c = P["cycle"]; T = sum(c.values()); t = np.linspace(0, T, 3000)
    t_move = [(0, c["夹紧"] + c["尾座前进"]), (T - c["装卸"] - c["松开"] - c["尾座后退"], T - c["装卸"])]
    for s, nm in (("M0", "曲线1"), ("M1s", "曲线2"), ("M2", "曲线3")):
        Ecyc = en["单件循环"][s]["单件电能kWh"] * 1e3
        if s == "M0":
            e = Ecyc * t / T
        else:
            mv = np.zeros_like(t)
            for a, b in t_move:
                mv += np.clip(t - a, 0, b - a)
            tm = sum(b - a for a, b in t_move)
            Eh = en["保压630s"][s]["电能kJ"] / 3.6
            e = (Ecyc - Eh) * mv / tm + Eh * (t - mv) / (T - tm)
        ax.plot(t / 60, e, label=nm, **BW, **STY[s])
    ax.set_yscale("log"); ax.set_ylim(0.5, 400)
    ax.set_xlabel("时间 t / min"); ax.set_ylabel("累计电能 E / Wh"); ax.legend(frameon=False, fontsize=9)
    save_p(fig, ax, "图18", {"图号": 18, "图意": "一个单件循环（656 s）内液压系统累计耗电（对数坐标）",
                             "曲线1": "原定量泵溢流保压", "曲线2": "单腔锁闭+蓄能器（恒压减压供油同值）", "曲线3": "本发明",
                             "说明": "保压段按平均功率绘制，实际为间歇充液台阶", "数据": "数据/energy.json"})


if __name__ == "__main__":
    r_figs(); p_figs(); print("figs ok")
