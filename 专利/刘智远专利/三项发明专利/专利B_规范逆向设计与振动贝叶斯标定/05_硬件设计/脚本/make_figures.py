# -*- coding: utf-8 -*-
"""专利B 附图生成（黑白线稿）。读取 ../预览/_proj.json（由 build_node_fc.py 生成）与 towerkit 合成塔。
输出：../预览/*.png；ROOT/专利B_.../06_附图/无标注版、标注版/图N.png/.svg/.json；06_附图/附图标记.json
运行：python make_figures.py
"""
import os, sys, json, math
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Polygon, Rectangle
from matplotlib import font_manager

HERE = os.path.dirname(os.path.abspath(__file__))
HW = os.path.dirname(HERE); PB = os.path.dirname(HW); ROOT = os.path.dirname(PB)
PRE = os.path.join(HW, "预览")
OUT0 = os.path.join(PB, "06_附图", "无标注版"); OUT1 = os.path.join(PB, "06_附图", "标注版")
for d in (PRE, OUT0, OUT1): os.makedirs(d, exist_ok=True)
font_manager.fontManager.addfont(r"C:\Windows\Fonts\simsun.ttc")
plt.rcParams["font.family"] = ["SimSun"]; plt.rcParams["axes.unicode_minus"] = False
P = json.load(open(os.path.join(PRE, "_proj.json"), encoding="utf-8"))
META = P["meta"]
ALL_LABELS = {}

def save(fig, ax, n, title, labels):
    for sub, d in (("", OUT1), ("", OUT0)):
        pass
    info = dict(fig=n, title=title, labels=sorted(labels, key=lambda s: int(s) if s.isdigit() else 999))
    for d in (OUT0, OUT1):
        pass
    return info

def finish(fig, n, title, labels, label_artists):
    fig.savefig(os.path.join(OUT1, f"图{n}.png"), dpi=300, facecolor="white")
    fig.savefig(os.path.join(OUT1, f"图{n}.svg"), facecolor="white")
    fig.savefig(os.path.join(PRE, f"图{n}_{title}.png"), dpi=120, facecolor="white")
    for a in label_artists: a.set_visible(False)
    fig.savefig(os.path.join(OUT0, f"图{n}.png"), dpi=300, facecolor="white")
    fig.savefig(os.path.join(OUT0, f"图{n}.svg"), facecolor="white")
    plt.close(fig)
    rec = dict(fig=n, title=title, labels=labels)
    for d in (OUT0, OUT1):
        json.dump(rec, open(os.path.join(d, f"图{n}.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    ALL_LABELS[f"图{n}"] = rec

def new_ax(w=7.0, h=9.0):
    fig = plt.figure(figsize=(w, h)); ax = fig.add_axes([0.02, 0.02, 0.96, 0.96])
    ax.set_aspect("equal"); ax.axis("off"); return fig, ax

def draw_lines(ax, lines, lw=0.6):
    for l in lines:
        a = np.array(l); ax.plot(a[:, 0], a[:, 1], "k-", lw=lw, solid_capstyle="round")

def leaders(ax, anchors, bbox, pad=0.12):
    """anchors: list of (label, (x,y))。标号沿外框环形排布，按极角排序避免交叉。"""
    xmin, xmax, ymin, ymax = bbox
    cx, cy = (xmin + xmax) / 2, (ymin + ymax) / 2
    rx, ry = (xmax - xmin) / 2 * (1 + pad) + 8, (ymax - ymin) / 2 * (1 + pad) + 8
    items = sorted(anchors, key=lambda t: math.atan2(t[1][1] - cy, t[1][0] - cx))
    k = len(items); arts = []
    angs = [math.atan2(t[1][1] - cy, t[1][0] - cx) for t in items]
    # 均匀化：与自身极角折中，保证最小间隔
    base = angs[0]
    slots = [base + 2 * math.pi * i / k for i in range(k)]
    best = None
    for sh in np.linspace(0, 2 * math.pi / k, 12):
        tot = sum(min(abs(((a - (s + sh) + math.pi) % (2 * math.pi)) - math.pi), 3) for a, s in zip(angs, slots))
        if best is None or tot < best[0]: best = (tot, sh)
    for (lab, (x, y)), s in zip(items, slots):
        t = s + best[1]
        lx, ly = cx + rx * math.cos(t), cy + ry * math.sin(t)
        arts += ax.plot([x, lx], [y, ly], "k-", lw=0.45)
        arts += ax.plot([x], [y], "ko", ms=1.6)
        arts.append(ax.text(lx + 4 * math.cos(t), ly + 4 * math.sin(t), lab, fontsize=11, ha="center", va="center",
                            fontfamily="Times New Roman"))
    return arts

def bbox_of(lines):
    a = np.concatenate([np.array(l) for l in lines])
    return a[:, 0].min(), a[:, 0].max(), a[:, 1].min(), a[:, 1].max()

def view_fig(n, title, key, skip=(), w=7, h=8):
    v = P["views"][key]
    fig, ax = new_ax(w, h)
    draw_lines(ax, v["lines"])
    bb = bbox_of(v["lines"])
    seen = {}
    for k, xy in v["anchors"].items():
        if k in skip: continue
        no = str(META[k]["no"])
        seen.setdefault(no, xy)
    arts = leaders(ax, list(seen.items()), bb)
    ax.set_xlim(bb[0] - (bb[1] - bb[0]) * 0.25 - 20, bb[1] + (bb[1] - bb[0]) * 0.25 + 20)
    ax.set_ylim(bb[2] - (bb[3] - bb[2]) * 0.2 - 20, bb[3] + (bb[3] - bb[2]) * 0.2 + 20)
    labs = {no: next(META[k]["cn"] for k in META if str(META[k]["no"]) == no) for no in seen}
    finish(fig, n, title, labs, arts)

# ---------------- 框图工具 ----------------
def blk(ax, x, y, w, h, txt, fs=9, lw=0.9, ls="-"):
    ax.add_patch(Rectangle((x, y), w, h, fill=False, ec="k", lw=lw, ls=ls))
    ax.text(x + w / 2, y + h / 2, txt, ha="center", va="center", fontsize=fs, linespacing=1.3)
    return (x, y, w, h)

def arr(ax, p, q, txt=None, both=False, ls="-"):
    ax.annotate("", xy=q, xytext=p, arrowprops=dict(arrowstyle="<|-|>" if both else "-|>", lw=0.8, color="k",
                                                    shrinkA=0, shrinkB=0, mutation_scale=9, ls=ls))
    if txt: ax.text((p[0] + q[0]) / 2 + 0.6, (p[1] + q[1]) / 2, txt, fontsize=7.5, va="center")

def numtag(ax, b, no, arts, side="r"):
    x, y, w, h = b
    if side == "r": p, q = (x + w, y + h * 0.75), (x + w + 2.2, y + h + 1.2)
    else: p, q = (x, y + h * 0.75), (x - 2.2, y + h + 1.2)
    arts += ax.plot([p[0], q[0]], [p[1], q[1]], "k-", lw=0.45)
    arts.append(ax.text(q[0] + (0.3 if side == "r" else -0.3), q[1] + 0.3, str(no), fontsize=10,
                        ha="left" if side == "r" else "right", fontfamily="Times New Roman"))

def box_ax(w=7, h=9.5, X=70, Y=100):
    fig = plt.figure(figsize=(w, h)); ax = fig.add_axes([0.02, 0.02, 0.96, 0.96])
    ax.set_xlim(0, X); ax.set_ylim(0, Y); ax.axis("off"); return fig, ax

# ---------------- 图1 方法流程 ----------------
def fig1():
    fig, ax = box_ax(7, 10)
    steps = [("S1", "获取输电塔杆件级桁架模型\n（激光点云/影像等任意测量手段）"),
             ("S2", "设计输入自动提取：呼高、横担长、挂点数、\n绝缘子串长→电压等级、转角→塔型、代表档距"),
             ("S3", "规范逆向设计：按 DL/T 5486、GB 50017 荷载组合与\n稳定/长细比约束，分组离散截面优化→截面先验分布"),
             ("S4", "测点优化：Fisher 信息/有效独立法\n在主材节点上选定振动测点"),
             ("S5", "布设角钢夹持式无线三轴振动节点，GNSS 授时\n同步采集环境振动，边缘网关 SSI-COV 识别模态"),
             ("S6", "贝叶斯修正：截面先验 + 模态似然，更新截面组、\n节点连接刚度与基础柔度（TMCMC/代理模型）"),
             ("S7", "输出带不确定度的标定有限元模型，\n风振分析与规范验算")]
    arts = []; y = 92; h = 9.0; prev = None
    for i, (s, t) in enumerate(steps):
        b = blk(ax, 10, y - h, 50, h, t, fs=9)
        ax.text(8.5, y - h / 2, s, ha="right", va="center", fontsize=10, fontfamily="Times New Roman")
        if prev: arr(ax, (35, prev), (35, y))
        prev = y - h; y -= h + 4
    ax.text(35, 97, "开始", ha="center", fontsize=10); arr(ax, (35, 96), (35, 92))
    arr(ax, (35, prev), (35, prev - 3.5)); ax.text(35, prev - 5.5, "结束", ha="center", fontsize=10)
    # 不满足收敛→回到 S4 补测
    ax.plot([60, 64, 64, 60], [92 - 5 * 13 + 4.5, 92 - 5 * 13 + 4.5, 92 - 3 * 13 + 4.5, 92 - 3 * 13 + 4.5], "k-", lw=0.8)
    arr(ax, (64, 92 - 3 * 13 + 4.5), (60, 92 - 3 * 13 + 4.5))
    ax.text(64.6, 92 - 4 * 13 + 4.5, "后验不确定度\n超阈值→补测", fontsize=7.5, va="center")
    finish(fig, 1, "方法流程图", {s: t.replace("\n", "") for s, t in steps}, arts)

# ---------------- 图2 系统框图 ----------------
def fig2():
    fig, ax = box_ax(7, 8, 70, 80); arts = []
    b1 = blk(ax, 2, 62, 20, 12, "几何获取单元\n（点云/影像→\n杆件级桁架模型）")
    b2 = blk(ax, 26, 62, 18, 12, "设计输入\n提取模块")
    b3 = blk(ax, 48, 62, 20, 12, "规范逆向设计\n模块（截面\n先验分布）")
    b4 = blk(ax, 48, 42, 20, 12, "测点优化模块")
    b5 = blk(ax, 2, 22, 22, 22, "", ls="--")
    ax.text(13, 41.5, "振动采集装置", ha="center", fontsize=8.5)
    n1 = blk(ax, 4, 32, 8, 7, "节点\n#1", fs=8); n2 = blk(ax, 14, 32, 8, 7, "节点\n#N", fs=8)
    ax.text(13, 35.5, "…", ha="center"); gw = blk(ax, 4, 23.5, 18, 6, "塔基边缘网关\nSSI-COV", fs=8)
    arr(ax, (8, 32), (8, 29.5), both=True); arr(ax, (18, 32), (18, 29.5), both=True)
    b6 = blk(ax, 28, 22, 18, 12, "贝叶斯修正\n模块")
    b7 = blk(ax, 50, 22, 18, 12, "标定有限元模型\n与规范验算模块")
    b8 = blk(ax, 28, 4, 40, 10, "数据与模型库（GB/T 706 角钢表、规范条文、\n荷载与气象参数、历史模态）", fs=8)
    gs = blk(ax, 2, 48, 12, 8, "GNSS 卫星\n授时 PPS", fs=8, ls=":")
    arr(ax, (22, 68), (26, 68)); arr(ax, (44, 68), (48, 68)); arr(ax, (58, 62), (58, 54))
    arr(ax, (48, 48), (24, 40), "测点"); arr(ax, (22, 26.5), (28, 28), "模态")
    arr(ax, (58, 62), (37, 34)); arr(ax, (46, 28), (50, 28))
    arr(ax, (8, 48), (8, 44)); arr(ax, (48, 14), (48, 22), both=True)
    for b, no in ((b1, 1), (b2, 2), (b3, 3), (b4, 4), (b5, 5), (n1, 51), (gw, 52), (b6, 6), (b7, 7), (b8, 8)):
        numtag(ax, b, no, arts)
    labs = {"1": "几何获取单元", "2": "设计输入提取模块", "3": "规范逆向设计模块", "4": "测点优化模块",
            "5": "振动采集装置", "51": "角钢夹持式无线三轴振动采集节点", "52": "塔基边缘网关",
            "6": "贝叶斯修正模块", "7": "标定有限元模型与规范验算模块", "8": "数据与模型库"}
    finish(fig, 2, "系统框图", labs, arts)

# ---------------- 图3 设计输入提取（塔正视示意） ----------------
def load_tower():
    sys.path.insert(0, os.path.join(ROOT, "00_共享"))
    from towerkit import tower
    return tower.build_tower("suspension")

def tower_front(ax, g, lw_main=0.9):
    N = g.nodes
    for i, j, c in zip(g.mi, g.mj, g.cat):
        a, b = N[i], N[j]
        if a[1] < -0.01 and b[1] < -0.01 or (abs(a[1]) < 5 and min(a[1], b[1]) <= 0 and c != "main" and max(a[1], b[1]) <= 0):
            pass
        if min(a[1], b[1]) > 0.01 and c != "main":
            continue  # 只画前片 + 主材
        ax.plot([a[0], b[0]], [a[2], b[2]], "k-", lw=lw_main if c == "main" else 0.35)

def fig3():
    g = load_tower(); N = g.nodes
    fig, ax = new_ax(7, 9.5); arts = []
    tower_front(ax, g)
    H = N[:, 2].max(); xm = N[:, 0].max()
    att = N[[i for i, t in enumerate(g.ntype) if t in ("attach", "arm_tip")]]
    tip = att[att[:, 0].argmax()]
    # 绝缘子串示意
    for p in N[[i for i, t in enumerate(g.ntype) if t == "attach"]]:
        ax.plot([p[0], p[0]], [p[2], p[2] - 3.5], "k-", lw=1.4)
        ax.plot([p[0] - 0.5, p[0] + 0.5], [p[2] - 3.5, p[2] - 3.5], "k-", lw=1.0)
    lowarm = N[[i for i, t in enumerate(g.ntype) if t == "attach"]][:, 2].min()
    def dim_v(x, z0, z1, t):
        ax.annotate("", xy=(x, z1), xytext=(x, z0), arrowprops=dict(arrowstyle="<->", lw=0.6))
        ax.text(x - 0.4, (z0 + z1) / 2, t, rotation=90, ha="right", va="center", fontsize=9)
    def dim_h(z, x0, x1, t):
        ax.annotate("", xy=(x1, z), xytext=(x0, z), arrowprops=dict(arrowstyle="<->", lw=0.6))
        ax.text((x0 + x1) / 2, z + 0.5, t, ha="center", fontsize=9)
    dim_v(-xm - 2.5, 0, lowarm - 3.5, "呼高 h")
    dim_v(-xm - 5.0, 0, H, "全高 H")
    dim_h(tip[2] + 2.0, 0, tip[0], "横担长 l")
    dim_v(tip[0] + 1.2, tip[2] - 3.5, tip[2], "串长 λ")
    ax.plot([-xm - 7, xm + 7], [0, 0], "k-", lw=1.0)
    for x in np.linspace(-xm - 7, xm + 6, 30): ax.plot([x, x + 0.6], [0, -0.6], "k-", lw=0.4)
    bb = (-xm - 6, xm + 2, 0, H)
    anchors = [("101", tuple(N[[i for i, t in enumerate(g.ntype) if t == "base"]][0][[0, 2]] + [0.3, 6])),
               ("102", (tip[0] * 0.6, tip[2] - 0.2)), ("103", (tip[0], tip[2] - 2)),
               ("104", (0, H - 0.5)), ("105", (-1.5, 20))]
    arts = leaders(ax, anchors, bb, pad=0.25)
    ax.set_xlim(-xm - 14, xm + 10); ax.set_ylim(-4, H + 6)
    finish(fig, 3, "设计输入提取示意图", {"101": "塔身主材", "102": "横担", "103": "绝缘子串挂点", "104": "地线支架", "105": "斜材"}, arts)

# ---------------- 图4/5/6 节点 ----------------
def fig6():
    v = P["views"]["fig3_section"]
    fig, ax = new_ax(7, 7.5)
    draw_lines(ax, v["lines"], lw=0.45)
    hatch = {"Angle": "////", "VBlock": "\\\\\\\\", "Pad1": "....", "Pad2": "....", "Hook1": "xxxx", "Hook2": "xxxx",
             "Rod1": "||||", "Rod2": "----", "Cam": "xxxx", "Mount": "////", "Shell": "", "Stud": "||||", "Acc": "++"}
    for k, polys in v["sections"].items():
        for pl in polys:
            a = np.array(pl)
            ax.add_patch(Polygon(a, closed=True, fill=False, ec="k", lw=0.9, hatch=hatch.get(k, "////")))
    bb = bbox_of(v["lines"])
    anchors = {}
    for k, polys in v["sections"].items():
        a = np.array(polys[0]); no = str(META[k]["no"])
        anchors.setdefault(no, tuple(a.mean(0)))
    for k in ("Nut1", "LockNut"):
        if k in v["anchors"]: anchors.setdefault(str(META[k]["no"]), tuple(v["anchors"][k]))
    arts = leaders(ax, list(anchors.items()), bb, pad=0.18)
    # 夹持力示意
    ax.annotate("", xy=(0, -4), xytext=(0, -20), arrowprops=dict(arrowstyle="-|>", lw=0.8))
    ax.annotate("", xy=(-4, 0), xytext=(-20, 0), arrowprops=dict(arrowstyle="-|>", lw=0.8))
    w = bb[1] - bb[0]; h = bb[3] - bb[2]
    ax.set_xlim(bb[0] - w * 0.3, bb[1] + w * 0.3); ax.set_ylim(bb[2] - h * 0.3, bb[3] + h * 0.3)
    labs = {no: next(META[k]["cn"] for k in META if str(META[k]["no"]) == no) for no in anchors}
    finish(fig, 6, "夹持机构剖视图", labs, arts)

# ---------------- 图7 电路与同步框图 ----------------
def fig7():
    fig, ax = box_ax(7.2, 8, 72, 80); arts = []
    ax.add_patch(Rectangle((1, 18), 52, 60, fill=False, ec="k", lw=0.9, ls="--"))
    ax.text(3, 76, "采集节点", fontsize=8.5)
    acc = blk(ax, 4, 60, 16, 10, "三轴加速度计\n（石英/MEMS）")
    mcu = blk(ax, 24, 44, 16, 14, "低功耗主控 MCU\n采样时间戳\n本地缓存/压缩")
    gn = blk(ax, 24, 64, 16, 8, "GNSS 授时模块\n+TCXO")
    rf = blk(ax, 4, 44, 16, 8, "低功耗无线模块")
    pm = blk(ax, 4, 22, 22, 12, "电源管理：MPPT、\n电池、低温加热\n与电量计")
    sp = blk(ax, 30, 22, 20, 8, "温度/倾角/\n壳体自检")
    ant = blk(ax, 42, 72, 10, 5, "授时天线", fs=7.5)
    sol = blk(ax, 4, 4, 16, 7, "太阳能板")
    gw = blk(ax, 56, 40, 14, 20, "塔基边缘网关\n汇聚、PPS\n对时校核、\nSSI-COV、\n上传")
    arr(ax, (42, 74.5), (40, 70))
    arr(ax, (32, 64), (32, 58), "PPS")
    ax.plot([28, 28, 12, 12], [64, 62, 62, 60], "k-", lw=0.8)
    ax.text(13, 62.6, "PPS 硬触发（外部触发同步采样）", fontsize=7)
    arr(ax, (20, 64), (24, 52), "SPI/UART", both=True)
    arr(ax, (24, 48), (20, 48), both=True)
    arr(ax, (20, 50), (56, 52), "无线（LoRa/Sub-GHz/LTE-M）", both=True, ls="--")
    arr(ax, (12, 11), (12, 22))
    arr(ax, (26, 30), (30, 44)); arr(ax, (40, 30), (36, 44), both=True)
    for b, no in ((acc, 26), (gn, 30), (ant, 33), (mcu, 36), (rf, 29), (pm, 37), (sp, 38), (sol, 31), (gw, 52)):
        numtag(ax, b, no, arts)
    labs = {"26": "三轴加速度计", "30": "GNSS授时模块", "33": "GNSS授时天线", "36": "主控MCU", "29": "低功耗无线模块",
            "37": "电源管理单元", "38": "温度/倾角/自检单元", "31": "太阳能板", "52": "塔基边缘网关"}
    finish(fig, 7, "电路与同步框图", labs, arts)

# ---------------- 图8 测点布置 ----------------
def fig8():
    g = load_tower(); N = g.nodes
    fig, ax = new_ax(7, 9.5)
    tower_front(ax, g)
    # 选点：主材节点中按高度分层（示意 Fisher 选点结果：塔身变坡、横担根、塔头）
    main_nodes = sorted({i for i, j, c in zip(g.mi, g.mj, g.cat) if c == "main" for i in (i, j)})
    cand = [i for i in main_nodes if N[i][0] < 0 and N[i][1] < 0]
    zs = np.array([N[i][2] for i in cand])
    pick = []
    for zt in (12, 24, 34, 42, 50, 57):
        pick.append(cand[int(np.argmin(abs(zs - zt)))])
    pick = list(dict.fromkeys(pick))
    for i in pick:
        x, z = N[i][0], N[i][2]
        ax.add_patch(Rectangle((x - 1.6, z - 1.0), 1.4, 2.0, fill=True, fc="white", ec="k", lw=0.9))
    # 网关
    base = N[[i for i, t in enumerate(g.ntype) if t == "base"]]
    bx = base[:, 0].min()
    ax.add_patch(Rectangle((bx - 3.2, 0.8), 2.2, 2.6, fill=False, ec="k", lw=1.0))
    ax.plot([-12, 12], [0, 0], "k-", lw=1)
    for k, i in enumerate(pick[1:]):
        p, q = (bx - 2.1, 3.4), (N[i][0] - 0.9, N[i][2] - 1.0)
        ax.plot([p[0], q[0]], [p[1], q[1]], "k:", lw=0.5)
    H = N[:, 2].max(); xm = N[:, 0].max()
    anchors = [("51", (N[pick[2]][0] - 0.9, N[pick[2]][2])), ("52", (bx - 2.1, 2.0)),
               ("53", ((bx - 2.1 + N[pick[3]][0]) / 2, (3.4 + N[pick[3]][2]) / 2)), ("101", (N[pick[1]][0] + 0.8, N[pick[1]][2] - 4))]
    arts = leaders(ax, anchors, (-xm - 2, xm, 0, H), pad=0.2)
    ax.set_xlim(-xm - 12, xm + 10); ax.set_ylim(-4, H + 6)
    finish(fig, 8, "测点布置示意图", {"51": "角钢夹持式无线三轴振动采集节点（优化测点，主材外侧）",
                                   "52": "塔基边缘网关", "53": "无线链路", "101": "塔身主材"}, arts)

if __name__ == "__main__":
    fig1(); fig2(); fig3()
    view_fig(4, "节点整体轴测图", "fig1_iso", w=7, h=8)
    view_fig(5, "节点爆炸图", "fig2_exploded", w=7.5, h=8)
    fig6(); fig7(); fig8()
    view_fig(10, "塔基边缘网关轴测图", "fig8_gateway", w=6, h=8)  # 备用图，正式编号由统稿确定
    allmap = {}
    for f, r in ALL_LABELS.items():
        for k, v in r["labels"].items():
            if k.isdigit(): allmap.setdefault(k, v)
    json.dump(dict(figures=ALL_LABELS, reference_signs=dict(sorted(allmap.items(), key=lambda t: int(t[0])))),
              open(os.path.join(PB, "06_附图", "附图标记.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("figs ok", list(ALL_LABELS))
