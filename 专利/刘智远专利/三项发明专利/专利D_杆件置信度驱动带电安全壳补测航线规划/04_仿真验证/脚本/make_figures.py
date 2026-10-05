# -*- coding: utf-8 -*-
"""由 ../数据/results.json 与 plot_combined.pkl 绘图：04 彩色结果图 + 06 附图（黑白线稿、无标注版）。"""
import json
import os
import pickle

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from mpl_toolkits.mplot3d.art3d import Line3DCollection  # noqa: E402

plt.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False
HERE = os.path.dirname(os.path.abspath(__file__))
PD = os.path.abspath(os.path.join(HERE, "..", ".."))
DATA = os.path.join(PD, "04_仿真验证", "数据")
FIG = os.path.join(PD, "04_仿真验证", "图")
FIG6 = os.path.join(PD, "06_附图", "无标注版")
os.makedirs(FIG, exist_ok=True); os.makedirs(FIG6, exist_ok=True)
R = json.load(open(os.path.join(DATA, "results.json"), encoding="utf-8"))
D = pickle.load(open(os.path.join(DATA, "plot_combined.pkl"), "rb"))
VAR = ["standard", "highlow", "missing", "occluded", "combined"]
VLAB = ["标准", "高低腿", "缺材", "遮挡", "组合"]
METH = ["none", "uniform", "geo_nbv", "proposed"]
MLAB = ["无补测", "均匀加密环绕", "纯几何NBV", "本发明"]
HATCH = ["", "///", "...", "xxx"]


def truss(ax, lw=0.5, color="k", alpha=1.0, mask=None):
    X, mi, mj = D["prior_nodes"], D["mi"], D["mj"]
    m = np.ones(len(mi), bool) if mask is None else mask
    seg = np.stack([X[mi[m]], X[mj[m]]], 1)
    ax.add_collection3d(Line3DCollection(seg, colors=color, linewidths=lw, alpha=alpha))


def capsule_wire(ax, a, b, r, n=16, color="k", lw=0.4, ls="-"):
    a, b = np.asarray(a, float), np.asarray(b, float)
    u = (b - a) / np.linalg.norm(b - a)
    e1 = np.cross(u, [0, 0, 1.0]) if abs(u[2]) < 0.9 else np.cross(u, [1.0, 0, 0])
    e1 /= np.linalg.norm(e1); e2 = np.cross(u, e1)
    th = np.linspace(0, 2 * np.pi, n + 1)
    for s in np.linspace(0, 1, 7):
        c = a + s * (b - a)
        ring = c + r * (np.outer(np.cos(th), e1) + np.outer(np.sin(th), e2))
        ax.plot(*ring.T, color=color, lw=lw, ls=ls)
    for k in range(0, n, 4):
        off = r * (np.cos(th[k]) * e1 + np.sin(th[k]) * e2)
        ax.plot(*np.stack([a + off, b + off]).T, color=color, lw=lw, ls=ls)


def setup3d(ax, lim=((-26, 26), (-26, 26), (0, 80)), elev=18, azim=-58):
    ax.set_xlim(*lim[0]); ax.set_ylim(*lim[1]); ax.set_zlim(*lim[2])
    ax.set_box_aspect((lim[0][1] - lim[0][0], lim[1][1] - lim[1][0], lim[2][1] - lim[2][0]))
    ax.view_init(elev=elev, azim=azim); ax.set_axis_off()


# ---------------------------------------------------------------- 图5 安全壳与候选视点（黑白）
def fig5():
    fig = plt.figure(figsize=(8, 9), dpi=200)
    ax = fig.add_subplot(111, projection="3d")
    truss(ax, 0.45)
    r = D["radius"]
    for a, b, k in D["live"]:
        a = np.asarray(a); b = np.asarray(b)
        if k == "conductor":
            a2 = a + (b - a) * 0.40; b2 = a + (b - a) * 0.60      # 截取塔附近 ±24 m 段
            ax.plot(*np.stack([a2, b2]).T, color="k", lw=1.4)
            capsule_wire(ax, a2, b2, r, lw=0.35, ls="--")
        else:
            ax.plot(*np.stack([a, b]).T, color="k", lw=1.2)
    C = D["cand"]; Rj = D["rejected"]
    sel = (np.abs(C[:, 1]) < 26) & (np.abs(C[:, 0]) < 26)
    ax.scatter(*C[sel].T, s=3, c="k", marker="o", depthshade=False, linewidths=0)
    sel = (np.abs(Rj[:, 1]) < 26) & (np.abs(Rj[:, 0]) < 26)
    ax.scatter(*Rj[sel].T, s=6, c="k", marker="x", linewidths=0.3, depthshade=False)
    setup3d(ax)
    fig.savefig(os.path.join(FIG6, "图5_安全壳与候选视点.png"), bbox_inches="tight", facecolor="white")
    plt.close(fig)


# ---------------------------------------------------------------- 图6 补测航线（黑白）
def fig6():
    fig = plt.figure(figsize=(8, 9), dpi=200)
    ax = fig.add_subplot(111, projection="3d")
    low = D["c_init"] < 0.5
    truss(ax, 0.35, mask=~low)
    truss(ax, 1.6, mask=low)                       # 初始低置信杆件加粗
    for a, b, k in D["live"]:
        a = np.asarray(a); b = np.asarray(b)
        if k == "conductor":
            a2 = a + (b - a) * 0.40; b2 = a + (b - a) * 0.60
            ax.plot(*np.stack([a2, b2]).T, color="k", lw=1.2)
            capsule_wire(ax, a2, b2, D["radius"], n=12, lw=0.25, ls=":")
    ip = D["init_path"]
    ip = ip[np.abs(ip[:, 1]) < 26]
    ax.plot(*ip.T, color="k", lw=0.8, ls="--")
    P = D["path_prop"]
    ax.plot(*P.T, color="k", lw=1.1)
    V = D["views_prop"]
    ax.scatter(*V.T, s=22, facecolors="white", edgecolors="k", linewidths=0.8, depthshade=False)
    for i, v in enumerate(V):
        ax.text(v[0], v[1], v[2] + 1.2, str(i + 1), fontsize=6)
    h = D["home"]; ax.scatter(*h, s=30, marker="^", c="k", depthshade=False)
    setup3d(ax)
    fig.savefig(os.path.join(FIG6, "图6_补测航线.png"), bbox_inches="tight", facecolor="white")
    plt.close(fig)


# ---------------------------------------------------------------- 图9 仿真结果（黑白，无标注版：保留坐标轴数字与图例）
def bars(ax, key, f=lambda x: x, ylabel=""):
    x = np.arange(len(VAR)); wdt = 0.2
    for k, m in enumerate(METH):
        y = [f(R[v][m][key]) for v in VAR]
        ax.bar(x + (k - 1.5) * wdt, y, wdt, color="white", edgecolor="k", hatch=HATCH[k], lw=0.6, label=MLAB[k])
    ax.set_xticks(x); ax.set_xticklabels(VLAB); ax.set_ylabel(ylabel)


def fig9(bw=True, path=None):
    fig, axs = plt.subplots(2, 3, figsize=(13, 7.5), dpi=200)
    bars(axs[0, 0], "coverage", lambda x: 100 * x, "杆件覆盖率 /%"); axs[0, 0].set_ylim(80, 101)
    bars(axs[0, 1], "n_low", ylabel="低置信杆件数")
    bars(axs[0, 2], "path_m", ylabel="补测航程 /m")
    bars(axs[1, 0], "tip_err_pct", ylabel="FE 塔顶位移误差 /%")
    bars(axs[1, 1], "f_err_pct", lambda x: max(x), "FE 前三阶频率最大误差 /%")
    # 停止判据：组合塔 固定4轮 的缺口曲线 + 自适应停止点
    ax = axs[1, 2]
    for v, ls in (("combined", "-"), ("standard", "--")):
        h = R[v]["history_fixed4"]
        ax.plot([q["t"] for q in h], [q["deficit"] for q in h], color="k", ls=ls, marker="o", ms=3, lw=0.9,
                label=f"{VLAB[VAR.index(v)]}塔（固定4轮）")
        hp = R[v]["history_proposed"][-1]
        ax.scatter([hp["t"]], [hp["deficit"]], s=60, marker="*", facecolors="white", edgecolors="k", zorder=5)
    ax.axhline(0.05, color="k", lw=0.6, ls=":")
    ax.set_xlabel("补测时间 /s"); ax.set_ylabel("加权置信缺口"); ax.legend(fontsize=7, frameon=False)
    axs[0, 0].legend(fontsize=7, ncol=2, frameon=False, loc="lower right")
    for a in axs.ravel():
        a.tick_params(labelsize=8)
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight", facecolor="white")
    plt.close(fig)


# ---------------------------------------------------------------- 04 补充：置信度三维图（彩色）
def fig_conf():
    fig = plt.figure(figsize=(12, 6), dpi=160)
    X, mi, mj = D["prior_nodes"], D["mi"], D["mj"]
    for k, (key, t) in enumerate((("w", "结构重要性权重 w"), ("c_init", "初始航线后置信度"), ("c_prop", "本发明补测后置信度"))):
        ax = fig.add_subplot(1, 3, k + 1, projection="3d")
        val = D[key] / (D[key].max() if key == "w" else 1)
        cm = plt.get_cmap("viridis" if key == "w" else "RdYlGn")
        seg = np.stack([X[mi], X[mj]], 1)
        ax.add_collection3d(Line3DCollection(seg, colors=cm(val), linewidths=1.0))
        setup3d(ax, ((-12, 12), (-12, 12), (0, 62)), elev=10)
        ax.set_title(t, fontsize=10)
    fig.savefig(os.path.join(FIG, "杆件权重与置信度.png"), bbox_inches="tight"); plt.close(fig)


fig5(); fig6()
fig9(path=os.path.join(FIG6, "图9_仿真结果.png"))
fig9(path=os.path.join(FIG, "仿真结果对比.png"))
fig_conf()
print("ok")
