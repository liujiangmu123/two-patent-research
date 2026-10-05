# 生成图1-图8 黑白线稿（无标注版/标注版）+ 附图标记.json
import json, os, math, numpy as np, matplotlib
matplotlib.use("Agg"); import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Polygon, Rectangle, Circle
plt.rcParams["font.sans-serif"] = ["SimSun", "SimHei", "Microsoft YaHei"]; plt.rcParams["axes.unicode_minus"] = False
H = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.join(H, ".."); MOD = os.path.join(ROOT, "..", "05_硬件设计", "模型")
E = json.load(open(os.path.join(MOD, "edges.json"), encoding="utf-8"))
ALL = {}

def save(fig, ax, n, title, labels, leaders):
    for sub, lab in (("无标注版", False), ("标注版", True)):
        arts = []
        if lab:
            for num, (xy, txy) in leaders.items():
                arts.append(ax.annotate(str(num), xy=xy, xytext=txy, fontsize=11, color="k",
                                        arrowprops=dict(arrowstyle="-", lw=0.6, color="k")))
        fig.savefig(os.path.join(ROOT, sub, "图%d.png" % n), dpi=300, bbox_inches="tight", facecolor="white")
        for a in arts: a.remove()
    d = {"title": title, "size_mm": [160, 120], "labels": {str(k): v for k, v in labels.items()}}
    json.dump(d, open(os.path.join(ROOT, "标注版", "图%d.json" % n), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    ALL["图%d" % n] = d; plt.close(fig)

def box(ax, x, y, w, h, t):
    ax.add_patch(FancyBboxPatch((x - w / 2, y - h / 2), w, h, boxstyle="round,pad=0.02", fc="w", ec="k", lw=1))
    ax.text(x, y, t, ha="center", va="center", fontsize=9)
    return (x + w / 2, y + h / 2 * 0.6)

def arrow(ax, a, b): ax.annotate("", xy=b, xytext=a, arrowprops=dict(arrowstyle="->", lw=1, color="k"))

def canvas(w=8, h=6):
    fig, ax = plt.subplots(figsize=(w, h)); ax.set_aspect("equal"); ax.axis("off"); return fig, ax

# 图1 方法流程
fig, ax = canvas(6, 9)
steps = [("S1 建立杆件级桁架有限元模型，\n施加各塔腿单位位移/单位温升工况，\n构建影响矩阵", 101),
         ("S2 由LoD3模型与太阳位置\n计算日照遮挡，得杆件阴阳面热场", 102),
         ("S3 散射体仿真并与PS/角反射器\n观测关联，确定观测算子行", 103),
         ("S4 升降轨LOS时序联合反演\n（扣除热胀分量）", 104),
         ("S5 输出各塔腿基础沉降、\n差异沉降、塔身倾斜与预警分级", 105)]
L = {}; LD = {}
for i, (t, n) in enumerate(steps):
    y = 8 - i * 1.8; p = box(ax, 0, y, 4.2, 1.2, t); L[n] = t.replace("\n", ""); LD[n] = (p, (2.6, y + 0.4))
    if i: arrow(ax, (0, y + 1.8 - 0.62), (0, y + 0.62))
ax.set_xlim(-2.5, 3.2); ax.set_ylim(0, 9)
save(fig, ax, 1, "方法流程图", L, LD)

# 图2 系统框图
fig, ax = canvas(9, 6)
B = [(1.5, 4.5, "塔材夹持式双向\n三面角反射器", 201), (1.5, 3, "杆件阴阳面\n测温节点", 202), (1.5, 1.5, "塔基采集单元", 203),
     (4.5, 4.5, "SAR影像获取与\nPS/CR提取模块", 204), (4.5, 3, "影响矩阵构建模块", 205), (4.5, 1.5, "热场计算模块", 206),
     (7.5, 3.8, "散射体关联与升降轨\n联合反演模块", 207), (7.5, 2.2, "沉降/倾斜输出\n与预警模块", 208)]
L = {}; LD = {}
for x, y, t, n in B:
    p = box(ax, x, y, 2.3, 1.0, t); L[n] = t.replace("\n", ""); LD[n] = (p, (p[0] + 0.15, p[1] + 0.35))
for a, b in [((2.65, 4.5), (3.35, 4.5)), ((2.65, 3), (3.35, 1.6)), ((2.65, 1.5), (3.35, 1.4)), ((5.65, 4.5), (6.35, 4.0)),
             ((5.65, 3), (6.35, 3.7)), ((5.65, 1.5), (6.35, 3.5)), ((7.5, 3.3), (7.5, 2.7))]: arrow(ax, a, b)
ax.add_patch(Rectangle((0.2, 0.8), 2.6, 4.4, fill=False, ls="--", lw=0.8)); ax.add_patch(Rectangle((3.2, 0.8), 5.6, 4.4, fill=False, ls="--", lw=0.8))
ax.text(1.5, 5.35, "塔上感知层", ha="center", fontsize=9); ax.text(6, 5.35, "反演与预警平台", ha="center", fontsize=9)
L[209] = "塔上感知层"; L[210] = "反演与预警平台"; LD[209] = ((0.2, 4), (-0.4, 5.3)); LD[210] = ((8.8, 4), (9.1, 5.3))
ax.set_xlim(-0.5, 9.4); ax.set_ylim(0.5, 5.7); save(fig, ax, 2, "系统框图", L, LD)

def tower(ax, x0=0, s=1.0):
    hs = [0, 10, 20, 30, 40, 48]; ws = [8, 6, 4.4, 3.2, 2.4, 2.0]
    for h, w in zip(hs, ws): ax.plot([x0 - w / 2 * s, x0 + w / 2 * s], [h * s, h * s], "k", lw=0.8)
    for i in range(len(hs) - 1):
        a, b = ws[i] / 2 * s, ws[i + 1] / 2 * s; y0, y1 = hs[i] * s, hs[i + 1] * s
        ax.plot([x0 - a, x0 - b], [y0, y1], "k", lw=1.6); ax.plot([x0 + a, x0 + b], [y0, y1], "k", lw=1.6)
        ax.plot([x0 - a, x0 + b], [y0, y1], "k", lw=0.5); ax.plot([x0 + a, x0 - b], [y0, y1], "k", lw=0.5)
    ax.plot([x0 - 9 * s, x0 + 9 * s], [42 * s, 42 * s], "k", lw=1.2); ax.plot([x0 - 6 * s, x0 + 6 * s], [48 * s, 48 * s], "k", lw=1.0)

# 图3 影响矩阵
fig, ax = canvas(10, 6)
tower(ax, 0, 0.1)
for dx in (-0.4, 0.4): ax.annotate("", xy=(dx, -0.6), xytext=(dx, 0), arrowprops=dict(arrowstyle="->"))
ax.text(0, -1.0, "单位工况 δ_k=1", ha="center", fontsize=9)
arrow(ax, (1.2, 2.5), (2.5, 2.5))
ax.add_patch(Rectangle((2.8, 0.5), 3, 4, fill=False))
for i in range(1, 6): ax.plot([2.8, 5.8], [0.5 + i * 4 / 6] * 2, "k", lw=0.3)
for j in range(1, 6): ax.plot([2.8 + j * 0.5] * 2, [0.5, 4.5], "k", lw=0.3)
ax.text(4.3, 4.8, "影响矩阵 G（散射体LOS × 工况）", ha="center", fontsize=9)
arrow(ax, (6, 2.5), (7, 2.5)); ax.text(8.3, 2.5, "d_LOS = G·u + T·ΔT + ε", ha="center", fontsize=10)
L = {301: "杆件级桁架有限元模型", 302: "塔腿单位位移工况", 303: "影响矩阵", 304: "影响矩阵行（对应散射体）", 305: "观测方程"}
LD = {301: ((0.3, 3.5), (1.0, 4.8)), 302: ((0.4, -0.5), (1.0, -1.2)), 303: ((5.8, 4), (6.3, 4.6)), 304: ((4.0, 3.2), (6.3, 3.6)), 305: ((8.3, 2.7), (8.6, 3.4))}
ax.set_xlim(-1.5, 10); ax.set_ylim(-1.5, 5.5); save(fig, ax, 3, "影响矩阵构建示意图", L, LD)

# 图4 日照遮挡热场
fig, ax = canvas(8, 6)
tower(ax, 0, 0.1)
for k in range(5): ax.annotate("", xy=(-0.6 + k * 0.3, 2 + k * 0.5), xytext=(-3.5 + k * 0.3, 4.5 + k * 0.5), arrowprops=dict(arrowstyle="->", lw=0.7))
ax.add_patch(Circle((-4, 5.6), 0.35, fill=False))
ax.plot([2.5, 4.0], [1, 1], "k", lw=4); ax.plot([2.5, 2.5], [1, 2.5], "k", lw=4)
for x in np.linspace(2.6, 3.9, 6): ax.plot([x, x + 0.15], [1.15, 1.35], "k", lw=0.5)
L = {401: "太阳", 402: "太阳光线方向", 403: "塔身（LoD3模型）", 404: "角钢受照面（阳面）", 405: "角钢背阴面（阴面）", 406: "被遮挡阴影区杆件"}
LD = {401: ((-4, 5.6), (-4.8, 5.9)), 402: ((-2.5, 4.5), (-3.2, 3.6)), 403: ((0.3, 4.5), (1.0, 5.2)), 404: ((3.3, 1.3), (4.3, 1.9)), 405: ((3.3, 0.9), (4.3, 0.4)), 406: ((0.2, 2.0), (1.3, 2.8))}
ax.set_xlim(-5, 5); ax.set_ylim(-0.5, 6.5); save(fig, ax, 4, "日照遮挡热场示意图", L, LD)

# 图5/6 由 FreeCAD 模型边投影（轴测）
def proj(p, az=-45, el=30):
    a, e = math.radians(az), math.radians(el); x, y, z = p
    u = x * math.cos(a) - y * math.sin(a); v = -(x * math.sin(a) + y * math.cos(a)) * math.sin(e) + z * math.cos(e)
    return u, v

def draw(ax, names, off={}):
    pos = {}
    for n in names:
        o = E[n]; dx = off.get(n, (0, 0, 0)); xs = []
        for ed in o["edges"]:
            P = [proj((p[0] + dx[0], p[1] + dx[1], p[2] + dx[2])) for p in ed]
            ax.plot([q[0] for q in P], [q[1] for q in P], "k", lw=0.5); xs += P
        pos[o["num"]] = xs[len(xs) // 3] if xs else (0, 0)
    return pos

names = list(E.keys())
lab = {E[n]["num"]: E[n]["label"] for n in names}
lab[10] = "升轨朝向三面角反射器"; lab[11] = "降轨朝向三面角反射器"
fig, ax = canvas(9, 9); pos = draw(ax, names)
save(fig, ax, 5, "塔材夹持式双向三面角反射器轴测图", {k: lab[k] for k in pos}, {k: (v, (v[0] + 150, v[1] + 120)) for k, v in pos.items()})
offm = {1: (0, 0, 0), 5: (150, 150, 0), 3: (300, 300, 0), 4: (450, 450, 0), 2: (-150, -150, 0), 6: (-350, -350, 0),
        7: (-450, -450, 250), 8: (-200, -200, 300), 9: (-500, -500, 450), 12: (-500, -500, 600)}
off = {n: offm.get(E[n]["num"], (-550, -550, 800)) for n in names}
fig, ax = canvas(10, 10); pos = draw(ax, names, off)
save(fig, ax, 6, "爆炸图", {k: lab[k] for k in pos}, {k: (v, (v[0] + 150, v[1] + 100)) for k, v in pos.items()})

# 图7 夹持剖视（Z=600 水平截面）
fig, ax = canvas(8, 8)
t = 10; b = 125
def hp(pts, h): ax.add_patch(Polygon(pts, closed=True, fill=False, hatch=h, ec="k", lw=1))
hp([(0, 0), (b, 0), (b, t), (t, t), (t, b), (0, b)], "xxxx")
hp([(-12, -12), (b + 10, -12), (b + 10, -2), (-2, -2), (-2, b + 10), (-12, b + 10)], "////")
hp([(-2, -2), (b, -2), (b, 0), (0, 0), (0, b), (-2, b)], "....")
hp([(t + 15, t), (b - 15, t), (b - 15, t + 12), (t + 15, t + 12)], "\\\\\\\\"); hp([(t, t + 15), (t + 12, t + 15), (t + 12, b - 15), (t, b - 15)], "\\\\\\\\")
ax.add_patch(Rectangle((b + 10, -20), 16, t + 60, fill=False, lw=1)); ax.add_patch(Rectangle((-20, b + 10), t + 60, 16, fill=False, lw=1))
ax.plot([b + 18] * 2, [-25, t + 45], "k-.", lw=0.5); ax.plot([-25, t + 45], [b + 18] * 2, "k-.", lw=0.5)
ax.plot([-12, -252], [-12, -252], "k", lw=6); ax.plot([-12, -252], [-12, -252], "w", lw=4)
ax.text(140, 150, "A–A 截面（Z=600 mm）", fontsize=9)
L7 = {1: "角钢主材", 2: "外夹块", 3: "内压板", 4: "夹紧螺栓（位于肢外缘外侧，塔材不钻孔）", 5: "防滑绝缘垫", 6: "悬臂托架", 16: "螺栓轴线"}
LD7 = {1: ((60, 5), (70, -70)), 2: ((-7, 60), (-90, 60)), 3: ((60, t + 6), (80, 60)), 4: ((b + 18, 30), (200, 40)), 5: ((-1, 30), (-90, 20)), 6: ((-150, -150), (-230, -80)), 16: ((b + 18, -22), (190, -40))}
ax.set_xlim(-280, 260); ax.set_ylim(-280, 220); save(fig, ax, 7, "夹持部位剖视图", L7, LD7)

# 图8 在塔上布置
fig, ax = canvas(9, 10)
s = 0.2; tower(ax, 0, s)
nodes = [(-4 * s, 0), (4 * s, 0), (-3 * s, 10 * s), (3 * s, 10 * s), (-2.2 * s, 20 * s), (2.2 * s, 20 * s), (-1.6 * s, 30 * s), (1.6 * s, 30 * s), (-1.0 * s, 48 * s)]
used = [(-3 * s, 10 * s), (3 * s, 10 * s), (-2.2 * s, 20 * s), (-1.0 * s, 48 * s)]
for x, y in nodes: ax.plot(x, y, "ko", ms=3, mfc="w")
for x, y in used: ax.add_patch(Polygon([(x, y), (x - 0.35, y + 0.25), (x - 0.35, y - 0.25)], fill=False, lw=1))
for x in (-9 * s, 9 * s):
    ax.add_patch(Circle((x, 38 * s), 5 * s, fill=False, ls="--", lw=0.7)); ax.plot([x, x], [42 * s, 38 * s], "k", lw=0.8)
ax.plot([-3, 3], [0, 0], "k", lw=1.2)
for x in np.linspace(-3, 3, 25): ax.plot([x, x - 0.15], [0, -0.15], "k", lw=0.4)
L8 = {801: "输电塔", 802: "有限元节点", 803: "按D最优选定节点处的夹持式角反射器", 804: "导线挂点（带电体）", 805: "带电安全距离包络（500 kV 不小于5.0 m）", 806: "塔腿基础", 807: "地线支架处角反射器"}
LD8 = {801: ((0.6, 6), (2.5, 7)), 802: ((4 * s, 0), (1.8, 0.8)), 803: ((3 * s, 10 * s), (2.0, 2.8)), 804: ((9 * s, 7.6), (2.6, 8.8)), 805: ((-9 * s - 1, 7.6), (-3.5, 9.5)), 806: ((-4 * s, 0), (-2.5, -0.8)), 807: ((-1.0 * s, 48 * s), (-1.8, 10.6))}
ax.set_xlim(-4, 4); ax.set_ylim(-1.2, 11); save(fig, ax, 8, "角反射器按有限元节点在塔上布置示意图", L8, LD8)

json.dump(ALL, open(os.path.join(ROOT, "附图标记.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("done")
