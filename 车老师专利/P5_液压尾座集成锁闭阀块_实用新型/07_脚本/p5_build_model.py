# -*- coding: utf-8 -*-
r"""P5 集成锁闭阀块 + 尾座油缸 出图/校核模型生成（freecadcmd 无头运行）。

在 P1 的 d3_valve_block.py（锁闭阀块 55，240×90×75，Sun T-162A 腔近似）基础上细化：
  阀孔改为 ISO 7789-22-01-0-98（M22×1.5）两通插装孔，安全阀孔为 ISO 7789-20-02-0-98；
  锁闭座阀阀孔与缸腔对接油口同轴，二者之间为直通主孔道；两腔锁闭油道自阀块端面钻入，入口分别为测压孔和套管安装孔；
  增加油温传感器套管、测压排气孔、可更换阻尼孔螺塞、端面密封槽、定位销与连接螺栓；缸体两腔油口改在端盖内。
全部尺寸读 00_设计基准/P5_设计基准.json。

用法：powershell -File 07_脚本\run_fc.ps1 p5_build_model.py
输出：04_模型/P5_出图模型.FCStd（全部零件 + 隐藏的孔系网络）
      04_模型/集成锁闭阀块.step（阀块本体与装在其上的元件）
      04_模型/尾座油缸与集成锁闭阀块_装配.step（含缸体）
      04_模型/_build_report.json（体积、质量、零件清单）
"""
import json
import math
import os
import time

import FreeCAD as App
import Part

V = App.Vector
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
B = json.load(open(os.path.join(ROOT, "00_设计基准", "P5_设计基准.json"), encoding="utf-8"))
OUTDIR = os.path.join(ROOT, "04_模型")
CY = B["尾座油缸"]
BK = B["阀块本体"]
L, W, H = BK["外形_LxWxH"]
YC = 45.0                       # 阀孔、锁闭油道所在 Y
ZA = -45.0                      # 缸轴线 Z
ZG = float(BK["锁闭油道高度ZG"])
E = 0.01                        # 布尔重叠量
G14, G38, M16 = 13.157, 16.662, 16.0


# ------------------------------------------------------------------ 基本体
def cz(d, z0, z1, x, y=YC):
    return Part.makeCylinder(d / 2.0, z1 - z0, V(x, y, z0), V(0, 0, 1))


def cx(d, x0, x1, y=YC, z=ZG):
    return Part.makeCylinder(d / 2.0, x1 - x0, V(x0, y, z), V(1, 0, 0))


def cy(d, y0, y1, x, z):
    return Part.makeCylinder(d / 2.0, y1 - y0, V(x, y0, z), V(0, 1, 0))


def box(x0, x1, y0, y1, z0, z1):
    return Part.makeBox(x1 - x0, y1 - y0, z1 - z0, V(x0, y0, z0))


def cone(r0, r1, p, d, h):
    return Part.makeCone(r0, r1, h, p, d)


def tip(d, p, direction):
    """118° 钻尖：底面直径 d，位于 p，尖端沿 direction。"""
    h = d / 2.0 / math.tan(math.radians(59))
    return Part.makeCone(d / 2.0, 0.0, h, p, direction)


def hexprism(af, p, d, h):
    """对边 af 的六棱柱，底面中心 p，轴向 d（单位向量），高 h。"""
    r = af / math.sqrt(3)
    d = V(d)
    d.normalize()
    a = V(1, 0, 0) if abs(d.x) < 0.9 else V(0, 1, 0)
    u = a.cross(d)
    u.normalize()
    v = d.cross(u)
    pts = [p + u * (r * math.cos(math.radians(60 * i + 30))) + v * (r * math.sin(math.radians(60 * i + 30))) for i in range(6)]
    w = Part.makePolygon(pts + [pts[0]])
    return Part.Face(w).extrude(d * h)


def fuse(*ss):
    s = ss[0]
    for t in ss[1:]:
        s = s.fuse(t)
    return s.removeSplitter()


def revolve_profile(pts, axis_p, axis_d):
    """在含轴线的平面内给出 (r, t) 折线（t 沿轴向），绕轴旋转成实体。"""
    axis_d = V(axis_d)
    axis_d.normalize()
    a = V(1, 0, 0) if abs(axis_d.x) < 0.9 else V(0, 1, 0)
    u = a.cross(axis_d)
    u.normalize()
    P3 = [axis_p + axis_d * t + u * r for r, t in pts]
    w = Part.makePolygon(P3 + [P3[0]])
    return Part.Face(w).revolve(axis_p, axis_d, 360)


# ------------------------------------------------------------------ 插装孔（自顶面向下）
def cavity_22(x):
    zt = H
    s = cz(22.0, zt - 17.0, zt + E, x)                                       # 螺纹段 M22×1.5（按大径）
    s = s.fuse(cz(20.4, zt - 28.0, zt - 17.0 + E, x))                         # 第二阀口段
    s = s.fuse(cone(10.2, 9.5, V(x, YC, zt - 28.0), V(0, 0, -1), 1.3))        # 15°倒角
    s = s.fuse(cz(19.0, zt - 40.0, zt - 29.3 + E, x))                         # D2 孔
    s = s.fuse(cz(42.0, zt - 0.3, zt + E, x))                                 # 锪平面 D1
    return s.removeSplitter()


def cavity_20(x):
    zt = H
    s = cz(20.0, zt - 14.5, zt + E, x)
    s = s.fuse(cz(18.4, zt - 21.0, zt - 14.5 + E, x))
    s = s.fuse(cone(9.2, 7.75, V(x, YC, zt - 21.0), V(0, 0, -1), 2.6))
    s = s.fuse(cz(15.5, zt - 33.0, zt - 23.6 + E, x))
    s = s.fuse(cz(38.0, zt - 0.3, zt + E, x))
    return s.removeSplitter()


def cavity_lower(x, kind):
    """阀孔中位于阀座以下、属于锁闭侧的部分（用于死容积统计）。"""
    zb = H - (40.0 if kind == "22" else 33.0)
    d = 19.0 if kind == "22" else 15.5
    return cz(d, zb, zb + 5.0, x)


# ------------------------------------------------------------------ 孔系网络
X = B["座阀阀孔"]["布置"]
XV2, XV4, XV3, XV1 = X["第二锁闭阀孔_V2"], X["预压阀孔_V4"], X["泄放阀孔_V3"], X["第一锁闭阀孔_V1"]
XRV = B["安全阀孔"]["X"]
HD = B["孔道"]
SP = HD["外侧孔道"]
MS = B["测压与测温"]
SEAL = B["安装与密封"]


def groove(x):
    g = B["安装与密封"]["密封槽"]
    return cz(g["外径"], -E, g["深"], x).cut(cz(g["内径"], -1, 3, x))


def side_passage(spec, x_override=None):
    x = spec["X"] if x_override is None else x_override
    z = spec["Z"]
    y0, y1 = spec["Y"]
    th = {"G3/8": G38, "G1/4": G14}[spec["螺纹"]]
    s = cy(spec["D"], y0 - 0.5, y1 + E, x, z)
    s = s.fuse(cy(th, W - spec["螺纹深"], W + E, x, z))
    s = s.fuse(cy(spec["锪平D"], W - 0.3, W + E, x, z))
    if "阻尼孔螺塞段" in spec:
        a, b = spec["阻尼孔螺塞段"]["Y"]
        s = s.fuse(cy(6.0, a - E, b + E, x, z)).fuse(cy(spec["过渡孔"]["D"], spec["过渡孔"]["Y"][0] - E, W - spec["螺纹深"] + E, x, z))
    return s.removeSplitter()


def nets():
    N = {}
    s3 = MS["第二测压孔_S3"]
    N["R_主孔道"] = cz(HD["第二主孔道_有杆腔"]["D"], -E, 22.0 + E, XV2)
    g2 = HD["第二锁闭油道_有杆腔"]
    N["R_锁闭油道"] = cx(g2["D"], 0.0, g2["X"][1]).fuse(tip(g2["D"], V(g2["X"][1], YC, ZG), V(1, 0, 0)))
    N["R_测压孔S3"] = cx(G14, -E, s3["螺纹深"]).fuse(cx(s3["锪平D"], -E, 0.3))
    N["R_V4阀口"] = cz(6.0, ZG - 3.0, 22.0 + E, XV4).fuse(tip(6.0, V(XV4, YC, ZG - 3.0), V(0, 0, -1)))
    N["R_RV阀口"] = cz(6.0, ZG - 3.0, H - 33.0 + E, XRV).fuse(tip(6.0, V(XRV, YC, ZG - 3.0), V(0, 0, -1)))
    bR = MS["测压排气孔_有杆腔"]
    N["R_测压排气孔"] = cy(bR["连通孔D"], bR["连通孔Y"][0] - E, bR["连通孔Y"][1] + 0.5, bR["X"], bR["Z"]).fuse(
        cy(M16, -E, bR["螺纹深"], bR["X"], bR["Z"])).fuse(cy(bR["锪平D"], -E, 0.3, bR["X"], bR["Z"]))
    N["R_密封槽"] = groove(XV2)
    # 无杆腔
    N["C_主孔道"] = cz(HD["第一主孔道_无杆腔"]["D"], -E, 22.0 + E, XV1)
    g1 = HD["第一锁闭油道_无杆腔"]
    th = MS["套管安装孔"]
    N["C_锁闭油道"] = cx(g1["D"], g1["X"][0], th["沉孔X"][0] + E).fuse(tip(g1["D"], V(g1["X"][0], YC, ZG), V(-1, 0, 0)))
    N["C_套管安装孔"] = cx(th["沉孔D"], th["沉孔X"][0], th["螺纹X"][0] + E).fuse(cx(14.0, th["螺纹X"][0], L + E)).fuse(
        cx(th["锪平D"], L - 0.3, L + E))
    s2 = MS["第一测压孔_S2"]
    N["C_测压孔S2"] = cy(s2["连通孔D"], s2["连通孔Y"][0] - E, s2["连通孔Y"][1] + 1.0, s2["X"], s2["Z"]).fuse(
        cy(G14, -E, s2["螺纹深"], s2["X"], s2["Z"])).fuse(cy(s2["锪平D"], -E, 0.3, s2["X"], s2["Z"]))
    op = B["阻尼孔螺塞"]
    N["C_V3阀口"] = cz(6.0, ZG - 3.0, 22.0 + E, XV3).fuse(tip(6.0, V(XV3, YC, ZG - 3.0), V(0, 0, -1))).fuse(
        cz(op["螺纹孔D"], op["螺纹孔Z"][0], op["螺纹孔Z"][1] + E, XV3))           # 阻尼孔螺塞螺纹孔 M8×1（按大径）
    bC = MS["测压排气孔_无杆腔"]
    N["C_测压排气孔"] = cy(bC["连通孔D"], bC["连通孔Y"][0] - E, bC["连通孔Y"][1] + 0.5, bC["X"], bC["Z"]).fuse(
        cy(M16, -E, bC["螺纹深"], bC["X"], bC["Z"])).fuse(cy(bC["锪平D"], -E, 0.3, bC["X"], bC["Z"]))
    N["C_密封槽"] = groove(XV1)
    # 外侧
    N["X_B口"] = side_passage(SP["第二外接油口B_V2"])
    N["X_PP口"] = side_passage(SP["预压油口PP_V4"])
    N["X_RV回油口"] = side_passage(SP["安全阀回油口_RV"])
    N["X_T口"] = side_passage(SP["泄油口T_V3"])
    N["X_A口"] = side_passage(SP["第一外接油口A_V1"])
    # 阀孔
    N["K_V2"] = cavity_22(XV2)
    N["K_V4"] = cavity_22(XV4)
    N["K_RV"] = cavity_20(XRV)
    N["K_V3"] = cavity_22(XV3)
    N["K_V1"] = cavity_22(XV1)
    # 紧固
    bo = SEAL["连接螺栓"]
    N["Z_螺栓孔"] = fuse(*[cz(bo["通孔D"], -E, H + E, x, y).fuse(cz(bo["沉孔D"], H - bo["沉孔深"], H + E, x, y))
                         for x, y in bo["位置"]])
    pn = SEAL["定位销"]
    N["Z_销孔"] = fuse(*[cz(6.0, -E, pn["孔深"], x, y) for x, y in pn["位置"]])
    return N


# ------------------------------------------------------------------ 元件
def cartridge_22(x):
    """直动式两通电磁座阀插装件（简化）：阀体 + 阀芯 + 线圈。阀座在 Z=27（第一阀口侧以下为锁闭侧）。"""
    a = V(x, YC, 0)
    prof = [(3.0, 23.0), (9.4, 23.0), (9.4, 29.5), (7.8, 29.5), (7.8, 31.5), (9.4, 31.5), (9.4, 33.0), (8.5, 33.0),
            (8.5, 45.0), (10.9, 45.0), (10.9, 62.0), (7.0, 62.0), (7.0, 118.0), (4.5, 118.0), (4.5, 58.0),
            (4.5, 28.0), (3.0, 27.0)]
    body = revolve_profile(prof, a, V(0, 0, 1))
    body = body.fuse(hexprism(27.0, V(x, YC, 62.0), V(0, 0, 1), 8.0).cut(cz(9.0, 61, 71, x)))
    for sgn in (-1, 1):
        body = body.cut(cy(4.0, YC - 9.0 if sgn < 0 else YC, YC + 9.0 if sgn > 0 else YC, x, 40.0))
    poppet = revolve_profile([(0.0, 25.8), (2.2, 25.8), (4.0, 28.5), (4.0, 57.0), (0.0, 57.0)], a, V(0, 0, 1))
    oring = revolve_profile([(7.85, 29.6), (9.35, 29.6), (9.35, 31.4), (7.85, 31.4)], a, V(0, 0, 1))
    coil = cz(40.0, 72.0, 112.0, x).cut(cz(14.2, 71, 113, x)).fuse(hexprism(19.0, V(x, YC, 112.0), V(0, 0, 1), 6.0).cut(cz(9.0, 111, 119, x)))
    return body.removeSplitter(), poppet, coil, oring


def cartridge_20(x):
    a = V(x, YC, 0)
    prof = [(2.5, 30.0), (7.65, 30.0), (7.65, 36.0), (6.2, 36.0), (6.2, 37.6), (7.65, 37.6), (7.65, 41.0), (8.0, 41.0),
            (8.0, 47.5), (9.9, 47.5), (9.9, 62.0), (10.0, 62.0), (10.0, 100.0), (4.0, 100.0), (4.0, 35.0), (2.5, 33.0)]
    body = revolve_profile(prof, a, V(0, 0, 1))
    body = body.fuse(hexprism(24.0, V(x, YC, 62.0), V(0, 0, 1), 8.0).cut(cz(8.0, 61, 71, x)))
    body = body.fuse(hexprism(17.0, V(x, YC, 100.0), V(0, 0, 1), 6.0))
    for sgn in (-1, 1):
        body = body.cut(cy(3.5, YC - 8.5 if sgn < 0 else YC, YC + 8.5 if sgn > 0 else YC, x, 44.0))
    poppet = revolve_profile([(0.0, 31.8), (1.8, 31.8), (3.4, 34.5), (3.4, 60.0), (0.0, 60.0)], a, V(0, 0, 1))
    oring = revolve_profile([(6.25, 36.1), (7.7, 36.1), (7.7, 37.5), (6.25, 37.5)], a, V(0, 0, 1))
    return body.removeSplitter(), poppet, oring


def psensor(p, d):
    """压力传感器 G1/4：螺柱（带 Ø3 引压孔）+ 六角 + 壳体 + 插头。p 为端口面中心，d 指向阀块外。"""
    d = V(d)
    din = d * -1
    stud = Part.makeCylinder(6.5, 12.0, p, din).cut(Part.makeCylinder(1.5, 12.2, p - din * 0.1, din))
    hx = hexprism(27.0, p, d, 10.0)
    body = Part.makeCylinder(12.0, 45.0, p + d * 10.0, d)
    conn = Part.makeCylinder(7.5, 15.0, p + d * 55.0, d)
    return fuse(stud, hx, body, conn)


def coupling(p, d):
    d = V(d)
    din = d * -1
    stud = Part.makeCylinder(7.9, 12.0, p, din).cut(Part.makeCylinder(2.0, 12.2, p - din * 0.1, din))
    return fuse(stud, hexprism(19.0, p, d, 10.0), Part.makeCylinder(7.0, 15.0, p + d * 10.0, d),
                Part.makeCylinder(9.0, 10.0, p + d * 25.0, d))


def thermowell():
    th = MS["套管安装孔"]
    tw = MS["油温传感器套管"]
    x0 = tw["端部X"]
    a = V(0, YC, ZG)
    prof = [(0.0, x0), (tw["外径"] / 2, x0), (tw["外径"] / 2, th["螺纹X"][0]), (6.95, th["螺纹X"][0]), (6.95, L),
            (tw["内径"] / 2, L), (tw["内径"] / 2, x0 + tw["端部壁厚"]), (0.0, x0 + tw["端部壁厚"])]
    body = revolve_profile(prof, a, V(1, 0, 0))
    head = hexprism(19.0, V(L, YC, ZG), V(1, 0, 0), 6.0).cut(cx(tw["内径"], L - 1, L + 7))
    well = body.fuse(head).removeSplitter()
    probe = cx(3.0, x0 + tw["端部壁厚"] + 0.1, L + 6.0).fuse(cx(12.0, L + 6.0, L + 34.0)).fuse(cx(8.0, L + 34.0, L + 44.0))
    return well, probe


def orifice_plug():
    """阻尼孔螺塞：旋在泄放阀孔孔底的第一阀口孔上段（锁闭侧），顶面开内六角，中心为阻尼孔。"""
    op = B["阻尼孔螺塞"]
    z0, z1 = op["Z"]
    d0 = op["图示孔径_mm"]                      # 图示阻尼孔径取可选范围上限，便于表达
    plug = cz(op["螺纹孔D"] - 0.1, z0, z1, XV3)
    plug = plug.cut(hexprism(op["内六角对边"], V(XV3, YC, z1 - op["内六角深"]), V(0, 0, 1), op["内六角深"] + 0.1))
    plug = plug.cut(cz(d0, z0 - 0.1, z1 - op["内六角深"] + 0.05, XV3))
    return plug


def oring_face(x):
    s = SEAL["密封槽"]
    a, b = 1.75, 0.98
    rc = s["外径"] / 2.0 - a - 0.03
    pts = [V(x + rc + a * math.cos(t), YC, 1.0 + b * math.sin(t)) for t in [2 * math.pi * i / 48 for i in range(48)]]
    w = Part.makePolygon(pts + [pts[0]])
    return Part.Face(w).revolve(V(x, YC, 0), V(0, 0, 1), 360)


def bolt(x, y):
    bo = SEAL["连接螺栓"]
    zh = H - bo["沉孔深"]
    head = cz(13.0, zh, zh + 8.0, x, y).cut(hexprism(6.0, V(x, y, zh + 4.0), V(0, 0, 1), 4.1))
    shank = cz(8.0, -bo["旋入端盖深"], zh + E, x, y)
    return head.fuse(shank).removeSplitter()


# ------------------------------------------------------------------ 缸体
def cylinder_parts():
    fc, br, rc = CY["前端盖"], CY["缸筒"], CY["后端盖"]
    D, d = CY["缸径"], CY["杆径"]
    out = {}
    cyl_ax = lambda dd, x0, x1: cx(dd, x0, x1, YC, ZA)   # noqa: E731
    f = box(fc["X"][0], fc["X"][1], 0, W, -90, 0).fuse(cyl_ax(fc["止口"]["D"] - 0.1, fc["止口"]["X"][0] - E, fc["止口"]["X"][1]))
    f = f.cut(cyl_ax(fc["杆孔D"], -1, fc["止口"]["X"][1] + 1))
    for g0 in (3.0, 10.0):
        f = f.cut(cyl_ax(42.0, g0, g0 + 4.0))
    o = CY["缸体油道"]["第二缸体油道_有杆腔"]
    pR = cz(o["竖孔"]["D"], o["竖孔"]["Z"][0], E, o["竖孔"]["X"]).fuse(tip(o["竖孔"]["D"], V(o["竖孔"]["X"], YC, o["竖孔"]["Z"][0]), V(0, 0, -1)))
    pR = pR.fuse(cx(o["轴向孔"]["D"], o["轴向孔"]["X"][0], o["轴向孔"]["X"][1] + E, YC, o["轴向孔"]["Z"]))
    f = f.cut(pR)
    bo = SEAL["连接螺栓"]
    for x, y in bo["位置"]:
        if x < fc["X"][1]:
            f = f.cut(cz(8.0, -bo["旋入端盖深"] - 3, E, x, y))
    for x, y in SEAL["定位销"]["位置"]:
        if x < fc["X"][1]:
            f = f.cut(cz(6.0, -6.0, E, x, y))
    out["12"] = ("前端盖", f.removeSplitter())
    b = box(br["X"][0], br["X"][1], 0, W, -90, -br["顶面让位_mm"])
    b = b.cut(cyl_ax(D, br["内孔X"][0] - 1, br["内孔X"][1] + 1))
    b = b.cut(cyl_ax(br["沉孔D"], br["X"][0] - 1, br["内孔X"][0])).cut(cyl_ax(br["沉孔D"], br["内孔X"][1], br["X"][1] + 1))
    out["11"] = ("缸筒", b.removeSplitter())
    r = box(rc["X"][0], rc["X"][1], 0, W, -90, 0).fuse(cyl_ax(rc["止口"]["D"] - 0.1, rc["止口"]["X"][0], rc["止口"]["X"][1] + E))
    o = CY["缸体油道"]["第一缸体油道_无杆腔"]
    pC = cz(o["竖孔"]["D"], o["竖孔"]["Z"][0], E, o["竖孔"]["X"]).fuse(tip(o["竖孔"]["D"], V(o["竖孔"]["X"], YC, o["竖孔"]["Z"][0]), V(0, 0, -1)))
    pC = pC.fuse(cx(o["轴向孔"]["D"], o["轴向孔"]["X"][0] - E, o["轴向孔"]["X"][1], YC, o["轴向孔"]["Z"]))
    r = r.cut(pC)
    for x, y in bo["位置"]:
        if x > rc["X"][0]:
            r = r.cut(cz(8.0, -bo["旋入端盖深"] - 3, E, x, y))
    for x, y in SEAL["定位销"]["位置"]:
        if x > rc["X"][0]:
            r = r.cut(cz(6.0, -6.0, E, x, y))
    out["13"] = ("后端盖", r.removeSplitter())
    # 活塞：伸出量 x（自完全缩回计），完全缩回时无杆腔侧凸台贴后端盖内端面
    xs = CY["图示伸出量x"]
    tb = CY["活塞限位凸台"]
    rear = br["内孔X"][1] - tb["无杆腔侧"]["h"] - xs
    front = rear - CY["活塞宽"]
    pis = cyl_ax(D - 0.1, front, rear).cut(cyl_ax(D + 1, front + 10.0, front + 19.0).cut(cyl_ax(D - 6.0, front + 9, front + 20)))
    pis = pis.fuse(cyl_ax(tb["无杆腔侧"]["D"], rear - E, rear + tb["无杆腔侧"]["h"]))
    pis = pis.fuse(cyl_ax(tb["有杆腔侧"]["D_out"], front - tb["有杆腔侧"]["h"], front + E).cut(cyl_ax(d + 0.2, front - 1, front + 1)))
    pis = pis.cut(cyl_ax(d, front - 1, front + 15.0))
    out["14"] = ("活塞", pis.removeSplitter())
    out["15"] = ("活塞杆", cyl_ax(d, -80.0, front + 15.0))
    # 密封件（示意，不编附图标记）：活塞组合密封、前端盖两道活塞杆密封
    out["14s"] = ("活塞密封件", cyl_ax(D - 0.05, front + 10.05, front + 18.95).cut(cyl_ax(D - 6.0, front + 9, front + 20)))
    rs = [cyl_ax(41.9, g0 + 0.05, g0 + 3.95).cut(cyl_ax(d + 0.1, g0, g0 + 4)) for g0 in (3.0, 10.0)]
    out["12s"] = ("活塞杆密封件", rs[0].fuse(rs[1]))
    geo = {"活塞前端面X": front, "活塞后端面X": rear, "无杆腔X": [rear, br["内孔X"][1]], "有杆腔X": [br["内孔X"][0], front]}
    return out, pR, pC, geo


# ------------------------------------------------------------------ 主程序
def main():
    t0 = time.time()
    N = nets()
    blk = box(0, L, 0, W, 0, H)
    blk = blk.cut(Part.makeCompound(list(N.values())))
    blk = blk.removeSplitter()
    parts = []                                   # (PartNo, 名称, Kind, Material, Group, shape)
    parts.append(("2", "阀块本体", "结构件", BK["材料"], "阀块", blk))
    # PartNo 即附图标记（V1.1 起与 05_附图/numerals.json 一致）；阀的阀芯、线圈、O 形圈用后缀 p/c/o 区分所属阀
    for pno, nm, x in (("41", "第一锁闭座阀", XV1), ("42", "第二锁闭座阀", XV2), ("43", "泄放座阀", XV3), ("44", "预压座阀", XV4)):
        body, pop, coil, orr = cartridge_22(x)
        parts += [(pno, nm, "外购件", "钢", "阀", body), (pno + "p", nm + "阀芯", "外购件", "钢", "阀", pop),
                  (pno + "c", nm + "电磁线圈", "外购件", "钢/树脂", "阀", coil), (pno + "o", nm + "阀体O形圈", "标准件", "NBR", "阀", orr)]
    body, pop, orr = cartridge_20(XRV)
    parts += [("45", "安全溢流阀", "外购件", "钢", "阀", body), ("45p", "安全溢流阀阀芯", "外购件", "钢", "阀", pop),
              ("45o", "安全溢流阀O形圈", "标准件", "NBR", "阀", orr)]
    s2 = MS["第一测压孔_S2"]
    parts.append(("71", "第一压力传感器", "外购件", "不锈钢", "传感器", psensor(V(s2["X"], 0.0, s2["Z"]), V(0, -1, 0))))
    parts.append(("72", "第二压力传感器", "外购件", "不锈钢", "传感器", psensor(V(0.0, YC, ZG), V(-1, 0, 0))))
    well, probe = thermowell()
    parts.append(("73", "油温传感器套管", "结构件", MS["油温传感器套管"]["材料"], "传感器", well))
    parts.append(("74", "油温传感器", "外购件", "不锈钢", "传感器", probe))
    for pno, key in (("75", "测压排气孔_有杆腔"), ("75", "测压排气孔_无杆腔")):
        b = MS[key]
        parts.append((pno, "测压排气接头（%s）" % key[-3:], "外购件", "钢", "传感器", coupling(V(b["X"], 0.0, b["Z"]), V(0, -1, 0))))
    parts.append(("76", "阻尼孔螺塞", "结构件", "不锈钢", "阀块", orifice_plug()))
    for x in (XV1, XV2):
        parts.append(("27", "端面密封圈", "标准件", "NBR70", "密封", oring_face(x)))
    for x, y in SEAL["连接螺栓"]["位置"]:
        parts.append(("28", "连接螺栓", "标准件", "8.8 级钢", "紧固", bolt(x, y)))
    for x, y in SEAL["定位销"]["位置"]:
        parts.append(("29", "定位销", "标准件", "钢", "紧固", cz(6.0, -6.0, 10.0 - 0.5, x, y)))
    cyl, pR, pC, geo = cylinder_parts()
    for pno, (nm, s) in cyl.items():
        if pno.endswith("s"):
            parts.append((pno, nm, "标准件", "PTFE/NBR", "缸", s))
        else:
            parts.append((pno, nm, "结构件", "45 钢" if pno != "15" else "45 钢镀铬", "缸", s))

    doc = App.newDocument("P5_ChuTu")
    objs = []
    for i, (pno, nm, kind, mat, grp, s) in enumerate(parts):
        o = doc.addObject("Part::Feature", "P%02d_%s" % (i, pno))
        o.Shape = s
        o.Label = "%s_%s" % (pno, nm)
        for pn, v in (("PartNo", pno), ("Kind", kind), ("Material", mat), ("Group_", grp), ("Structure", nm)):
            o.addProperty("App::PropertyString", pn, "Patent")
            setattr(o, pn, v)
        objs.append(o)
    g = doc.addObject("App::DocumentObjectGroup", "Nets")
    g.Label = "孔系网络（检查用）"
    for k, s in list(N.items()) + [("Y_缸体油道_有杆腔", pR), ("Y_缸体油道_无杆腔", pC)]:
        f = doc.addObject("Part::Feature", "N_" + str(len(g.Group)))
        f.Shape = s
        f.Label = "孔系_" + k
        f.addProperty("App::PropertyString", "Net", "Patent")
        f.Net = k
        f.addProperty("App::PropertyBool", "Virtual", "Patent")
        f.Virtual = True
        g.addObject(f)
    doc.recompute()
    fc = os.path.join(OUTDIR, "P5_出图模型.FCStd")
    doc.saveAs(fc)
    blk_objs = [o for o in objs if o.Group_ != "缸"]
    Part.export(blk_objs, os.path.join(OUTDIR, "集成锁闭阀块.step"))
    Part.export(objs, os.path.join(OUTDIR, "尾座油缸与集成锁闭阀块_装配.step"))
    rep = {"生成时间": time.strftime("%Y-%m-%d %H:%M:%S"), "FreeCAD": ".".join(App.Version()[:3]),
           "阀块本体": {"valid": blk.isValid(), "体积_cm3": round(blk.Volume / 1000, 2), "质量_45钢_kg": round(blk.Volume * 7.85e-6, 2),
                    "包围盒": [round(v, 2) for v in (blk.BoundBox.XMin, blk.BoundBox.XMax, blk.BoundBox.YMin, blk.BoundBox.YMax,
                                                     blk.BoundBox.ZMin, blk.BoundBox.ZMax)]},
           "零件数": len(parts), "零件": [{"PartNo": p[0], "名称": p[1], "valid": p[5].isValid(), "体积_cm3": round(p[5].Volume / 1000, 3)} for p in parts],
           "缸体几何": geo, "孔系网络": list(N.keys()), "耗时_s": round(time.time() - t0, 1)}
    with open(os.path.join(OUTDIR, "_build_report.json"), "w", encoding="utf-8") as fh:
        json.dump(rep, fh, ensure_ascii=False, indent=1)
    print("BUILD_DONE", rep["阀块本体"], "parts", len(parts), "t", rep["耗时_s"])
    App.closeDocument(doc.Name)


main()
