# -*- coding: utf-8 -*-
"""专利A 申请附图（黑白线条，附图标记引线），统一输出为 06_附图/{标注版,无标注版}/图N.png 与 标注版/图N.json。

图1 方法流程图；图2 角钢面元高斯条带生成示意图；图3 激光足迹与无回波负证据示意图；图4 逐杆件离散假设检验示意图；
图5 系统框图；图6 载荷整体轴测图；图7 载荷爆炸图；图8 倾角调节机构剖视图；图9 载荷三视图；图10 同步电路框图；
图11 同步时序图；图12 相机视场与激光扫描面关系示意图；图13 仿真重建精度对比；图14 消融对比；图15 置信度校准与多期复测。
几何图依赖 05_硬件设计/模型/_proj.json（由 FreeCAD 模型投影导出）；图13–15 依赖 04_仿真验证/数据/。
用法（项目根目录）：.venv\\Scripts\\python.exe <本脚本> [--only 13,14,15]
"""
import argparse
import json
import math
import os
import pickle
import sys

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Ellipse, PathPatch, Polygon, Rectangle  # noqa: E402
from matplotlib.path import Path  # noqa: E402

plt.rcParams["font.sans-serif"] = ["SimSun", "SimHei", "Microsoft YaHei"]
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["font.size"] = 10
HERE = os.path.dirname(os.path.abspath(__file__))
PA = os.path.normpath(os.path.join(HERE, ".."))
FIG = os.path.join(PA, "06_附图")
D_LB, D_NO = os.path.join(FIG, "标注版"), os.path.join(FIG, "无标注版")
for d in (D_LB, D_NO):
    os.makedirs(d, exist_ok=True)
DATA = os.path.join(PA, "04_仿真验证", "数据")
PJ = json.load(open(os.path.join(PA, "05_硬件设计", "模型", "_proj.json"), encoding="utf-8"))
LW = 0.7
TITLES = {}
LABELS = {}


def save(fig, n, labeled, title, labels=()):
    d = D_LB if labeled else D_NO
    fig.savefig(os.path.join(d, f"图{n}.png"), dpi=300, facecolor="white", bbox_inches="tight")
    plt.close(fig)
    if labeled:
        TITLES[n] = title
        LABELS[n] = [str(k) for k in labels]
        json.dump({"title": title, "labels": LABELS[n]}, open(os.path.join(D_LB, f"图{n}.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)


def draw_lines(ax, lines, lw=LW):
    for ln in lines:
        a = np.array(ln)
        ax.plot(a[:, 0], a[:, 1], "k-", lw=lw, solid_capstyle="round")


def leaders(ax, labels, keys, extent, rpad=1.18):
    xs = [p[0] for ln in extent for p in ln]
    ys = [p[1] for ln in extent for p in ln]
    cx, cy = (max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2
    rx, ry = (max(xs) - min(xs)) / 2 * rpad, (max(ys) - min(ys)) / 2 * rpad
    items = [(k, labels[k]) for k in keys if k in labels]
    items.sort(key=lambda kv: math.atan2(kv[1][1] - cy, kv[1][0] - cx))
    n = max(len(items), 1)
    used = []
    for k, (x, y) in items:
        a = math.atan2(y - cy, x - cx)
        for u in used:
            if abs((a - u + math.pi) % (2 * math.pi) - math.pi) < 2 * math.pi / (1.7 * n):
                a = u + 2 * math.pi / (1.7 * n)
        used.append(a)
        tx, ty = cx + rx * math.cos(a), cy + ry * math.sin(a)
        ax.plot([x, tx], [y, ty], "k-", lw=0.5)
        ax.plot([x], [y], "k.", ms=2.5)
        ax.text(tx + 6 * math.cos(a), ty + 6 * math.sin(a), k, fontsize=10,
                ha="left" if math.cos(a) > 0.2 else ("right" if math.cos(a) < -0.2 else "center"),
                va="bottom" if math.sin(a) > 0.2 else ("top" if math.sin(a) < -0.2 else "center"))


def blk(ax, x, y, w, h, txt, no=None, labeled=True, fs=9, dash=False):
    ax.add_patch(Rectangle((x, y), w, h, fill=False, lw=1.0, ls="--" if dash else "-"))
    ax.text(x + w / 2, y + h / 2, txt, ha="center", va="center", fontsize=fs)
    if no and labeled:
        ax.plot([x + w, x + w + 0.25], [y + h, y + h + 0.25], "k-", lw=0.5)
        ax.text(x + w + 0.28, y + h + 0.28, str(no), fontsize=9)


def arr(ax, p, q, txt="", both=False, fs=7.5, off=(0, 0.12)):
    ax.annotate("", xy=q, xytext=p, arrowprops=dict(arrowstyle="<|-|>" if both else "-|>", lw=0.8, color="k",
                                                    shrinkA=0, shrinkB=0, mutation_scale=9))
    if txt:
        ax.text((p[0] + q[0]) / 2 + off[0], (p[1] + q[1]) / 2 + off[1], txt, fontsize=fs, ha="center", va="bottom")


# ====================================================================== 图1 方法流程图
STEPS = ["S1 同步采集：秒脉冲硬触发两台相机曝光并记录曝光中点；激光测距记录保留未产生回波的射线",
         "S2 获取初始桁架图：节点、杆件连接、初始截面参数与存在概率",
         "S3 确定性生成函数：每根杆件展开为角钢两肢平面内相互正交的两组面元高斯条带",
         "S4 同一高斯场双模态渲染：影像颜色与轮廓（含漫反射明暗）；激光期望距离与命中概率（含光束足迹）",
         "S5 联合目标函数（光度+轮廓+激光距离+无回波负证据+桁架图先验），梯度经生成函数雅可比回传至桁架参数",
         "S6 逐杆件离散假设检验：肢朝向 0°/90°/180°/270° × 准距偏心 × 存在/不存在，按目标函数降低量与裕度判定",
         "S7 按存在概率剪除或恢复杆件，零能模态检查后更新拓扑",
         "S8 截面参数离散吸附至角钢规格表，固定规格后微调",
         "S9 拉普拉斯近似：节点协方差、截面标准差与杆件置信度（按标定膨胀系数校准）",
         "S10 输出带角钢规格、偏心连接与置信度属性的梁单元有限元模型"]


def fig1(labeled):
    fig, ax = plt.subplots(figsize=(9, 13))
    ax.set_xlim(0, 18); ax.set_ylim(0, 25.5); ax.axis("off")
    ys = [24.2 - i * 2.4 for i in range(len(STEPS))]
    for i, t in enumerate(STEPS):
        y = ys[i]
        ax.add_patch(Rectangle((1.5, y - 0.8), 15, 1.6, fill=False, lw=1))
        lab, body = t.split(" ", 1)
        if len(body) > 30:
            cut = body.find("：") + 1 if 0 < body.find("：") < 22 else 26
            body = body[:cut] + "\n" + body[cut:]
        ax.text(9, y, (lab + " " + body) if labeled else body, ha="center", va="center", fontsize=8.6)
        if i:
            arr(ax, (9, ys[i - 1] - 0.8), (9, y + 0.8))
    # S4–S7 分阶段迭代回路
    ax.plot([16.5, 17.4, 17.4, 16.5], [ys[6], ys[6], ys[3], ys[3]], "k-", lw=0.8)
    arr(ax, (17.4, ys[3]), (16.5, ys[3]))
    ax.text(17.6, (ys[3] + ys[6]) / 2, "分阶段迭代", fontsize=8, rotation=90, va="center")
    save(fig, 1, labeled, "方法流程图")


# ====================================================================== 图2 角钢面元高斯条带生成示意
def fig2(labeled):
    fig = plt.figure(figsize=(12, 5))
    ax = fig.add_subplot(121); ax.set_aspect("equal"); ax.axis("off")
    b, t = 1.0, 0.12
    ax.add_patch(Polygon([[0, 0], [b, 0], [b, t], [t, t], [t, b], [0, b]], fill=False, lw=1.2))
    ax.annotate("", xy=(b, -0.15), xytext=(0, -0.15), arrowprops=dict(arrowstyle="<->", lw=.6))
    ax.text(b / 2, -0.3, "b", ha="center", fontsize=11, style="italic")
    ax.annotate("", xy=(b + 0.12, t), xytext=(b + 0.12, 0), arrowprops=dict(arrowstyle="<->", lw=.6))
    ax.text(b + 0.18, 0.02, "t", fontsize=11, style="italic")
    ax.annotate("", xy=(0.95, 0.0), xytext=(0, 0), arrowprops=dict(arrowstyle="-|>", lw=.8))
    ax.annotate("", xy=(0.0, 0.95), xytext=(0, 0), arrowprops=dict(arrowstyle="-|>", lw=.8))
    ax.text(0.97, 0.06, "n$_1$", fontsize=10); ax.text(0.05, 0.97, "n$_2$", fontsize=10)
    ax.plot([-0.32], [-0.32], "k+", ms=9)
    ax.annotate("", xy=(0.0, 0.0), xytext=(-0.32, -0.32), arrowprops=dict(arrowstyle="-|>", lw=.6))
    ax.text(-0.75, -0.45, "节点连线（工作线）", fontsize=8)
    ax.text(-0.25, -0.1, "δ", fontsize=11, style="italic")
    ax.add_patch(matplotlib.patches.Arc((0, 0), 0.6, 0.6, theta1=0, theta2=35, lw=.6))
    ax.plot([0, 0.45], [0, 0.32], "k-.", lw=.5); ax.text(0.33, 0.12, "θ", fontsize=11, style="italic")
    for k in range(4):
        u = (k + 0.5) / 4 * (b - t) + t
        ax.add_patch(Ellipse((u, t / 2), (b - t) / 4 * 0.95, t * 0.9, fill=False, lw=.6))
        ax.add_patch(Ellipse((t / 2, u), t * 0.9, (b - t) / 4 * 0.95, fill=False, lw=.6))
    ax.set_xlim(-0.85, 1.45); ax.set_ylim(-0.6, 1.15)
    ax.set_title("(a) 截面参数与两肢面元高斯", fontsize=10, y=-0.1)
    ax2 = fig.add_subplot(122, projection="3d"); ax2.set_axis_off()
    na, nb = np.array([0, 0, 0]), np.array([0.3, 0.2, 3.0])
    ax2.plot(*zip(na, nb), "k-.", lw=.8)
    ax2.scatter(*zip(na, nb), c="k", s=15)
    d = (nb - na) / np.linalg.norm(nb - na)
    n1 = np.cross(d, [1, 0, 0]); n1 /= np.linalg.norm(n1); n2 = np.cross(d, n1)
    tt = np.linspace(0, 2 * np.pi, 30)
    for s in np.linspace(0.08, 0.92, 9):
        c = na + s * (nb - na)
        for leg in (n1, n2):
            for j in range(2):
                cc = c + leg * (0.1 + 0.2 * j)
                pts = cc[None] + 0.09 * np.cos(tt)[:, None] * leg + 0.15 * np.sin(tt)[:, None] * d
                ax2.plot(pts[:, 0], pts[:, 1], pts[:, 2], "k-", lw=.4)
    if labeled:
        ax2.text(*(na - [0.15, 0, 0.25]), "节点 i", fontsize=9); ax2.text(*(nb + [0, 0, 0.12]), "节点 j", fontsize=9)
        ax2.text(*(na + 0.5 * (nb - na) + n1 * 0.6), "肢1", fontsize=9)
        ax2.text(*(na + 0.62 * (nb - na) + n2 * 0.6), "肢2", fontsize=9)
    ax2.view_init(18, -60); ax2.set_box_aspect((1, 1, 2.2))
    ax2.set_title("(b) 沿杆件轴向 K 段 × 每肢 P 列", fontsize=10, y=-0.02)
    save(fig, 2, labeled, "角钢面元高斯条带生成示意图")


# ====================================================================== 图3 激光足迹与无回波负证据
def fig3(labeled):
    fig, axs = plt.subplots(1, 2, figsize=(13, 5.4))
    ax = axs[0]; ax.set_aspect("equal"); ax.axis("off")
    ax.plot([0], [0], "ks", ms=6)
    for s in (-1, 1):
        ax.plot([0, 9.0], [0, s * 0.85], "k--", lw=.6)
    ax.plot([0, 7.2], [0, 0], "k-", lw=.8)
    for x in (2.5, 5.0):
        ax.add_patch(Ellipse((x, 0), 0.25, 0.19 * x, fill=False, lw=.7))
    # 角钢截面（光束照射处）及其两肢面元高斯
    ax.add_patch(Polygon([[7.2, -0.25], [7.9, -0.25], [7.9, -0.15], [7.3, -0.15], [7.3, 0.45], [7.2, 0.45]],
                         fill=False, lw=1.2))
    ax.add_patch(Ellipse((7.25, 0.15), 0.12, 0.55, fill=False, lw=.5, ls=":"))
    ax.add_patch(Ellipse((7.55, -0.2), 0.55, 0.12, fill=False, lw=.5, ls=":"))
    ax.add_patch(Ellipse((7.2, 0), 0.22, 1.37, fill=False, lw=.7))
    if labeled:
        ax.text(-0.5, -0.45, "激光器", fontsize=9)
        ax.annotate("足迹（随距离放大）", xy=(5.0, 0.47), xytext=(2.6, 1.25), fontsize=9,
                    arrowprops=dict(arrowstyle="-", lw=.5))
        ax.annotate("角钢两肢面元高斯", xy=(7.55, -0.22), xytext=(7.0, -1.25), fontsize=9,
                    arrowprops=dict(arrowstyle="-", lw=.5))
        ax.annotate("命中能量占比 h", xy=(7.3, 0.3), xytext=(8.2, 0.95), fontsize=9,
                    arrowprops=dict(arrowstyle="-", lw=.5))
    ax.set_xlim(-1, 11); ax.set_ylim(-1.7, 1.7)
    ax.set_title("(a) 各向异性高斯光束与面元高斯的闭式命中能量", fontsize=10, y=-0.1)
    ax = axs[1]; ax.set_aspect("equal"); ax.axis("off")
    ax.add_patch(Polygon([[3, -2], [7, -2], [6.2, 3], [3.8, 3]], fill=False, lw=.8, ls="-."))
    for (x0, y0, x1, y1) in [(3.2, -1.5, 6.6, 0.8), (3.5, 0.8, 6.0, 2.6), (6.8, -1.6, 3.6, 0.5)]:
        ax.plot([x0, x1], [y0, y1], "k-", lw=2.2)
    ax.plot([0, 10], [1.6, 1.25], "k-", lw=.8); ax.plot([10], [1.25], "k>", ms=4)
    for x in (4.2, 5.0, 5.8):
        ax.add_patch(Ellipse((x, 1.6 - 0.035 * x), 0.35, 0.22, fill=False, lw=.5, ls=":"))
    ax.plot([0, 6.3], [-1.0, -0.15], "k-", lw=.8); ax.plot([6.3], [-0.15], "ko", ms=4)
    ax.add_patch(Ellipse((4.4, -0.42), 0.35, 0.22, fill=False, lw=.5, ls=":"))
    if labeled:
        ax.text(0.0, 1.8, "射线①", fontsize=9)
        ax.text(0.0, -0.75, "射线②", fontsize=9)
        ax.text(6.45, -0.4, "回波", fontsize=9)
        ax.text(6.4, 3.05, "塔体包围区域", fontsize=9)
        ax.text(0.0, -2.75, "射线①未产生回波：对沿线面元累加 -log(1-H)", fontsize=9)
        ax.text(0.0, -3.35, "射线②有回波：对深度小于（实测距离-容差）的面元累加 -log(1-H)", fontsize=9)
    ax.set_xlim(-0.3, 10.8); ax.set_ylim(-3.7, 3.5)
    ax.set_title("(b) 无回波负证据项", fontsize=10, y=-0.12)
    save(fig, 3, labeled, "激光足迹与无回波负证据示意图")


# ====================================================================== 图4 逐杆件离散假设检验
def _L(ax, c, ang, b=1.0, t=0.14, ls="-", lw=1.1):
    pts = np.array([[0, 0], [b, 0], [b, t], [t, t], [t, b], [0, b]])
    R = np.array([[math.cos(ang), -math.sin(ang)], [math.sin(ang), math.cos(ang)]])
    p = pts @ R.T + c
    ax.add_patch(Polygon(p, fill=False, lw=lw, ls=ls))


def fig4(labeled):
    fig, axs = plt.subplots(1, 3, figsize=(14, 4.8))
    ax = axs[0]; ax.set_aspect("equal"); ax.axis("off")
    for k, ang in enumerate((0, 90, 180, 270)):
        c = np.array([(k % 2) * 3.0, -(k // 2) * 3.0])
        # 以截面形心为中心旋转（形心在 (0.29b, 0.29b) 附近）
        g = np.array([0.29, 0.29])
        R = np.array([[math.cos(math.radians(ang)), -math.sin(math.radians(ang))],
                      [math.sin(math.radians(ang)), math.cos(math.radians(ang))]])
        _L(ax, c - R @ g, math.radians(ang))
        ax.plot(*c, "k+", ms=8)
        ax.text(c[0] - 0.6, c[1] - 1.05, f"{ang}°", fontsize=10)
    ax.set_xlim(-1.4, 4.4); ax.set_ylim(-4.6, 1.4)
    ax.set_title("(a) 肢朝向假设（绕截面形心）", fontsize=10, y=-0.12)
    ax = axs[1]; ax.set_aspect("equal"); ax.axis("off")
    for k, (dx, dy, nm) in enumerate(((0, 0, "δ=0"), (-0.55, 0, "δ=-g·n$_1$"), (0, -0.55, "δ=-g·n$_2$"),
                                       (-0.29, -0.29, "保持形心"))):
        c = np.array([(k % 2) * 3.0, -(k // 2) * 3.0])
        _L(ax, c + [dx, dy], 0.0)
        ax.plot(*c, "k+", ms=8)
        ax.text(c[0] - 0.4, c[1] - 1.05, nm, fontsize=9)
    ax.set_xlim(-1.4, 4.4); ax.set_ylim(-4.6, 1.4)
    ax.set_title("(b) 准距规则偏心假设（g≈0.55b）", fontsize=10, y=-0.12)
    ax = axs[2]; ax.axis("off"); ax.set_xlim(0, 10); ax.set_ylim(0, 10)
    blk(ax, 1, 8, 8, 1.3, "对每根杆件枚举假设 H$_k$（含现状 H$_0$）", labeled=False, fs=9)
    blk(ax, 1, 5.7, 8, 1.3, "在该杆件包络内的像素与激光射线上\n计算目标函数降低量 ΔE$_k$", labeled=False, fs=8.5)
    blk(ax, 1, 3.4, 8, 1.3, "ΔE$_k$ > 裕度阈值 Δ$_{min}$ ？", labeled=False, fs=9)
    blk(ax, 1, 1.1, 3.6, 1.3, "接受 H$_k$", labeled=False, fs=9)
    blk(ax, 5.4, 1.1, 3.6, 1.3, "保持 H$_0$", labeled=False, fs=9)
    arr(ax, (5, 8), (5, 7)); arr(ax, (5, 5.7), (5, 4.7)); arr(ax, (3, 3.4), (2.8, 2.4)); arr(ax, (7, 3.4), (7.2, 2.4))
    ax.text(2.2, 2.8, "是", fontsize=9); ax.text(7.4, 2.8, "否", fontsize=9)
    ax.set_title("(c) 判定流程", fontsize=10, y=-0.12)
    save(fig, 4, labeled, "逐杆件离散假设检验示意图")


# ====================================================================== 图5 系统框图（不含补测规划）
MODS = [("数据预处理与时空配准模块", 201), ("初始桁架图构建模块", 202), ("角钢高斯条带生成模块", 203),
        ("影像-激光联合可微渲染模块", 204), ("桁架参数优化与拓扑更新模块", 205),
        ("规格吸附与置信度评估模块", 206), ("有限元模型导出模块", 207)]


def fig5(labeled):
    fig, ax = plt.subplots(figsize=(11, 6)); ax.set_xlim(0, 22); ax.set_ylim(0, 12); ax.axis("off")
    ax.add_patch(Rectangle((0.3, 0.6), 9.4, 10.8, fill=False, lw=1.1, ls="--")); ax.text(0.5, 11, "同步采集载荷", fontsize=9)
    if labeled:
        ax.plot([9.7, 10], [11.4, 11.7], "k-", lw=.5); ax.text(10.05, 11.75, "100", fontsize=9)
    blk(ax, 0.8, 8.8, 4, 1.6, "激光扫描头", 3, labeled, fs=8)
    blk(ax, 5.2, 8.8, 4, 1.6, "俯视/仰视相机", 5, labeled, fs=8)
    blk(ax, 0.8, 6.2, 4, 1.6, "组合导航单元", 7, labeled)
    blk(ax, 5.2, 6.2, 4, 1.6, "同步板", 8, labeled)
    blk(ax, 2.6, 3.4, 5, 1.8, "机载计算单元\n（预处理/数据质量检查）", 9, labeled, fs=8)
    blk(ax, 2.6, 1.0, 5, 1.4, "挂架·快拆接口·减振器", 1, labeled, fs=8)
    ax.add_patch(Rectangle((11.5, 0.6), 10.2, 10.8, fill=False, lw=1.1, ls="--")); ax.text(11.7, 11, "重建系统", fontsize=9)
    if labeled:
        ax.plot([21.7, 21.9], [11.4, 11.7], "k-", lw=.5); ax.text(21.5, 11.75, "200", fontsize=9)
    for i, (t, n) in enumerate(MODS):
        blk(ax, 12.5, 9.6 - i * 1.4, 7.6, 1.0, t, n, labeled, fs=8)
        if i:
            arr(ax, (16.3, 9.6 - (i - 1) * 1.4), (16.3, 10.6 - i * 1.4))
    for a, b in [((4.8, 9.6), (5.2, 9.6)), ((2.8, 8.8), (2.8, 7.8)), ((7.2, 8.8), (7.2, 7.8)), ((4.8, 7.0), (5.2, 7.0)),
                 ((5.0, 6.2), (5.0, 5.2))]:
        arr(ax, a, b, both=True)
    arr(ax, (7.6, 4.3), (12.5, 10.1))
    ax.text(10.6, 5.6, "同步观测\n数据", fontsize=7.5, ha="center")
    save(fig, 5, labeled, "系统框图", ["100", "1", "3", "5", "7", "8", "9", "200"] + [str(n) for _, n in MODS])


# ====================================================================== 图6–9 载荷几何图
KEYS_ALL = ["1", "11", "12", "2", "3", "41", "42", "43", "44", "45", "46", "5", "6", "7", "8", "9", "13"]


def geo(n, view, title, keys, figsize=(8, 6), section=False):
    v = PJ[view]
    present = set(v["labels"]) | ({"4"} if section else set())
    keys = [k for k in keys + (["4"] if section else []) if k in present]
    for labeled in (False, True):
        fig, ax = plt.subplots(figsize=figsize); ax.set_aspect("equal"); ax.axis("off")
        if section:
            for f in v["faces"]:
                verts = f["outer"]; codes = [Path.MOVETO] + [Path.LINETO] * (len(verts) - 1)
                for w in f["inner"]:
                    verts = verts + w; codes += [Path.MOVETO] + [Path.LINETO] * (len(w) - 1)
                ax.add_patch(PathPatch(Path(verts, codes), facecolor="white", edgecolor="k", lw=LW,
                                       hatch="////" if f["no"] in (2, 41, 43, 45, 46) else "\\\\\\\\"))
        draw_lines(ax, v["lines"])
        if labeled:
            labs = dict(v["labels"])
            if section:
                labs["4"] = labs.get("43", labs.get("41"))
            leaders(ax, labs, keys, v["lines"])
        save(fig, n, labeled, title, keys)


def fig9_views():
    keys = ["1", "11", "12", "2", "3", "5", "6", "8", "9"]
    for labeled in (False, True):
        fig, axs = plt.subplots(1, 3, figsize=(15, 5))
        for ax, vw, t in zip(axs, ["front", "top", "side"], ["(a) 主视", "(b) 俯视", "(c) 左视"]):
            ax.set_aspect("equal"); ax.axis("off"); draw_lines(ax, PJ[vw]["lines"], 0.5)
            ax.set_title(t, fontsize=10, y=-0.12)
            if labeled:
                leaders(ax, PJ[vw]["labels"], keys, PJ[vw]["lines"])
        save(fig, 9, labeled, "载荷三视图", keys)


# ====================================================================== 图10 同步电路框图
def fig10(labeled):
    fig, ax = plt.subplots(figsize=(11, 6.5)); ax.set_xlim(0, 22); ax.set_ylim(0, 13); ax.axis("off")
    blk(ax, 0.5, 9.5, 3.6, 2, "组合导航单元", 7, labeled)
    ax.add_patch(Rectangle((6, 3), 8, 8.8, fill=False, lw=1.2, ls="--"))
    if labeled:
        ax.plot([14, 14.3], [11.8, 12.2], "k-", lw=.5); ax.text(14.35, 12.25, "8", fontsize=9)
    ax.text(6.2, 11.4, "同步板", fontsize=9)
    blk(ax, 6.6, 8.6, 3.2, 1.8, "秒脉冲整形与\n隔离输入", 81, labeled)
    blk(ax, 10.4, 8.6, 3.2, 1.8, "时间基准计数器", 82, labeled)
    blk(ax, 6.6, 5.9, 3.2, 1.8, "触发脉冲发生", 83, labeled)
    blk(ax, 10.4, 5.9, 3.2, 1.8, "曝光中点\n时间戳锁存", 84, labeled)
    blk(ax, 8.5, 3.4, 3.2, 1.6, "微控制器", 85, labeled)
    blk(ax, 17, 9.8, 4, 1.8, "激光扫描头", 3, labeled)
    blk(ax, 17, 6.9, 4, 1.8, "俯视测绘相机", 5, labeled)
    blk(ax, 17, 4.1, 4, 1.8, "仰视相机", 6, labeled)
    blk(ax, 0.5, 3.4, 3.6, 2, "机载计算单元", 9, labeled)
    arr(ax, (4.1, 10.5), (6.6, 9.6), "PPS")
    arr(ax, (4.1, 11.1), (17, 11.1), "秒脉冲 + 时间报文", off=(0, 0.1))
    arr(ax, (9.8, 9.5), (10.4, 9.5)); arr(ax, (12.0, 8.6), (12.0, 7.7)); arr(ax, (8.2, 8.6), (8.2, 7.7))
    arr(ax, (9.8, 6.9), (17, 7.9), "触发 1", off=(1.5, 0.1))
    arr(ax, (9.8, 6.4), (17, 4.9), "触发 2", off=(1.5, -0.6))
    arr(ax, (17, 7.3), (13.6, 6.9), "曝光有效信号 1", off=(0.3, -0.55))
    arr(ax, (17, 4.6), (13.6, 6.1), "曝光有效信号 2", off=(0.6, -0.6))
    arr(ax, (12, 5.9), (11.2, 5.0)); arr(ax, (8.5, 4.2), (4.1, 4.4), "曝光中点时间戳")
    arr(ax, (4.1, 3.8), (17, 3.0)); ax.text(13, 2.4, "图像数据", fontsize=7.5)
    arr(ax, (19, 9.8), (19, 9.2)); ax.plot([19, 19, 2.3], [9.2, 2.0, 2.0], "k-", lw=.8); arr(ax, (2.3, 2.0), (2.3, 3.4))
    ax.text(10, 1.5, "点云数据", fontsize=7.5)
    arr(ax, (2.3, 9.5), (2.3, 5.4), "位姿原始观测", off=(-0.2, 0))
    save(fig, 10, labeled, "同步电路框图", ["3", "5", "6", "7", "8", "81", "82", "83", "84", "85", "9"])


# ====================================================================== 图11 同步时序图
def fig11(labeled):
    fig, ax = plt.subplots(figsize=(11, 5)); ax.set_xlim(-1.5, 12); ax.set_ylim(-0.5, 7.2); ax.axis("off")
    rows = ["秒脉冲", "触发", "曝光有效", "时间戳", "激光扫描"]
    for i, r in enumerate(rows):
        y = 5.5 - i * 1.25; ax.text(-1.45, y + 0.2, r, fontsize=9)
        if i == 0:
            xs = [0, 0, 0.1, 0.1, 10, 10, 10.1, 10.1, 11.5]; ys = [0, 1, 1, 0, 0, 1, 1, 0, 0]
        elif i == 1:
            xs, ys = [], []
            for k in (0, 2.5, 5, 7.5, 10):
                xs.extend([k + .5, k + .5, k + .6, k + .6]); ys.extend([0, 1, 1, 0])
        elif i == 2:
            xs, ys = [], []
            for k in (0, 2.5, 5, 7.5, 10):
                xs.extend([k + .8, k + .8, k + 1.6, k + 1.6]); ys.extend([0, 1, 1, 0])
        elif i == 3:
            xs, ys = [0, 11.5], [0, 0]
            for k in (0, 2.5, 5, 7.5, 10):
                ax.annotate("", xy=(k + 1.2, y + 0.8), xytext=(k + 1.2, y), arrowprops=dict(arrowstyle="->", lw=.6))
        else:
            xs = list(np.repeat(np.arange(0, 11.5, 0.25), 2)); ys = ([0, 1, 1, 0] * len(xs))[:len(xs)]
        ax.plot([-0.3] + xs + [11.5], [y] + [y + 0.8 * v for v in ys] + [y], "k-", lw=.8)
    if labeled:
        ax.annotate("", xy=(0.5, 6.7), xytext=(0, 6.7), arrowprops=dict(arrowstyle="<->", lw=.5)); ax.text(0.05, 6.8, "Δφ", fontsize=9)
        ax.annotate("", xy=(1.6, 2.95), xytext=(0.8, 2.95), arrowprops=dict(arrowstyle="<->", lw=.5)); ax.text(0.9, 3.0, "T$_e$", fontsize=9)
        ax.text(1.3, 2.0, "t$_{mid}$ = t$_{rise}$ + T$_e$/2", fontsize=9)
    save(fig, 11, labeled, "同步时序图")


# ====================================================================== 图12 视场与扫描几何
def fig12(labeled):
    fig, ax = plt.subplots(figsize=(10, 7)); ax.set_aspect("equal"); ax.axis("off")
    tw = [[-4, 0], [-1, 30], [1, 30], [4, 0]]; ax.plot(*zip(*tw), "k-", lw=1)
    ax.plot([-1, -1.2, 1.2, 1], [30, 36, 36, 30], "k-", lw=1); ax.plot([-9, 9], [30, 30], "k-", lw=1)
    for i in range(6):
        y0, y1 = i * 5, (i + 1) * 5; x0 = 4 - 0.1 * y0; x1 = 4 - 0.1 * y1
        ax.plot([-x0, x1], [y0, y1], "k-", lw=.4); ax.plot([x0, -x1], [y0, y1], "k-", lw=.4)
    U = np.array([20, 24]); ax.add_patch(Rectangle(U - [0.8, 0.25], 1.6, 0.5, fill=False, lw=1))
    for s in (-1, 1):
        ax.plot([U[0] - 1.6 * s, U[0]], [U[1] + 0.3, U[1] + 0.25], "k-", lw=1)
    a = math.radians(-10)
    ax.plot([U[0], U[0] - 16 * math.cos(a)], [U[1], U[1] + 16 * math.sin(a)], "k-", lw=1.2)
    ax.plot([U[0], U[0] - 16 * math.cos(a + 0.35)], [U[1], U[1] + 16 * math.sin(a + 0.35)], "k-", lw=.5)
    ax.plot([U[0], U[0] - 16 * math.cos(a - 0.35)], [U[1], U[1] + 16 * math.sin(a - 0.35)], "k-", lw=.5)
    hf = math.radians(36.9)
    for s in (-1, 1):
        ax.plot([U[0], U[0] + 24 * math.tan(hf) * s], [U[1], 0], "k-", lw=.6)
    ax_ang = math.radians(180 - 65); hu = math.radians(40)
    for s in (-1, 1):
        g = ax_ang + s * hu; ax.plot([U[0], U[0] + 14 * math.cos(g)], [U[1], U[1] + 14 * math.sin(g)], "k--", lw=.6)
    ax.set_xlim(-12, 32); ax.set_ylim(-1, 40)
    if labeled:
        for (x, y, t) in [(U[0] + 1.3, U[1] + 0.6, "100"), (U[0] - 15, U[1] + 4.2, "激光扫描范围"),
                          (U[0] + 6, 8, "俯视相机视场"), (U[0] - 9, U[1] + 12.5, "仰视相机视场"), (-7, 12, "输电塔")]:
            ax.text(x, y, t, fontsize=10)
    save(fig, 12, labeled, "相机视场与激光扫描范围关系示意图", ["100"])


# ====================================================================== 图13–15 仿真结果
def _load(name):
    p = os.path.join(DATA, name)
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else None


def fig13(labeled):
    R = _load("results.json")
    fd = pickle.load(open(os.path.join(DATA, "_figdata_main.pkl"), "rb"))
    M = R["main"]
    U = fd["U"]; P = fd["P"]
    X = np.asarray(U["nodes_true"]); mi, mj = np.asarray(U["mi"]), np.asarray(U["mj"])
    ex = np.asarray(U["exist"])
    used = np.zeros(len(X), bool); used[mi[ex]] = True; used[mj[ex]] = True
    e_ptm = np.linalg.norm(np.asarray(fd["V_base"]) - X, axis=1)[used] * 1000
    e_new = np.linalg.norm(np.asarray(P["V"]) - X, axis=1)[used] * 1000
    both = ex & np.asarray(fd["present"])
    b_true = np.asarray(U["b"])[both] * 1000
    b_ptm = np.array([220 if c == "main" else 140 if c == "diagonal" else 90 for c in np.asarray(U["cat"])[both]])
    b_new = np.asarray(fd["b_snap"])[both] * 1000
    fig, axs = plt.subplots(1, 3, figsize=(15, 4.6))
    ax = axs[0]
    bins = np.linspace(0, 150, 31)
    ax.hist(e_ptm, bins, histtype="step", color="k", ls="--", lw=1.2, label="点到中心线拟合基线")
    ax.hist(e_new, bins, histtype="stepfilled", color="0.75", ec="k", lw=.8, label="本发明")
    ax.set_xlabel("节点位置误差 / mm"); ax.set_ylabel("节点数"); ax.legend(fontsize=8, frameon=False)
    ax.set_title("(a) 节点误差分布", fontsize=10, y=-0.3)
    ax = axs[1]
    ax.scatter(b_true, b_new, s=6, c="k", marker="o", label="本发明")
    ax.scatter(b_true, b_ptm, s=10, c="none", edgecolors="0.4", marker="s", lw=.6, label="统一截面基线")
    ax.plot([40, 230], [40, 230], "k:", lw=.8)
    ax.set_xlabel("真值肢宽 / mm"); ax.set_ylabel("重建肢宽 / mm"); ax.legend(fontsize=8, frameon=False, loc="upper left")
    ax.set_title("(b) 肢宽重建", fontsize=10, y=-0.3)
    ax = axs[2]
    A = _load("analysis_main.json")
    o = A["orientation"]
    labs = ["可翻转杆件\n(b≥63 mm, L≥2.5 m)", "其余杆件", "全部"]
    v0 = [o["eligible_init_correct"], o["rest_init_correct"], o["all_init_correct"]]
    v1 = [o["eligible_final_correct"], o["rest_final_correct"], o["all_final_correct"]]
    xx = np.arange(3)
    ax.bar(xx - 0.18, np.array(v0) * 100, 0.34, color="white", ec="k", hatch="///", label="初值")
    ax.bar(xx + 0.18, np.array(v1) * 100, 0.34, color="0.6", ec="k", label="本发明")
    ax.set_xticks(xx); ax.set_xticklabels(labs, fontsize=8); ax.set_ylim(70, 100)
    ax.set_ylabel("肢朝向正确率 / %"); ax.legend(fontsize=8, frameon=False)
    ax.set_title("(c) 肢朝向", fontsize=10, y=-0.3)
    fig.tight_layout()
    save(fig, 13, labeled, "仿真重建精度对比图")


ABL_ORDER = ["本发明", "仅激光（降级模式）", "仅影像", "圆柱基元", "独立端点（不共享节点）", "无足迹模型", "无负证据",
             "无对称软先验", "无外参时间标定", "无逐杆件假设检验", "无朝向可观测性门控"]
ABL_SHORT = {"本发明": "本发明", "仅激光（降级模式）": "仅激光", "仅影像": "仅影像", "圆柱基元": "圆柱基元",
             "独立端点（不共享节点）": "独立端点", "无足迹模型": "无足迹", "无负证据": "无负证据", "无对称软先验": "无对称",
             "无外参时间标定": "无外参标定", "无逐杆件假设检验": "无假设检验", "无朝向可观测性门控": "无门控"}


def fig14(labeled):
    R = _load("results.json")
    vals = {"本发明": R["main"]["本发明"]}
    for g in ("abl1", "abl1b", "abl2", "abl2b", "abl3"):
        for k, v in R.get(g, {}).items():
            if isinstance(v, dict) and "RMSEn_m" in v:
                vals[k] = v
    names = [k for k in ABL_ORDER if k in vals]
    fig, axs = plt.subplots(1, 3, figsize=(15, 4.6))
    for ax, key, sc, yl, tt in ((axs[0], "RMSEn_m", 1000, "节点 RMSE / mm", "(a) 节点精度"),
                                (axs[1], "width_MAE_mm", 1, "肢宽平均绝对误差 / mm", "(b) 肢宽精度"),
                                (axs[2], "orient_correct_rate", 100, "肢朝向正确率 / %", "(c) 肢朝向")):
        y = [vals[k][key] * sc for k in names]
        ax.bar(range(len(names)), y, 0.6, color=["0.3"] + ["white"] * (len(names) - 1), ec="k", hatch=None)
        ax.set_xticks(range(len(names))); ax.set_xticklabels([ABL_SHORT[k] for k in names], rotation=60, fontsize=8)
        ax.set_ylabel(yl); ax.set_title(tt, fontsize=10, y=-0.42)
        if key == "orient_correct_rate":
            ax.set_ylim(70, 100)
    fig.tight_layout()
    save(fig, 14, labeled, "消融对比图")


def fig15(labeled):
    R = _load("results.json")
    fd = pickle.load(open(os.path.join(DATA, "_figdata_main.pkl"), "rb"))
    U = fd["U"]; P = fd["P"]; conf = fd["conf"]
    X = np.asarray(U["nodes_true"]); mi, mj = np.asarray(U["mi"]), np.asarray(U["mj"])
    ex = np.asarray(U["exist"])
    used = np.zeros(len(X), bool); used[mi[ex]] = True; used[mj[ex]] = True
    err = np.linalg.norm(np.asarray(P["V"]) - X, axis=1)[used] * 1000
    kap = R["main"]["置信度校准"]["kappa"]
    sig = np.asarray(conf["sig_v"])[used] * 1000 * kap
    fig, axs = plt.subplots(1, 2, figsize=(11, 4.6))
    ax = axs[0]
    ax.scatter(sig, err, s=6, c="k")
    mx = max(sig.max(), err.max()) * 1.05
    ax.plot([0, mx], [0, mx], "k:", lw=.8); ax.plot([0, mx], [0, 2.8 * mx], "k--", lw=.6)
    ax.set_xlim(0, mx); ax.set_ylim(0, mx)
    ax.set_xlabel("校准后节点预测标准差 κσ / mm"); ax.set_ylabel("节点实际误差 / mm")
    ax.set_title("(a) 节点置信度校准", fontsize=10, y=-0.3)
    ax = axs[1]
    ch = R["main"]["多期变化检测"]
    keys = ["detected_lost", "detected_moved"]
    ax.axis("off")
    txt = (f"第二期：一根斜材缺失、一个横担节点位移 (0, 30, -50) mm\n\n"
           f"缺失杆件检出：{'是' if ch['detected_lost'] else '否'}；误报杆件 {ch['false_member_flags']} 根\n"
           f"位移节点检出：{'是' if ch['detected_moved'] else '否'}；估计位移 {ch['moved_node_est_disp_m'] * 1000:.1f} mm\n"
           f"其余被标记节点 {ch['false_node_flags']} 个")
    ax.text(0.02, 0.5, txt, fontsize=10, va="center")
    ax.set_title("(b) 多期复测变化检测", fontsize=10, y=-0.3)
    fig.tight_layout()
    save(fig, 15, labeled, "置信度校准与多期复测结果图")


FIGS = {1: fig1, 2: fig2, 3: fig3, 4: fig4, 5: fig5, 10: fig10, 11: fig11, 12: fig12, 13: fig13, 14: fig14, 15: fig15}

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    a = ap.parse_args()
    only = {int(x) for x in a.only.split(",") if x}
    for n in range(1, 16):
        if only and n not in only:
            continue
        if n == 6:
            geo(6, "iso", "同步采集载荷整体轴测图", KEYS_ALL)
        elif n == 7:
            geo(7, "explode", "同步采集载荷爆炸图", [k for k in KEYS_ALL if k != "13"], figsize=(9, 8))
        elif n == 8:
            geo(8, "section", "倾角调节机构剖视图", ["2", "3", "7", "41", "42", "43", "44", "45", "46"], figsize=(7, 6),
                section=True)
        elif n == 9:
            fig9_views()
        else:
            for lab in (False, True):
                FIGS[n](lab)
        print("图", n, TITLES.get(n), LABELS.get(n))
