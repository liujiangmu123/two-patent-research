# -*- coding: utf-8 -*-
# 专利E 附图生成：图1、2、5、6、7、8（黑白线稿，数字引线）；图3/4/9由仿真组提供，不生成
import os, json, math
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Circle, Polygon, Wedge

plt.rcParams["font.sans-serif"] = ["SimSun", "Microsoft YaHei", "SimHei"]
plt.rcParams["axes.unicode_minus"] = False
HW = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIG = os.path.join(os.path.dirname(HW), "06_附图")
OUT = {"无标注版": os.path.join(FIG, "无标注版"), "标注版": os.path.join(FIG, "标注版")}
for d in OUT.values(): os.makedirs(d, exist_ok=True)
LABELS = {}

def save(fig, ax, name, items):
    """items: [(编号, 名称, (x,y)目标点, (tx,ty)引线终点)]"""
    LABELS[name] = {str(n): t for n, t, _, _ in items}
    lines = []
    for n, t, p, q in items:
        l = ax.annotate(str(n), xy=p, xytext=q, fontsize=11, ha="center", va="center",
                        arrowprops=dict(arrowstyle="-", lw=0.7, color="k"))
        lines.append(l)
    fig.savefig(os.path.join(OUT["无标注版"], name + ".png"), dpi=300, bbox_inches="tight", facecolor="w")
    for n, t, p, q in items:   # 标注版：编号后附名称
        pass
    for l, (n, t, p, q) in zip(lines, items):
        l.set_text("%d %s" % (n, t)); l.set_fontsize(8)
    fig.savefig(os.path.join(OUT["标注版"], name + ".png"), dpi=300, bbox_inches="tight", facecolor="w")
    plt.close(fig)

def box(ax, x, y, w, h, txt="", fs=9):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="square,pad=0", fc="w", ec="k", lw=1.0))
    if txt: ax.text(x + w / 2, y + h / 2, txt, ha="center", va="center", fontsize=fs)

def arrow(ax, a, b):
    ax.annotate("", xy=b, xytext=a, arrowprops=dict(arrowstyle="-|>", lw=0.9, color="k"))

def canvas(w=8, h=10):
    fig, ax = plt.subplots(figsize=(w, h)); ax.set_aspect("equal"); ax.axis("off"); return fig, ax

# ---------- 图1 方法流程 ----------
fig, ax = canvas(7, 11)
steps = [("S1", "多相机布站、GNSS授时同步触发采集视频"), ("S2", "IMU自振动补偿与图像稳像"),
         ("S3", "桁架三维线框图投影至各相机像平面"), ("S4", "沿投影杆件提取亚像素位移时程"),
         ("S5", "多视角位移融合重建节点三维位移"), ("S6", "随机子空间/频域分解识别模态"),
         ("S7", "振型映射回桁架图并输出评估结果")]
items = []
for i, (s, t) in enumerate(steps):
    y = 10 - i * 1.4
    box(ax, 0, y, 6, 0.9, s + "  " + t)
    if i: arrow(ax, (3, y + 1.4), (3, y + 0.9))
    items.append((101 + i, s, (6, y + 0.45), (7, y + 0.45)))
ax.set_xlim(-0.5, 7.5); ax.set_ylim(1, 11.2)
save(fig, ax, "图1_方法流程", items)

# ---------- 图2 系统框图 ----------
fig, ax = canvas(10, 7)
for k in range(3):
    box(ax, 0, 5 - k * 1.8, 2.6, 1.3, "地面同步测振\n相机装置 #%d" % (k + 1))
    arrow(ax, (2.6, 5.65 - k * 1.8), (4, 3.85))
box(ax, 4, 3.2, 2.6, 1.3, "边缘计算盒\n(稳像/位移提取)")
box(ax, 4, 0.6, 2.6, 1.3, "GNSS授时\nPPS同步网")
arrow(ax, (5.3, 1.9), (5.3, 3.2))
box(ax, 7.5, 3.2, 2.6, 1.3, "中心处理服务器\n(融合/模态识别)")
arrow(ax, (6.6, 3.85), (7.5, 3.85))
box(ax, 7.5, 5.6, 2.6, 1.0, "桁架三维线框图库")
arrow(ax, (8.8, 5.6), (8.8, 4.5))
box(ax, 7.5, 0.8, 2.6, 1.0, "振型评估与告警输出")
arrow(ax, (8.8, 3.2), (8.8, 1.8))
items = [(10, "相机装置", (0, 5.6), (-0.7, 6.6)), (22, "边缘计算盒", (4, 4.2), (3.5, 5.0)),
         (20, "授时同步网", (4, 1.2), (3.3, 1.2)), (40, "中心处理服务器", (10.1, 4.0), (10.8, 4.0)),
         (41, "线框图库", (10.1, 6.1), (10.8, 6.1)), (42, "评估输出", (10.1, 1.3), (10.8, 1.3))]
ax.set_xlim(-1.2, 11.3); ax.set_ylim(0, 7)
save(fig, ax, "图2_系统框图", items)

# ---------- 图5/6 轴测与爆炸（取自FreeCAD边线）----------
E = json.load(open(os.path.join(HW, "模型", "edges.json"), encoding="utf-8"))
def proj(p):
    x, y, z = p; a = math.radians(30)
    return ((x - y) * math.cos(a), (x + y) * math.sin(a) + z)
NAME = {}
def iso(name, explode):
    fig, ax = canvas(8, 10); items = []
    tags = {"31": (-1, 0.15), "32": (1, 0.6), "33": (1, 0.0), "34": (-1, 0.0), "11": (-1, 0.0), "12": (1, 0.3),
            "13": (-1, 0.0), "14": (1, 0.0), "21": (1, 0.0), "22": (1, 0.0), "23": (-1, 0.0), "24": (-1, 0.0)}
    for no, d in E.items():
        off = np.array(d["explode"]) if explode else np.zeros(3)
        for e in d["edges"]:
            pts = [proj(np.array(q) + off) for q in e]
            xs, ys = zip(*pts); ax.plot(xs, ys, "k-", lw=0.45)
        c = proj(np.array(d["center"]) + off)
        s, dy = tags[no]
        items.append((int(no), d["name"].split("（")[0], c, (c[0] + s * 650, c[1] + dy * 300 + 150)))
    ax.autoscale(); ax.margins(0.12)
    save(fig, ax, name, items)
iso("图5_相机装置轴测图", False)
iso("图6_相机装置爆炸图", True)

# ---------- 图7 同步与电路框图 ----------
fig, ax = canvas(11, 7)
B = {21: (0, 5, "GNSS天线"), 25: (2.5, 5, "GNSS授时模块\n(PPS+UTC)"), 26: (5.2, 5, "FPGA/MCU\n触发与时间戳板"),
     11: (8, 5, "全局快门相机"), 13: (8, 2.8, "IMU(≥1kHz)"), 22: (5.2, 2.8, "边缘计算SoC\n(GPU/NPU)"),
     27: (2.5, 2.8, "4G/5G/LoRa\n通信模块"), 23: (0, 0.6, "锂电池\n24V"), 24: (0, 2.8, "太阳能板"),
     28: (2.5, 0.6, "MPPT/电源管理\nDC-DC 12/5/3.3V"), 33: (8, 0.6, "云台驱动")}
for k, (x, y, t) in B.items(): box(ax, x, y, 2.0, 1.1, t, 8.5)
for a, b in [((2, 5.55), (2.5, 5.55)), ((4.5, 5.55), (5.2, 5.55)), ((7.2, 5.75), (8, 5.75)),
             ((8, 5.3), (7.2, 5.3)), ((8, 3.35), (7.2, 3.35)), ((6.2, 5), (6.2, 3.9)),
             ((5.2, 3.35), (4.5, 3.35)), ((1, 2.8), (1, 1.7)), ((2, 1.15), (2.5, 1.15)),
             ((4.5, 1.15), (8, 1.15)), ((3.5, 1.7), (3.5, 2.8)), ((7.2, 3.1), (8, 1.4))]:
    arrow(ax, a, b)
ax.text(7.6, 5.95, "触发", fontsize=7, ha="center"); ax.text(7.6, 4.95, "曝光回传", fontsize=7, ha="center")
items = [(k, t.split("\n")[0], (x + 2.0, y + 1.1), (x + 2.3, y + 1.45)) for k, (x, y, t) in B.items()]
ax.set_xlim(-0.5, 10.8); ax.set_ylim(0, 6.8)
save(fig, ax, "图7_同步与电路框图", items)

# ---------- 图8 多相机布站平面图 ----------
fig, ax = canvas(9, 9)
ax.add_patch(Polygon([[-6, -6], [6, -6], [6, 6], [-6, 6]], fc="w", ec="k", lw=1.2))
ax.plot([-6, 6], [-6, 6], "k-", lw=0.6); ax.plot([-6, 6], [6, -6], "k-", lw=0.6)
ax.add_patch(Circle((0, 0), 40, fill=False, ls="--", lw=0.6)); ax.add_patch(Circle((0, 0), 150, fill=False, ls="--", lw=0.6))
ax.plot([-170, 170], [0, 0], "k-.", lw=0.5)  # 线路走向
cams = [(80, 200), (80, 290), (110, 245)]
items = [(50, "铁塔", (6, 6), (25, 25)), (51, "40m内界", (-28, 28), (-40, 50)),
         (52, "150m外界", (-106, 106), (-125, 125)), (53, "线路中心线", (-150, 0), (-150, -15))]
for i, (r, a) in enumerate(cams):
    p = np.array([r * math.cos(math.radians(a)), r * math.sin(math.radians(a))])
    ax.add_patch(Polygon(p + np.array([[-4, -3], [4, -3], [4, 3], [-4, 3]]), fc="w", ec="k"))
    ax.plot([p[0], 0], [p[1], 0], "k:", lw=0.6)
    ang = math.degrees(math.atan2(-p[1], -p[0])); ax.add_patch(Wedge(p, 25, ang - 9, ang + 9, fill=False, lw=0.6))
    items.append((54 + i, "相机装置#%d" % (i + 1), tuple(p), tuple(p * 1.18)))
ax.add_patch(Wedge((0, 0), 30, 200, 290, fill=False, lw=0.6)); ax.text(-8, -36, "θ=60°~120°", fontsize=8)
ax.set_xlim(-170, 170); ax.set_ylim(-170, 170)
save(fig, ax, "图8_多相机布站平面图", items)

jp = os.path.join(FIG, "附图标记.json")
J = json.load(open(jp, encoding="utf-8")) if os.path.exists(jp) else {}
J.setdefault("附图", {}).update(LABELS)
J["硬件附图说明"] = "图1、2、5、6、7、8由硬件组生成；图3、4、9由仿真组提供"
json.dump(J, open(jp, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
# 预览
import shutil
for f in os.listdir(OUT["标注版"]):
    if f[:2] in ("图5", "图6"): shutil.copy(os.path.join(OUT["标注版"], f), os.path.join(HW, "预览", f))
print("done", list(LABELS))
