# -*- coding: utf-8 -*-
# 专利D 附图1/2/3/4/7/8 黑白线稿生成：无标注版(仅数字引线) + 标注版(数字+中文) + 附图标记.json
import os, json, numpy as np, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Circle, Polygon, Rectangle
plt.rcParams["font.sans-serif"] = ["SimHei"]; plt.rcParams["axes.unicode_minus"] = False
HERE = os.path.dirname(os.path.abspath(__file__)); HW = os.path.dirname(HERE)
FIG = os.path.join(os.path.dirname(HW), "06_附图"); PRE = os.path.join(HW, "预览")
for d in ("无标注版", "标注版"): os.makedirs(os.path.join(FIG, d), exist_ok=True)
os.makedirs(PRE, exist_ok=True)
REFS = {}

def new(w=8, h=10):
    f, a = plt.subplots(figsize=(w, h)); a.set_aspect("equal"); a.axis("off"); return f, a

def node(a, x, y, w, h, ref, txt, lab, shape="box"):
    if shape == "dia":
        a.add_patch(Polygon([(x, y + h / 2), (x + w / 2, y), (x, y - h / 2), (x - w / 2, y)], fill=False, lw=1.2))
    else:
        a.add_patch(FancyBboxPatch((x - w / 2, y - h / 2), w, h, boxstyle="round,pad=0.02,rounding_size=0.05", fill=False, lw=1.2))
    a.text(x, y, ("S%d " % ref if ref < 100 else "%d " % ref) + (txt if lab else ""), ha="center", va="center", fontsize=9)

def arrow(a, p, q, txt=None):
    a.annotate("", q, p, arrowprops=dict(arrowstyle="-|>", lw=1, color="k"))
    if txt: a.text((p[0] + q[0]) / 2 + 0.08, (p[1] + q[1]) / 2, txt, fontsize=8)

def lead(a, p, q, n):  # 数字引线
    a.plot([p[0], q[0]], [p[1], q[1]], "k-", lw=0.6); a.text(q[0], q[1], str(n), fontsize=10, ha="center", va="bottom")

def save(f, name, lab):
    for ext in ("png",):
        f.savefig(os.path.join(FIG, "标注版" if lab else "无标注版", name + "." + ext), dpi=300, bbox_inches="tight", facecolor="w")
    if lab: f.savefig(os.path.join(PRE, name + ".png"), dpi=90, bbox_inches="tight", facecolor="w")
    plt.close(f)

# ---------- 图1 方法流程 ----------
S = [(101, "获取初始航线并采集点云/影像"), (102, "三维重建与杆件骨架匹配"), (103, "逐杆件置信度计算"),
     (104, "三态判别：可信/存疑/缺失"), (105, "有限元灵敏度加权补测价值"), (106, "生成带电安全壳并筛选壳内外候选视点"),
     (107, "子模贪心选视点 + TSP 排序"), (108, "下发航点，机上增量重建与评估"), (109, "满足停止准则？"), (110, "输出补测结果与杆件状态")]
def fig1(lab):
    f, a = new(6, 12); ys = np.linspace(11, 0.5, len(S))
    for (r, t), y in zip(S, ys): node(a, 3, y, 4.6 if r != 109 else 3.4, 0.7, r, t, lab, "dia" if r == 109 else "box")
    for i in range(len(S) - 1): arrow(a, (3, ys[i] - 0.38), (3, ys[i + 1] + 0.38), "是" if (lab and S[i][0] == 109) else None)
    a.plot([4.7, 5.6, 5.6], [ys[8], ys[8], ys[2]], "k-", lw=1); arrow(a, (5.6, ys[2]), (5.32, ys[2]))
    if lab: a.text(5.65, (ys[8] + ys[2]) / 2, "否", fontsize=8)
    a.set_xlim(0, 6.2); a.set_ylim(0, 11.6); save(f, "图1_方法流程", lab)
REFS["图1"] = {"S%d" % r: t for r, t in S}

# ---------- 图2 系统框图 ----------
B2 = {201: ("数据获取模块", 1, 6), 202: ("重建与骨架匹配模块", 1, 4.5), 203: ("杆件置信度三态判别模块", 1, 3),
      204: ("有限元灵敏度模块", 4.5, 3), 205: ("带电安全壳生成模块", 4.5, 6), 206: ("候选视点生成模块", 4.5, 4.5),
      207: ("子模贪心与TSP规划模块", 8, 4.5), 208: ("机上增量评估与停止判定模块", 8, 3), 209: ("航点下发模块", 8, 6),
      300: ("机载实时评估装置", 8, 1.3)}
def fig2(lab):
    f, a = new(11, 7)
    for r, (t, x, y) in B2.items(): node(a, x + 0.6, y, 2.9, 0.8, r, t, lab)
    E = [(201, 202), (202, 203), (203, 206), (204, 206), (205, 206), (206, 207), (207, 209), (209, 201), (208, 207), (203, 208), (300, 208)]
    for u, v in E:
        (_, x1, y1), (_, x2, y2) = B2[u], B2[v]; p = np.array([x1 + .6, y1]); q = np.array([x2 + .6, y2]); d = q - p
        k = min(1.45 / max(abs(d[0]), 1e-9), 0.4 / max(abs(d[1]), 1e-9)); arrow(a, p + d * k, q - d * k)
    a.add_patch(Rectangle((-0.3, 0.6), 11.2, 6.1, fill=False, ls="--", lw=0.8))
    a.set_xlim(-0.5, 11); a.set_ylim(0.5, 7); save(f, "图2_系统框图", lab)
REFS["图2"] = {str(k): v[0] for k, v in B2.items()}

# ---------- 图3 三态判别 ----------
def tower(a, ox, s=1.0):
    L = [(-1, 0), (-0.4, 4), (0.4, 4), (1, 0)]; pts = [(ox + x * s, y * s) for x, y in L]
    a.plot(*zip(*pts), "k-", lw=1)
    segs = []
    for i in range(4):
        y0, y1 = i, i + 1; w0, w1 = 1 - 0.15 * y0, 1 - 0.15 * y1
        segs += [((-w0, y0), (w1, y1)), ((w0, y0), (-w1, y1)), ((-w1, y1), (w1, y1))]
    return [((ox + p[0] * s, p[1] * s), (ox + q[0] * s, q[1] * s)) for p, q in segs]
def fig3(lab):
    f, a = new(10, 5); segs = tower(a, 2)
    st = ["T", "T", "T", "U", "T", "M", "U", "T", "T", "M", "T", "T"]
    for (p, q), s in zip(segs, st):
        a.plot([p[0], q[0]], [p[1], q[1]], "k-", lw={"T": 2.2, "U": 1.0, "M": 0.8}[s], ls={"T": "-", "U": "--", "M": ":"}[s])
    lead(a, ((segs[0][0][0] + segs[0][1][0]) / 2, 0.5), (0.3, 1.2), 301)
    lead(a, ((segs[3][0][0] + segs[3][1][0]) / 2, 1.5), (3.8, 2.0), 302)
    lead(a, ((segs[5][0][0] + segs[5][1][0]) / 2, 1.5), (0.2, 2.6), 303)
    # 判别轴
    a.plot([5, 9.5], [1, 1], "k-", lw=1); a.annotate("", (9.6, 1), (9.4, 1), arrowprops=dict(arrowstyle="-|>"))
    for x, n in ((6.5, 304), (8, 305)): a.plot([x, x], [0.85, 1.15], "k-"); a.text(x, 0.55, str(n), ha="center")
    for x, ls, n in ((5.7, ":", 303), (7.25, "--", 302), (8.8, "-", 301)): a.plot([x - .4, x + .4], [2, 2], "k", ls=ls, lw=1.5); a.text(x, 2.2, str(n), ha="center")
    if lab:
        a.text(9.6, 0.6, "置信度c", fontsize=9); a.text(6.5, 0.25, "τ_low", ha="center", fontsize=8); a.text(8, 0.25, "τ_high", ha="center", fontsize=8)
        for x, t in ((5.7, "缺失"), (7.25, "存疑"), (8.8, "可信")): a.text(x, 2.6, t, ha="center", fontsize=9)
    a.set_xlim(0, 10); a.set_ylim(0, 4.5); save(f, "图3_三态判别示意", lab)
REFS["图3"] = {"301": "可信杆件(实线粗)", "302": "存疑杆件(虚线)", "303": "缺失杆件(点线)", "304": "下阈值τ_low", "305": "上阈值τ_high"}

# ---------- 图4 置信度×灵敏度 ----------
def fig4(lab):
    f, a = new(6, 6); rng = np.random.default_rng(3); c = rng.uniform(0, 1, 40); s = rng.uniform(0, 1, 40)
    a.set_axis_on(); a.set_aspect("auto")
    for sp in ("top", "right"): a.spines[sp].set_visible(False)
    a.set_xticks([]); a.set_yticks([])
    X, Y = np.meshgrid(np.linspace(0, 1, 50), np.linspace(0, 1, 50)); a.contour(X, Y, (1 - X) * Y, levels=[.1, .25, .45], colors="k", linewidths=.7, linestyles="--")
    hi = (1 - c) * s > 0.25; a.scatter(c[~hi], s[~hi], facecolors="w", edgecolors="k", s=25); a.scatter(c[hi], s[hi], c="k", s=25)
    a.axvline(0.6, color="k", lw=.6)
    lead(a, (c[hi][0], s[hi][0]), (0.05, 0.95), 401); lead(a, (c[~hi][0], s[~hi][0]), (0.9, 0.08), 402); lead(a, (0.3, 0.83), (0.42, 0.97), 403); lead(a, (0.6, 0.5), (0.7, 0.55), 404)
    if lab: a.set_xlabel("杆件置信度 c"); a.set_ylabel("有限元灵敏度 s"); a.set_title("补测价值 w=(1-c)·s", fontsize=10)
    else: a.set_xlabel("c"); a.set_ylabel("s")
    save(f, "图4_置信度灵敏度加权示意", lab)
REFS["图4"] = {"401": "高补测价值杆件(实心)", "402": "低补测价值杆件(空心)", "403": "补测价值等值线", "404": "置信度阈值线"}

# ---------- 图7 装置电路/数据流框图 ----------
B7 = {701: ("激光雷达(以太网/PPS)", 0.5, 6), 702: ("工频电场传感器+前置放大", 0.5, 4.3), 703: ("24bit ADC(SPI)", 3.5, 4.3),
      704: ("边缘计算单元 Jetson Orin NX 16GB", 4.5, 6), 705: ("NVMe SSD", 8, 7.2), 706: ("4G/图传回传模块", 8, 6),
      707: ("飞控 MAVLink/PSDK(UART)", 8, 4.3), 708: ("安全壳冗余越界判定(MCU看门狗)", 4.5, 2.6), 709: ("DC-DC 12V/5V 电源管理", 0.5, 1.2),
      710: ("散热风扇PWM/温度监测", 4.5, 1.2), 711: ("无人机电池 6S 22.2V", 0.5, 7.4)}
def fig7(lab):
    f, a = new(12, 7.5)
    for r, (t, x, y) in B7.items(): node(a, x + 1.3, y, 2.9, 0.75, r, t, lab)
    E = [(701, 704), (702, 703), (703, 704), (703, 708), (704, 705), (704, 706), (704, 707), (708, 707), (711, 709), (709, 704), (710, 704)]
    for u, v in E:
        (_, x1, y1), (_, x2, y2) = B7[u], B7[v]; p = np.array([x1 + 1.3, y1]); q = np.array([x2 + 1.3, y2]); d = q - p
        k = min(1.5 / max(abs(d[0]), 1e-9), 0.42 / max(abs(d[1]), 1e-9)); arrow(a, p + d * k, q - d * k)
    a.add_patch(Rectangle((-0.1, 0.6), 7.6, 6.15, fill=False, ls="--", lw=.8)); a.text(7.3, 0.7, "300", fontsize=10)
    a.set_xlim(-0.3, 11.5); a.set_ylim(0.5, 8); save(f, "图7_机载装置电路数据流框图", lab)
REFS["图7"] = {str(k): v[0] for k, v in B7.items()}; REFS["图7"]["300"] = "机载实时评估装置(虚线框)"

# ---------- 图8 轴测与爆炸 ----------
E8 = json.load(open(os.path.join(HW, "模型", "edges_iso.json")))
rec = json.load(open(os.path.join(HW, "模型", "构建记录.json"), encoding="utf-8"))
def fig8(lab):
    f, axs = plt.subplots(1, 2, figsize=(12, 9))
    for a, key, dx in ((axs[0], "assembled", 0), (axs[1], "exploded", 0)):
        a.set_aspect("equal"); a.axis("off")
        for ref, lines in E8[key].items():
            for ln in lines:
                p = np.array(ln); a.plot(p[:, 0], p[:, 1], "k-", lw=.5)
        if key == "exploded":
            for ref, lines in E8[key].items():
                p = np.vstack([np.array(l) for l in lines]); c = p.mean(0); m = p[p[:, 0].argmax()]
                a.plot([m[0], m[0] + 40], [c[1], c[1]], "k-", lw=.5)
                nm = [x["name"] for x in rec["parts"] if str(x["ref"]) == ref][0]
                a.text(m[0] + 42, c[1], "8%s" % ref + (" " + nm if lab else ""), fontsize=8, va="center")
        a.set_title(("(a) 装配轴测" if key == "assembled" else "(b) 爆炸视图") if lab else ("(a)" if key == "assembled" else "(b)"), fontsize=10, y=-0.05)
    save(f, "图8_装置结构轴测与爆炸", lab)
REFS["图8"] = {"8%d" % x["ref"]: x["name"] for x in rec["parts"]}

for lab in (False, True):
    fig1(lab); fig2(lab); fig3(lab); fig4(lab); fig7(lab); fig8(lab)
J=os.path.join(FIG, "附图标记.json")
old=json.load(open(J,encoding="utf-8")) if os.path.exists(J) else {}
old.update(REFS); REFS=old
json.dump(REFS, open(os.path.join(FIG, "附图标记.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("done")
