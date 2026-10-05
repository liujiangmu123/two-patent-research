# -*- coding: utf-8 -*-
"""锁闭阀块 55 可加工级模型（D3）。freecadcmd：sh 07_脚本/run_fc.sh d3_valve_block.py

局部坐标（mm）：X 沿缸轴（X=0 为有杆腔端/前端，朝卡盘），Y 由前面(Y=0)向后，Z 向上，Z=0 为与缸体结合的底面。
装到出图模型：局部原点 → 全局 (1370, 455, 1125)，与缸筒 66 两腔油口 X=1390/1590 对应局部 X=20/220。
外形 240×90×75，45 钢调质 HB220~250、发黑；或 6061-T6（压力 ≤7 MPa 可用）。
输出：04_模型/锁闭阀块_详细.FCStd、锁闭阀块_详细.step
"""
import os
import FreeCAD as App
import Part

V = App.Vector
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
L, W, H = 240.0, 90.0, 75.0
YC = 45.0                 # 主油道/插装孔所在 Y
ZG = 20.0                 # 两腔水平主油道高度
D_GAL = 6.0               # 主油道直径（c04 取孔径 6 mm）
D_PORT = 8.0              # 缸体结合面油口
# Sun T-162A 两通腔（规格依据：BOM/说明书 DTDA-MCN-224 → T-162A；以下尺寸为公开资料近似值，待按 Sun 腔体图核实）
CAV = dict(thread="3/4-16 UNF-2B", d1=19.05, h1=14.0,   # 螺纹段（建模取大径）
           d2=17.48, h2=24.0,                             # 侧口(2口)台阶段
           d3=12.70, h3=33.3,                             # 鼻端(1口)
           port2_z=H - 19.0)                              # 侧口中心高
CAVITY_SPEC = {"腔型": "Sun T-162A（两通，1口鼻端、2口侧面）",
               "螺纹": CAV["thread"], "台阶直径_mm": [CAV["d1"], CAV["d2"], CAV["d3"]],
               "台阶深度_mm": [CAV["h1"], CAV["h2"], CAV["h3"]],
               "依据": "BOM 19/20/21/23 选 Sun DTDA-MCN-224，样本标 T-162A 腔",
               "状态": "尺寸为公开资料近似值（官方腔体图网页 403 未取到），下单前须按 Sun 腔体图 T-162A 及成形刀具核对；"
                       "安装方向（鼻端接缸腔、侧口接外部）须核对 DTDA 的密封方向"}
VALVES = {"V2(20)": 55.0, "V4(23)": 95.0, "V3(21)": 145.0, "V1(19)": 185.0}
G14 = 13.157              # G1/4 大径
BOLTS = [(30, 12), (30, 78), (210, 12), (210, 78)]   # 4×M8 内六角，沉孔


def cz(r, z0, z1, x, y=YC):
    return Part.makeCylinder(r, z1 - z0, V(x, y, z0), V(0, 0, 1))


def cx(r, x0, x1, y=YC, z=ZG):
    return Part.makeCylinder(r, x1 - x0, V(x0, y, z), V(1, 0, 0))


def cy(r, y0, y1, x, z):
    return Part.makeCylinder(r, y1 - y0, V(x, y0, z), V(0, 1, 0))


def cavity(x):
    s = cz(CAV["d1"] / 2, H - CAV["h1"], H + 0.01, x)
    s = s.fuse(cz(CAV["d2"] / 2, H - CAV["h2"], H - CAV["h1"] + 0.01, x))
    s = s.fuse(cz(CAV["d3"] / 2, H - CAV["h3"], H - CAV["h2"] + 0.01, x))
    s = s.fuse(Part.makeCone(CAV["d3"] / 2, 0.1, CAV["d3"] / 2 * 0.577, V(x, YC, H - CAV["h3"]), V(0, 0, -1)))
    return s


def tap(r_major, depth, start, axis, drill_r=None, drill_extra=0):
    """螺纹孔（按大径建模，偏保守），返回实体。axis: 'x+','x-','y+','y-','z-'。"""
    x, y, z = start
    d = {"x+": V(1, 0, 0), "x-": V(-1, 0, 0), "y+": V(0, 1, 0), "y-": V(0, -1, 0), "z-": V(0, 0, -1)}[axis]
    s = Part.makeCylinder(r_major, depth + 0.01, V(x, y, z) - d * 0.01, d)
    return s


def build():
    nets = {}
    # 有杆腔网络 R：缸口 Ø8(X=20) → 主油道 Ø6(Z=20, X0~98) → V2/V4 鼻端；左端面 S3 G1/4；前面测压口 MP1；顶面工艺堵/排气 PL1
    nets["有杆腔"] = [cz(D_PORT / 2, -0.01, ZG, 20), cx(D_GAL / 2, 0, 98),
                   cz(D_GAL / 2, ZG, H - CAV["h3"] + 0.5, 55), cz(D_GAL / 2, ZG, H - CAV["h3"] + 0.5, 95),
                   tap(G14 / 2, 14, (0, YC, ZG), "x+"),                      # S3 传感器口 G1/4
                   tap(5.0, 12, (75, 0, ZG), "y+"), cy(2.5, 0, YC, 75, ZG),   # MP1 测压口 M10×1 + Ø5
                   cz(2.0, ZG, H, 75), tap(4.0, 10, (75, YC, H), "z-")]       # PL1 排气/工艺堵 M8×1
    # 无杆腔网络 C：缸口 Ø8(X=220) → 主油道 Ø6(X120~240) → V3/V1 鼻端；右端面 S2；前面 T1(M10) 与 MP2；顶面 PL2
    nets["无杆腔"] = [cz(D_PORT / 2, -0.01, ZG, 220), cx(D_GAL / 2, 120, L),
                   cz(D_GAL / 2, ZG, H - CAV["h3"] + 0.5, 145), cz(D_GAL / 2, ZG, H - CAV["h3"] + 0.5, 185),
                   tap(G14 / 2, 14, (L, YC, ZG), "x-"),                      # S2
                   tap(5.0, 14, (125, 0, ZG), "y+"), cy(4.25, 0, YC - 2.5, 125, ZG),   # T1 M10 插入孔（直通油道）
                   tap(5.0, 12, (165, 0, ZG), "y+"), cy(2.5, 0, YC, 165, ZG),          # MP2
                   cz(2.0, ZG, H, 165), tap(4.0, 10, (165, YC, H), "z-")]              # PL2
    for name, x in VALVES.items():
        nets["腔" + name] = [cavity(x)]
    zp = CAV["port2_z"]
    for net, x in (("B口", 55.0), ("Ppre口", 95.0), ("T口", 145.0), ("A口", 185.0)):
        nets[net] = [tap(G14 / 2, 14, (x, W, zp), "y-"), cy(D_GAL / 2, YC, W - 13.9, x, zp)]
    # 阻尼孔 22 安装座：T 口通道内 M6 阻尼塞螺纹段（方案乙）
    nets["T口"].append(cy(3.0, W - 22, W - 13.9, 145.0, zp))
    nets["螺栓孔"] = []
    for (x, y) in BOLTS:
        nets["螺栓孔"] += [cz(4.5, -0.01, H + 0.01, x, y), cz(7.0, H - 9, H + 0.01, x, y)]
    # 底面 O 形圈端面密封槽（两腔油口）：O 形圈 14×2.65（GB/T 3452.1），槽 ID14 OD21.2 深 2.0
    grooves = []
    for x in (20.0, 220.0):
        grooves.append(cz(10.6, -0.01, 2.0, x).cut(cz(7.0, -0.1, 2.1, x)))
    nets["O形圈槽"] = grooves
    # 定位销孔 2×Ø6H7 深 10（底面，对角）
    nets["销孔"] = [cz(3.0, -0.01, 10, 8, 8), cz(3.0, -0.01, 10, L - 8, W - 8)]
    blk = Part.makeBox(L, W, H)
    for ss in nets.values():
        for s in ss:
            blk = blk.cut(s)
    # 外棱倒角 C1
    try:
        blk = blk.makeChamfer(1.0, [e for e in blk.Edges if e.Length >= 70 and isinstance(e.Curve, Part.Line)])
    except Exception:  # noqa: BLE001
        pass
    return blk.removeSplitter(), nets


CONNECTED = {frozenset(p) for p in [("有杆腔", "腔V2(20)"), ("有杆腔", "腔V4(23)"), ("无杆腔", "腔V3(21)"),
                                    ("无杆腔", "腔V1(19)"), ("B口", "腔V2(20)"), ("Ppre口", "腔V4(23)"),
                                    ("T口", "腔V3(21)"), ("A口", "腔V1(19)")]}


def main():
    blk, nets = build()
    doc = App.newDocument("ValveBlock55")
    o = doc.addObject("Part::Feature", "LockValveBlock55")
    o.Shape = blk
    o.Label = "55_锁闭阀块_详细"
    for p, v in (("PartNo", "55"), ("Material", "45 钢调质 HB220~250，发黑"), ("Mount", "局部原点→全局(1370,455,1125)")):
        o.addProperty("App::PropertyString", p, "Patent")
        setattr(o, p, v)
    g = doc.addObject("App::DocumentObjectGroup", "Oil_nets")
    g.Label = "孔系（检查用，隐藏）"
    for n, ss in nets.items():
        s = ss[0]
        for t in ss[1:]:
            s = s.fuse(t)
        f = doc.addObject("Part::Feature", "N_%d" % len(g.Group))
        f.Shape = s
        f.Label = "孔系_" + n
        g.addObject(f)
    doc.recompute()
    fc = os.path.join(ROOT, "04_模型", "锁闭阀块_详细.FCStd")
    doc.saveAs(fc)
    Part.export([o], os.path.join(ROOT, "04_模型", "锁闭阀块_详细.step"))
    print("VB_DONE valid=%s vol=%.0f mass45=%.2f kg" % (blk.isValid(), blk.Volume, blk.Volume * 7.85e-6))
    App.closeDocument(doc.Name)


if not globals().get("BUILD_ONLY"):
    main()
