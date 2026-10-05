# -*- coding: utf-8 -*-
"""Draw the Chinese explanatory figures used in the analysis report (flowcharts, portfolio map)."""
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")
OUT = Path(__file__).resolve().parent / "fig_report"
OUT.mkdir(exist_ok=True)
plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

C_STAGE = ["#DCE9F5", "#E3F1E1", "#FCEBD7", "#EFE3F3"]
C_EDGE = ["#2E5E8C", "#3C7A3A", "#B06A1B", "#7A4B8C"]


def box(ax, x, y, w, h, text, fc, ec, fs=9, bold=False):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.06",
                                fc=fc, ec=ec, lw=1.2))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs,
            weight="bold" if bold else "normal", wrap=True)


def arrow(ax, x0, y0, x1, y1, color="#555555", style="-|>", lw=1.2, ls="-"):
    ax.add_patch(FancyArrowPatch((x0, y0), (x1, y1), arrowstyle=style, mutation_scale=11,
                                 color=color, lw=lw, linestyle=ls))


def fig_ptm_pipeline():
    fig, ax = plt.subplots(figsize=(11, 6.6), dpi=200)
    ax.set_xlim(0, 11)
    ax.set_ylim(0, 6.6)
    ax.axis("off")
    stages = [
        ("① 数据增强", ["PCA 主方向转向\n(横担∥x 轴)", "对称增密\n2/4 份翻转+ICP", "仅坐标双边滤波\n锐化 σs=0.30, σf=0.20 m"]),
        ("② 桁架重建\n(降维+节点优先)", ["90°旋转-ICP\n最近邻距离 d_r\n分塔身/横担+连通域", "R³→R²：xoz 投影\n主材=分层边缘点\n+RANSAC 双线交点",
                                "R²→R¹：主材缓冲\nτ=0.1 m 内点计数\n→AMPD 峰=斜/辅材节点",
                                "连接判定\n对侧 3 近邻\n0.1 m 分段占有率>0.5"]),
        ("③ 拓扑恢复", ["共享棱公式 (2)\n单面 2D → 3D", "横担四面独立重建\n顶点聚类 + 吸附装配",
                    "固定拓扑图优化 (Ceres)\n点到线段距离；斜材端点 1-DoF"]),
        ("④ 仿真分析", ["梁单元 FE：Q355\n主/斜/辅 L220×22 / L140×12 / L90×8", "自重+导线张力+风压 w0=0.35 kN/m²\n塔脚固支，0.1 m 网格",
                    "输出：最大位移 vs 1% 塔高限值"]),
    ]
    ys = [5.0, 3.55, 2.1, 0.65]
    for i, (title, items) in enumerate(stages):
        y = ys[i]
        box(ax, 0.1, y, 1.9, 1.05, title, C_STAGE[i], C_EDGE[i], fs=10, bold=True)
        n = len(items)
        w = (8.7 - 0.25 * (n - 1)) / n
        for j, t in enumerate(items):
            x = 2.2 + j * (w + 0.25)
            box(ax, x, y, w, 1.05, t, "white", C_EDGE[i], fs=8.3 if n < 4 else 7.8)
            if j:
                arrow(ax, x - 0.25, y + 0.52, x - 0.02, y + 0.52, C_EDGE[i])
        if i < 3:
            arrow(ax, 1.05, y - 0.02, 1.05, ys[i + 1] + 1.07, "#333333", lw=1.6)
    ax.text(5.5, 6.55, "PTM（Pylon Truss Modeler）方法流程与关键参数（据论文整理）",
            ha="center", va="top", fontsize=12, weight="bold")
    fig.savefig(OUT / "F1_PTM流程.png", bbox_inches="tight", facecolor="white")
    plt.close(fig)


def fig_portfolio():
    fig, ax = plt.subplots(figsize=(11, 6.4), dpi=200)
    ax.set_xlim(0, 11)
    ax.set_ylim(0, 6.4)
    ax.axis("off")
    # data chain
    box(ax, 0.2, 4.9, 1.9, 0.9, "ULS 点云\n(多期)", "#F2F2F2", "#666666", fs=9.5, bold=True)
    box(ax, 2.6, 4.9, 2.3, 0.9, "LoD3 桁架图\n节点/杆件/类别", "#DCE9F5", "#2E5E8C", fs=9.5, bold=True)
    box(ax, 5.4, 4.9, 2.3, 0.9, "力学可分析模型\n截面/材质/边界", "#E3F1E1", "#3C7A3A", fs=9.5, bold=True)
    box(ax, 8.2, 4.9, 2.6, 0.9, "塔体数字孪生\n安全评估与预警", "#FCEBD7", "#B06A1B", fs=9.5, bold=True)
    for x0, x1 in ((2.1, 2.6), (4.9, 5.4), (7.7, 8.2)):
        arrow(ax, x0, 5.35, x1, 5.35, "#333333", lw=1.6)
    box(ax, 8.2, 3.55, 2.6, 0.9, "InSAR 时序 / 角反射器\nGNSS / 地温（MDS-1）", "#EFE3F3", "#7A4B8C", fs=9)
    arrow(ax, 9.5, 4.45, 9.5, 4.88, "#7A4B8C", lw=1.4)

    pats = [
        (0.2, 1.85, "P5 对称一致性\n残差门控增强\n+ 异常定位", "#2E5E8C", (1.15, 3.0), (1.15, 4.88)),
        (2.4, 1.85, "P2 拓扑继承\n多期节点位移\n+ 构件变更", "#2E5E8C", (3.4, 3.0), (3.75, 4.88)),
        (4.6, 1.85, "P3 规范逆向设计\n截面/材质推断\n+ 观测标定", "#3C7A3A", (5.6, 3.0), (6.5, 4.88)),
        (6.8, 1.85, "P4 杆件置信度\n→可靠度传播\n+ 补测闭环", "#B06A1B", (7.6, 3.0), (8.3, 4.88)),
        (8.9, 1.85, "P1 FE 影响矩阵\nInSAR 形变解耦\n+ 基础沉降反演", "#7A4B8C", (9.9, 3.0), (9.9, 3.53)),
    ]
    for x, y, t, c, a0, a1 in pats:
        box(ax, x, y, 1.95, 1.1, t, "white", c, fs=8.6, bold=True)
        arrow(ax, a0[0], a0[1], a1[0], a1[1], c, lw=1.2, ls="--")
    box(ax, 0.2, 0.35, 10.6, 1.1,
        "外围：P6 节间规律自适应一维峰检测（可并入 P2/P5 从权）｜ U1 塔脚抱箍式 GNSS-角反射器-地温一体化监测装置（实用新型，承接 MDS-1）\n"
        "｜ S1 软件著作权：LoD3 桁架重建与塔体孪生评估平台（承接 WebGIS 可视化平台）｜ 适用扩展：通信塔、风电格构塔、光热吸热塔支架",
        "#FAFAFA", "#999999", fs=8.6)
    ax.text(5.5, 6.33, "以 PTM 为起点的专利组合布局（本报告建议）", ha="center", va="top", fontsize=12, weight="bold")
    fig.savefig(OUT / "F2_专利组合布局.png", bbox_inches="tight", facecolor="white")
    plt.close(fig)


def fig_p1_route():
    fig, ax = plt.subplots(figsize=(11, 5.6), dpi=200)
    ax.set_xlim(0, 11)
    ax.set_ylim(0, 5.6)
    ax.axis("off")
    c = "#7A4B8C"
    steps = [
        (0.2, 3.9, "S1 ULS→LoD3\n桁架图 + FE 模型"),
        (2.4, 3.9, "S2 单位工况\n4 腿 × (dz, dx, dy)\n+ 均匀温升 + 日照温差"),
        (4.6, 3.9, "S3 LoD3 雷达成像仿真\n预测散射体/CR 位置\n与观测 PS 匹配到节点"),
        (6.8, 3.9, "S4 观测算子\nG = LOS·影响向量\n升/降轨联合"),
        (9.0, 3.9, "S5 时序正则反演\ns_k(t)、ΔT 系数\n(Kalman / 最小二乘)"),
    ]
    for i, (x, y, t) in enumerate(steps):
        box(ax, x, y, 1.9, 1.2, t, "white", c, fs=8.5)
        if i:
            arrow(ax, x - 0.3, y + 0.6, x - 0.02, y + 0.6, c, lw=1.4)
    box(ax, 0.2, 1.9, 10.6, 1.25,
        "观测方程：d_LOS(p, t) = Σ_k G_{p,k} · s_k(t) + H_p · ΔT(t) + W_p · q(t) + ε\n"
        "p：塔体/塔脚散射体（含角反射器）；s_k：第 k 塔腿基础位移；H_p：由 LoD3 几何与太阳位置算得的热致位移响应；q：风/导线荷载代理量",
        "#EFE3F3", c, fs=9.2)
    box(ax, 0.2, 0.3, 5.1, 1.2, "S6 正演：s_k(t) → 杆件轴力/应力比、塔顶倾斜率\n对照 DL/T 741 倾斜限值与杆件承载力 → 分级预警", "white", c, fs=8.8)
    box(ax, 5.7, 0.3, 5.1, 1.2, "S7 冻胀-融沉季节模型外推（地温/Stefan）\n+ 影响矩阵 Fisher 信息 → 角反射器最优安装位置", "white", c, fs=8.8)
    arrow(ax, 9.95, 3.88, 9.95, 3.17, c, lw=1.4)
    arrow(ax, 2.7, 1.88, 2.7, 1.52, c, lw=1.4)
    arrow(ax, 8.2, 1.88, 8.2, 1.52, c, lw=1.4)
    ax.text(5.5, 5.55, "P1 技术路线：用 LoD3 有限元影响矩阵把 InSAR 塔体形变“翻译”为基础沉降与杆件应力",
            ha="center", va="top", fontsize=11.5, weight="bold")
    fig.savefig(OUT / "F3_P1技术路线.png", bbox_inches="tight", facecolor="white")
    plt.close(fig)


if __name__ == "__main__":
    fig_ptm_pipeline()
    fig_portfolio()
    fig_p1_route()
    print("figures:", sorted(p.name for p in OUT.glob("*.png")))
