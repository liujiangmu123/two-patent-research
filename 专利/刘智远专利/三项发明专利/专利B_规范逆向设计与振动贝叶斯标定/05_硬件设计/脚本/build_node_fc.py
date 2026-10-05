# -*- coding: utf-8 -*-
"""专利B 硬件：角钢夹持式无线三轴振动采集节点 + 塔基边缘网关 三维建模（freecadcmd 无界面运行）。

运行：freecadcmd.exe build_node_fc.py
输出：../模型/*.FCStd、*.step、构建记录.json；../预览/_proj.json（各视图投影线，供出图脚本使用）
单位 mm。坐标：角钢轴线沿 Z，肢背外角点在原点，两肢沿 +X、+Y；节点位于外侧象限（x<0,y<0）。
"""
import os, json, math, sys, time
import FreeCAD as App
import Part, TechDraw
from FreeCAD import Vector as V, Placement, Rotation

HERE = os.path.dirname(os.path.abspath(__file__))
HW = os.path.dirname(HERE)
MOD = os.path.join(HW, "模型"); PRE = os.path.join(HW, "预览")
os.makedirs(MOD, exist_ok=True); os.makedirs(PRE, exist_ok=True)

ANG = dict(b=100.0, t=8.0)          # 建模示例角钢 L100x8（适配 L40–L250，更换拉杆）
B, T = ANG["b"], ANG["t"]
L_ANG = 420.0

def box(x0, x1, y0, y1, z0, z1):
    return Part.makeBox(x1 - x0, y1 - y0, z1 - z0, V(x0, y0, z0))

def cylZ(cx, cy, r, z0, z1):
    return Part.makeCylinder(r, z1 - z0, V(cx, cy, z0), V(0, 0, 1))

def cylDir(p, d, r, h):
    return Part.makeCylinder(r, h, V(*p), V(*d))

def prism(pts, z0, z1):
    w = Part.makePolygon([V(x, y, z0) for x, y in pts] + [V(pts[0][0], pts[0][1], z0)])
    return Part.Face(w).extrude(V(0, 0, z1 - z0))

def hexZ(cx, cy, s, z0, z1):  # 对边距 s 的六角
    r = s / math.sqrt(3)
    pts = [(cx + r * math.cos(math.radians(30 + 60 * k)), cy + r * math.sin(math.radians(30 + 60 * k))) for k in range(6)]
    return prism(pts, z0, z1)

def hexX(cx, cy, cz, s, x0, x1):
    r = s / math.sqrt(3)
    pts = [V(x0, cy + r * math.cos(math.radians(60 * k)), cz + r * math.sin(math.radians(60 * k))) for k in range(6)]
    f = Part.Face(Part.makePolygon(pts + [pts[0]]))
    return f.extrude(V(x1 - x0, 0, 0))

def hexY(cx, cy, cz, s, y0, y1):
    r = s / math.sqrt(3)
    pts = [V(cx + r * math.cos(math.radians(60 * k)), y0, cz + r * math.sin(math.radians(60 * k))) for k in range(6)]
    f = Part.Face(Part.makePolygon(pts + [pts[0]]))
    return f.extrude(V(0, y1 - y0, 0))

parts = {}   # name -> (shape, label_no, 中文名, 材料, 密度 g/cm3)

def add(name, shp, no, cn, mat, rho):
    parts[name] = (shp, no, cn, mat, rho)

# ---------------- 角钢（被测构件，非本装置组成，仅示意） ----------------
angle = box(0, B, 0, T, -L_ANG / 2, L_ANG / 2).fuse(box(0, T, T, B, -L_ANG / 2, L_ANG / 2)).removeSplitter()
add("Angle", angle, 100, "角钢主材（被测构件）", "Q345", 7.85)

# ---------------- 1x 夹持机构 ----------------
HZ = 55.0     # V 形夹块半高
# V 形夹块：90° 内夹角，两内侧面分别贴合两肢外表面，肢背处设根部让位槽
vb_pts = [(78, -2), (78, -18), (-18, -18), (-18, 78), (-2, 78), (-2, 6), (-6, 6), (-6, -6), (6, -6), (6, -2)]
vblock = prism(vb_pts, -HZ, HZ)
# 两翼下垂拉杆耳座
lug1 = box(62, 78, -34, -18, -12, 12)
lug2 = box(-34, -18, 62, 78, -12, 12)
# 外侧安装凸台（沿肢夹角平分线 n=-(1,1)/√2）
n = V(-1, -1, 0); n.normalize()
boss = cylDir((-18 + 8, -18 + 8, 0), (-1, -1, 0), 20, 25.5)  # 起点在夹块背面内
# 防坠绳孔耳板（顶部）
lan = box(-18, 10, -18, 10, HZ, HZ + 14).cut(cylDir((-18, -4, HZ + 7), (1, 0, 0), 4.5, 30)) \
    .cut(cylDir((-4, -18, HZ + 7), (0, 1, 0), 4.5, 30))
vblock = vblock.fuse([lug1, lug2, boss, lan]).removeSplitter()
vblock = vblock.cut(cylDir((50, -26, 0), (1, 0, 0), 5.5, 40)).cut(cylDir((-26, 50, 0), (0, 1, 0), 5.5, 40))
add("VBlock", vblock, 11, "肢背V形夹块", "6061-T6铝合金(硬质阳极化)", 2.70)

pad1 = box(8, 74, -2, 0, -HZ + 5, HZ - 5)
pad2 = box(-2, 0, 8, 74, -HZ + 5, HZ - 5)
add("Pad1", pad1, 12, "绝缘摩擦垫(肢1)", "G10环氧玻纤", 1.85)
add("Pad2", pad2, 12, "绝缘摩擦垫(肢2)", "G10环氧玻纤", 1.85)

# 肢1：偏心凸轮拉杆 + 钩爪；肢2：螺杆拉杆 + 钩爪 + 防松螺母
RY = -26.0
rod1 = cylDir((40, RY, 0), (1, 0, 0), 5, B + 30 - 40)
add("Rod1", rod1, 13, "拉杆(肢1，可换长度适配L40–L250)", "304不锈钢", 7.93)
hook1 = box(B + 2, B + 18, RY - 8, T + 8, -12, 12).fuse(box(B - 14, B + 18, T, T + 8, -12, 12)).removeSplitter()
hook1 = hook1.cut(cylDir((B, RY, 0), (1, 0, 0), 5.5, 30))
add("Hook1", hook1, 14, "钩爪(肢1)", "304不锈钢", 7.93)
nut1 = hexX(0, RY, 0, 16, B + 18, B + 26)
add("Nut1", nut1, 17, "调节螺母", "304不锈钢", 7.93)
# 偏心凸轮（轴线 Z，偏心 3 mm）+ 手柄
cam = cylZ(45, RY + 3, 11, -8, 8)
pin = cylZ(45, RY, 3, -14, 14)
handle = box(30, 45, RY - 40, RY - 30, -5, 5).fuse(box(30, 40, RY - 40, RY + 2, -5, 5)).removeSplitter()
add("Cam", cam.fuse([pin, handle]).removeSplitter(), 15, "偏心凸轮及手柄", "17-4PH不锈钢", 7.80)

rod2 = cylDir((RY, 30, 0), (0, 1, 0), 5, B + 30 - 30)
add("Rod2", rod2, 16, "螺杆拉杆(肢2)", "304不锈钢", 7.93)
hook2 = box(RY - 8, T + 8, B + 2, B + 18, -12, 12).fuse(box(T, T + 8, B - 14, B + 18, -12, 12)).removeSplitter()
hook2 = hook2.cut(cylDir((RY, B, 0), (0, 1, 0), 5.5, 30))
add("Hook2", hook2, 14, "钩爪(肢2)", "304不锈钢", 7.93)
nutA = hexY(RY, 0, 0, 16, 52, 61)
nutB = hexY(RY, 0, 0, 16, 45, 51)
add("Nut2", nutA, 17, "调节螺母", "304不锈钢", 7.93)
add("LockNut", nutB, 18, "防松锁紧螺母+碟簧", "304不锈钢", 7.93)
add("NutT2", hexY(RY, 0, 0, 16, B + 18, B + 26), 17, "调节螺母", "304不锈钢", 7.93)

# ---------------- 2x 采集单元（局部坐标：X'横向, Y'=n 外法向, Z 轴向），绕Z转135° ----------------
PL = Placement(V(0, 0, 0), Rotation(V(0, 0, 1), 135))
S0 = 39.0   # 壳体内表面（凸台端面）到原点沿 n 的距离
HX, HY, HZh = 62.0, 72.0, 95.0   # 半宽、深、半高
def L(shp):
    s = shp.copy(); s.Placement = PL.multiply(s.Placement); return s

shell = box(-HX, HX, S0, S0 + HY, -HZh, HZh)
shell = shell.cut(box(-HX + 3, HX - 3, S0 + 3, S0 + HY - 3, -HZh + 3, HZh - 3))
# 轴系对齐标记（壳体侧面凸起箭头：Z 沿角钢轴线，X'、n）
arrZ = prism([(HX, -10), (HX + 1.5, -10), (HX + 1.5, 10), (HX, 10)], 0, 1)  # placeholder
def arrow_on_side(z0):
    pts = [(-4, z0), (4, z0), (4, z0 + 14), (8, z0 + 14), (0, z0 + 24), (-8, z0 + 14), (-4, z0 + 14)]
    w = Part.makePolygon([V(HX, S0 + 36 + p[0], p[1]) for p in pts] + [V(HX, S0 + 36 + pts[0][0], pts[0][1])])
    return Part.Face(w).extrude(V(1.2, 0, 0))
mark = arrow_on_side(20)
mark2 = box(-HX, -HX + 40, S0 - 1.2, S0, -HZh + 6, -HZh + 10)    # 底面X'刻线（与肢夹角平分线正交）
add("Shell", shell.fuse([mark]).removeSplitter(), 21, "IP67壳体(PC/ASA，含轴系对齐标记)", "PC/ASA", 1.20)
add("AxisMark", mark2, 22, "轴系对齐刻线", "PC/ASA", 1.20)
seal = box(-HX - 1, HX + 1, S0 + HY - 6, S0 + HY - 4, -HZh - 1, HZh + 1).cut(box(-HX + 2, HX - 2, S0 + HY - 7, S0 + HY - 3, -HZh + 2, HZh - 2))
add("Seal", seal, 23, "硅橡胶密封圈", "VMQ", 1.15)
mount = box(-32, 32, S0 + 3, S0 + 18, -28, 28)
add("Mount", mount, 24, "传感器刚性安装座(穿壁螺柱直连夹块)", "6061-T6铝合金", 2.70)
stud = Part.makeCylinder(4, 30, V(0, S0 - 12, 0), V(0, 1, 0))
add("Stud", stud, 25, "M8穿壁螺柱", "304不锈钢", 7.93)
acc = box(-24, 24, S0 + 18, S0 + 34, -12, 12)
add("Acc", acc, 26, "三轴石英加速度计(M-A352)", "—", 0)
pcb = box(-56, 56, S0 + 40, S0 + 42, -85, 85)
add("PCB", pcb, 27, "主控/授时/无线电路板", "FR4", 1.85)
bat = box(-50, 50, S0 + 44, S0 + 64, -85, -20)
add("Bat", bat, 28, "低温磷酸铁锂电池组+加热膜", "—", 0)
radio = box(10, 40, S0 + 44, S0 + 52, 0, 30)
add("Radio", radio, 29, "低功耗无线模块", "—", 0)
gnssm = box(-40, -10, S0 + 44, S0 + 50, 0, 30)
add("GNSSm", gnssm, 30, "GNSS授时模块+TCXO", "—", 0)
solar = box(-HX, HX, S0 + HY, S0 + HY + 5, -HZh, HZh)
add("Solar", solar, 31, "太阳能板(钢化玻璃层压)", "—", 0)
radome = Part.makeCylinder(32, 22, V(0, S0 + HY / 2, HZh), V(0, 0, 1)).fuse(
    Part.makeSphere(32, V(0, S0 + HY / 2, HZh + 22)).common(box(-40, 40, S0 - 10, S0 + HY + 10, HZh + 22, HZh + 60))).removeSplitter()
add("Radome", radome, 32, "GNSS授时天线罩", "ASA", 1.07)
patch = box(-18, 18, S0 + HY / 2 - 18, S0 + HY / 2 + 18, HZh + 2, HZh + 6)
add("Patch", patch, 33, "GNSS陶瓷贴片天线", "—", 0)
whip = Part.makeCylinder(6, 90, V(35, S0 + HY / 2, -HZh - 90), V(0, 0, 1))
add("Whip", whip, 34, "无线天线(玻璃钢)", "FRP", 1.9)
gland = Part.makeCylinder(7, 10, V(-30, S0 + HY / 2, -HZh - 10), V(0, 0, 1))
add("Vent", gland, 35, "防水透气阀", "PA66+ePTFE", 1.2)

LOCAL = {"Shell", "AxisMark", "Seal", "Mount", "Stud", "Acc", "PCB", "Bat", "Radio", "GNSSm", "Solar", "Radome", "Patch", "Whip", "Vent"}
for k in list(parts):
    if k in LOCAL:
        s, *rest = parts[k]
        parts[k] = (L(s), *rest)

# 实际质量覆写（器件按规格书/估算，g）
MASS_OVR = {"Acc": 25.0, "PCB": 45.0, "Bat": 330.0, "Radio": 8.0, "GNSSm": 12.0, "Solar": 210.0, "Patch": 18.0, "Shell": None}

# ---------------- 文档、导出 ----------------
doc = App.newDocument("PatentB_Node")
objs = {}
rec = {"time": time.strftime("%Y-%m-%d %H:%M:%S"), "freecad": App.Version()[:3], "angle_example": "L100x8",
       "parts": []}
total = 0.0
for k, (s, no, cn, mat, rho) in parts.items():
    o = doc.addObject("Part::Feature", k); o.Shape = s; o.Label = f"{no}_{cn}"
    objs[k] = o
    m = MASS_OVR.get(k)
    if m is None:
        m = s.Volume / 1000.0 * rho
    if k != "Angle":
        total += m
    bb = s.BoundBox
    rec["parts"].append(dict(name=k, no=no, cn=cn, mat=mat, volume_mm3=round(s.Volume, 1), mass_g=round(m, 1),
                             bbox=[round(bb.XLength, 1), round(bb.YLength, 1), round(bb.ZLength, 1)], valid=s.isValid()))
node_parts = [k for k in parts if k != "Angle"]
cmp_node = Part.makeCompound([parts[k][0] for k in node_parts])
bb = cmp_node.BoundBox
rec["node_mass_g_excl_fasteners"] = round(total, 1)
rec["node_bbox_mm"] = [round(bb.XLength, 1), round(bb.YLength, 1), round(bb.ZLength, 1)]
# 质心（用于共振估算）
mx = V(0, 0, 0); mt = 0
for r_, k in zip(rec["parts"], parts):
    if k == "Angle": continue
    c = parts[k][0].BoundBox.Center if parts[k][0].Volume < 1 else parts[k][0].CenterOfMass if hasattr(parts[k][0], "CenterOfMass") else parts[k][0].BoundBox.Center
    try:
        c = parts[k][0].Solids[0].CenterOfMass if len(parts[k][0].Solids) == 1 else parts[k][0].BoundBox.Center
    except Exception:
        c = parts[k][0].BoundBox.Center
    mx += c * r_["mass_g"]; mt += r_["mass_g"]
cg = mx * (1.0 / mt)
rec["node_cg_mm"] = [round(cg.x, 1), round(cg.y, 1), round(cg.z, 1)]
rec["cg_offset_along_n_mm"] = round(-(cg.x + cg.y) / math.sqrt(2), 1)
doc.recompute()
doc.saveAs(os.path.join(MOD, "专利B_角钢夹持振动节点.FCStd"))
Part.export([objs[k] for k in node_parts], os.path.join(MOD, "专利B_角钢夹持振动节点.step"))
Part.export(list(objs.values()), os.path.join(MOD, "专利B_角钢夹持振动节点_含角钢.step"))

# ---------------- 塔基边缘网关 ----------------
gdoc = App.newDocument("PatentB_Gateway")
g = {}
GW, GD, GH = 400.0, 200.0, 500.0
# 塔腿主材（L160x14，示意）+ 抱箍底板夹在塔腿角钢上，箱体离地 ≥ 0.8 m
legA = box(0, 160, 0, 14, 0, 1600).fuse(box(0, 14, 14, 160, 0, 1600)).removeSplitter()
g["Leg"] = (legA, 101, "塔腿主材（示意）")
brk = box(-12, 0, -12, 160, 700, 1500).fuse(box(-12, 160, -12, 0, 700, 1500)).removeSplitter()
g["Bracket"] = (brk, 41, "角钢夹持安装支架")
P2 = Placement(V(-12, -12, 0), Rotation(V(0, 0, 1), 135))
def L2(s):
    s = s.copy(); s.Placement = P2.multiply(s.Placement); return s
cab = box(-GW / 2, GW / 2, 10, 10 + GD, 800, 800 + GH)
g["Cabinet"] = (L2(cab), 42, "IP66不锈钢网关箱体")
door = box(-GW / 2 + 15, GW / 2 - 15, 10 + GD, 14 + GD, 815, 785 + GH)
g["Door"] = (L2(door), 43, "箱门（带锁、遮阳罩）")
hood = box(-GW / 2 - 20, GW / 2 + 20, 0, GD + 40, 800 + GH, 812 + GH)
g["Hood"] = (L2(hood), 44, "遮阳顶罩")
pv = box(-350, 350, 0, 10, 0, 520)
pv.rotate(V(0, 0, 0), V(1, 0, 0), -40)
pv.translate(V(0, 30, 1330))
g["PV"] = (L2(pv), 45, "太阳能板(60 W)")
ant1 = Part.makeCylinder(8, 260, V(-120, GD - 40, 1312), V(0, 0, 1))
g["Ant4G"] = (L2(ant1), 46, "4G/5G天线")
ant2 = Part.makeCylinder(10, 200, V(120, GD - 40, 1312), V(0, 0, 1))
g["AntRF"] = (L2(ant2), 47, "节点无线汇聚天线")
gn = Part.makeCylinder(40, 30, V(0, 60, 1312), V(0, 0, 1))
g["AntGNSS"] = (L2(gn), 48, "GNSS授时天线")
gobjs = {}
grec = []
for k, (s, no, cn) in g.items():
    o = gdoc.addObject("Part::Feature", k); o.Shape = s; o.Label = f"{no}_{cn}"; gobjs[k] = o
    grec.append(dict(name=k, no=no, cn=cn, bbox=[round(s.BoundBox.XLength, 1), round(s.BoundBox.YLength, 1), round(s.BoundBox.ZLength, 1)], valid=s.isValid()))
gdoc.recompute()
gdoc.saveAs(os.path.join(MOD, "专利B_塔基边缘网关.FCStd"))
Part.export(list(gobjs.values()), os.path.join(MOD, "专利B_塔基边缘网关.step"))
rec["gateway_parts"] = grec
rec["gateway_cabinet_mm"] = [GW, GD, GH]

# ---------------- 投影 ----------------
def proj_edges(shape, d, groups=(0, 1, 3)):
    r = TechDraw.projectEx(shape, d)
    lines = []
    for gi in groups:
        s = r[gi]
        if s is None or s.isNull(): continue
        for e in s.Edges:
            try:
                pts = e.discretize(Deflection=0.15)
            except Exception:
                continue
            lines.append([[round(p.x, 2), round(p.y, 2)] for p in pts])
    return lines

def proj_point(p, d):
    s = Part.makeBox(0.6, 0.6, 0.6, V(p.x - 0.3, p.y - 0.3, p.z - 0.3))
    r = TechDraw.projectEx(s, d)
    xs, ys = [], []
    for gi in range(len(r)):
        if r[gi] is None or r[gi].isNull(): continue
        bb = r[gi].BoundBox
        xs += [bb.XMin, bb.XMax]; ys += [bb.YMin, bb.YMax]
    return [round((min(xs) + max(xs)) / 2, 2), round((min(ys) + max(ys)) / 2, 2)]

def anchor_pt(s):
    """部件可见锚点：取包围盒中心向外侧（-n 与 +Z）偏移后最接近的表面点。"""
    c = s.BoundBox.Center
    try:
        v = s.Vertexes
        best = min(v, key=lambda q: (q.Point - (c + V(-30, -30, 15))).Length)
        return (best.Point + c) * 0.5 if s.Volume > 0 else c
    except Exception:
        return c

VIEWS = {}
D_ISO = V(-1.0, -0.55, 0.6)
# 图1 节点整体轴测（夹在角钢上）
names1 = list(parts)
cmp1 = Part.makeCompound([parts[k][0] for k in names1])
VIEWS["fig1_iso"] = dict(lines=proj_edges(cmp1, D_ISO),
                         anchors={k: proj_point(anchor_pt(parts[k][0]), D_ISO) for k in names1})
# 图2 爆炸图：沿 n 方向分层展开
EXP = {"Angle": 0, "Pad1": -0, "Pad2": 0, "VBlock": 60, "Rod1": 60, "Rod2": 60, "Hook1": 60, "Hook2": 60, "Cam": 60,
       "Nut1": 60, "Nut2": 60, "LockNut": 60, "NutT2": 60, "Stud": 140, "AxisMark": 200, "Shell": 200, "Mount": 260, "Acc": 320,
       "PCB": 380, "Radio": 430, "GNSSm": 430, "Bat": 480, "Seal": 540, "Solar": 600, "Radome": 200, "Patch": 200,
       "Whip": 200, "Vent": 200}
EXPZ = {"Radome": 120, "Patch": 70, "Whip": -90, "Vent": -60, "Pad1": 0, "Pad2": 0}
exp_sh = {}
for k in names1:
    s = parts[k][0].copy()
    off = n * EXP.get(k, 0) + V(0, 0, EXPZ.get(k, 0))
    if k in ("Pad1", "Pad2"):
        off = n * 30
    s.translate(off); exp_sh[k] = s
D_EXP = V(-1.0, 0.25, 0.45)
cmp2 = Part.makeCompound(list(exp_sh.values()))
VIEWS["fig2_exploded"] = dict(lines=proj_edges(cmp2, D_EXP),
                              anchors={k: proj_point(anchor_pt(exp_sh[k]), D_EXP) for k in names1})
# 图3 夹持机构剖视：z=0 平面剖切，俯视（沿 -Z 看），剖面填充多边形
cut_keep = box(-400, 400, -400, 400, -400, 0.0)
sec_polys = {}; below = {}
for k in names1:
    s = parts[k][0]
    try:
        lo = s.common(cut_keep)
        if lo.Volume > 1e-3: below[k] = lo
        ws = s.slice(V(0, 0, 1), 0.0)
        polys = []
        for w in ws:
            pts = w.discretize(Deflection=0.1)
            polys.append([[round(p.x, 2), round(p.y, 2)] for p in pts])
        if polys: sec_polys[k] = polys
    except Exception as ex:
        pass
D_TOP = V(0, 0, 1)
cmp3 = Part.makeCompound(list(below.values()))
VIEWS["fig3_section"] = dict(lines=proj_edges(cmp3, D_TOP),
                             sections=sec_polys,
                             ref=[proj_point(V(0, 0, 0), D_TOP), proj_point(V(100, 0, 0), D_TOP), proj_point(V(0, 100, 0), D_TOP)],
                             anchors={k: proj_point(below[k].BoundBox.Center if k in below else parts[k][0].BoundBox.Center, D_TOP) for k in below})
# 网关轴测
D_G = V(-1.0, -0.35, 0.55)
gnames = list(g)
cmpg = Part.makeCompound([g[k][0] for k in gnames])
VIEWS["fig8_gateway"] = dict(lines=proj_edges(cmpg, D_G),
                             anchors={k: proj_point(anchor_pt(g[k][0]), D_G) for k in gnames})
meta = {k: dict(no=v[1], cn=v[2]) for k, v in parts.items()}
meta.update({k: dict(no=v[1], cn=v[2]) for k, v in g.items()})
with open(os.path.join(PRE, "_proj.json"), "w", encoding="utf-8") as f:
    json.dump(dict(views=VIEWS, meta=meta), f, ensure_ascii=False)
with open(os.path.join(MOD, "构建记录.json"), "w", encoding="utf-8") as f:
    json.dump(rec, f, ensure_ascii=False, indent=1)
print("DONE", rec["node_mass_g_excl_fasteners"], rec["node_bbox_mm"], rec["node_cg_mm"])
