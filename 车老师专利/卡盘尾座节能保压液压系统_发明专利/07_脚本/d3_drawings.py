# -*- coding: utf-8 -*-
"""D3 工程图（TechDraw，需 GUI）：freecad.exe 07_脚本/d3_drawings.py
输出 04_模型/工程图/*.pdf|*.svg 与 工程图.FCStd。
页：DWG-55 锁闭阀块（三视图+A-A/B-B 剖视）、DWG-00 试验台总装图、DWG-63 楔块、DWG-64 从动楔座、DWG-51 工件模拟滑块。
"""
import os, time, traceback, importlib.util
import FreeCAD as App
import FreeCADGui as Gui
import Part

V = App.Vector
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "04_模型", "工程图")
os.makedirs(OUT, exist_ok=True)
TPL = os.path.join(App.getResourceDir(), "Mod", "TechDraw", "Templates", "ISO")
LOG = open(os.path.join(OUT, "_drawings.log"), "w", encoding="utf-8")


def log(*a):
    LOG.write(" ".join(str(x) for x in a) + "\n")
    LOG.flush()


def spin(n=30):
    for _ in range(n):
        Gui.updateGui()
        time.sleep(0.05)


import TechDraw  # noqa: E402
import TechDrawGui  # noqa: E402

doc = App.newDocument("D3_Drawings")


def page(name, size, title, dwgno, scale_txt, material="", mass=""):
    p = doc.addObject("TechDraw::DrawPage", "Page_" + name)
    t = doc.addObject("TechDraw::DrawSVGTemplate", "Tpl_" + name)
    t.Template = os.path.join(TPL, "%s_Landscape_ISO5457_minimal.svg" % size)
    p.Template = t
    p.Label = dwgno + " " + title
    W, H = {"A1": (841, 594), "A2": (594, 420), "A3": (420, 297)}[size]
    p.addProperty("App::PropertyFloat", "PW").PW = W
    p.addProperty("App::PropertyFloat", "PH").PH = H
    # 自绘标题栏（右下角 180×40）
    tb = ["卡盘尾座节能保压液压系统 试验台", "%s  %s" % (dwgno, title),
          "比例 %s   材料 %s" % (scale_txt, material or "-"),
          "质量 %s   图幅 %s   D3 2026-10" % (mass or "-", size)]
    note(p, tb, W - 195, 50, 4.0)
    return p


def note(p, lines, x, y, size=3.5):
    a = doc.addObject("TechDraw::DrawViewAnnotation", "Note")
    a.Text = lines
    a.TextSize = size
    a.Font = "SimHei"
    a.X, a.Y = x, y
    p.addView(a)
    return a


def view(p, src, d, x, y, scale, xdir=None, hidden=True, label=""):
    v = doc.addObject("TechDraw::DrawViewPart", "View")
    p.addView(v)
    v.Source = src
    v.Direction = d
    if xdir is not None:
        v.XDirection = xdir
    v.Scale = scale
    v.ScaleType = "Custom"
    v.HardHidden = hidden
    v.X, v.Y = x, y
    v.Caption = label
    return v


def section(p, base, src, origin, normal, sym, x, y, scale, xdir=None):
    s = doc.addObject("TechDraw::DrawViewSection", "Sec_" + sym)
    p.addView(s)
    s.BaseView = base
    s.Source = src
    s.SectionOrigin = origin
    s.SectionNormal = normal
    s.Direction = normal
    if xdir is not None:
        s.XDirection = xdir
    s.SectionSymbol = sym
    s.Scale = scale
    s.ScaleType = "Custom"
    s.X, s.Y = x, y
    s.Caption = "%s-%s" % (sym, sym)
    try:
        s.CutSurfaceDisplay = "Hatch"
    except Exception:
        pass
    return s


def wait(v):
    for _ in range(200):
        Gui.updateGui()
        time.sleep(0.05)
        try:
            if v.getVisibleEdges():
                return
        except Exception:
            pass


def verts(v):
    out, i = [], 0
    while True:
        try:
            out.append((i, v.getVertexByIndex(i).Point))
        except Exception:
            return out
        i += 1


def edges(v):
    out, i = [], 0
    while True:
        try:
            out.append((i, v.getEdgeByIndex(i)))
        except Exception:
            return out
        i += 1


def proj(v, P3):
    q = v.projectPoint(P3)
    return q


def near_vertex(v, P3):
    q = proj(v, P3)
    best = None
    for i, pt in verts(v):
        for sgn in (1, -1):
            d = (pt.x - q.x) ** 2 + (pt.y - sgn * q.y) ** 2
            if best is None or d < best[0]:
                best = (d, i)
    return best[1], best[0] ** 0.5


def dim(p, v, typ, P3a, P3b, fmt=None, tol=None, ox=0, oy=0):
    """typ: DistanceX / DistanceY / Distance。P3a/P3b 为模型三维点。tol=(上,下)。"""
    try:
        ia, da = near_vertex(v, P3a)
        ib, db = near_vertex(v, P3b)
        if ia == ib or da > 0.6 or db > 0.6:
            log("dim skip", typ, P3a, P3b, da, db)
            return None
        d = doc.addObject("TechDraw::DrawViewDimension", "Dim")
        d.Type = typ
        d.References2D = [(v, "Vertex%d" % ia), (v, "Vertex%d" % ib)]
        p.addView(d)
        if fmt:
            d.FormatSpec = fmt
        if tol:
            d.EqualTolerance = tol[0] == -tol[1]
            d.OverTolerance = tol[0]
            d.UnderTolerance = tol[1]
        d.X, d.Y = ox, oy
        return d
    except Exception as e:  # noqa: BLE001
        log("dim err", e)
        return None


def dia(p, v, center3, r, fmt=None, tol=None, typ="Diameter", ox=0, oy=0):
    q = proj(v, center3)
    sc = v.Scale
    for i, e in edges(v):
        c = e.Curve
        if isinstance(c, Part.Circle) and abs(c.Radius - r * sc) < 0.02 * sc + 1e-3:
            for sgn in (1, -1):
                if (c.Center.x - q.x) ** 2 + (c.Center.y - sgn * q.y) ** 2 < 0.25:
                    d = doc.addObject("TechDraw::DrawViewDimension", "Dia")
                    d.Type = typ
                    d.References2D = [(v, "Edge%d" % i)]
                    p.addView(d)
                    if fmt:
                        d.FormatSpec = fmt
                    if tol:
                        d.EqualTolerance = tol[0] == -tol[1]
                        d.OverTolerance = tol[0]
                        d.UnderTolerance = tol[1]
                    d.X, d.Y = ox, oy
                    return d
    log("dia miss", center3, r)
    return None


def export(p, name):
    doc.recompute()
    spin(60)
    TechDrawGui.exportPageAsPdf(p, os.path.join(OUT, name + ".pdf"))
    TechDrawGui.exportPageAsSvg(p, os.path.join(OUT, name + ".svg"))
    log("exported", name)


def fixed(shape, label):
    o = doc.addObject("Part::Feature", label)
    o.Shape = shape
    o.Visibility = False
    return o


# ======================================================================= DWG-55 锁闭阀块
def dwg55():
    spec = importlib.util.spec_from_file_location("vb", os.path.join(ROOT, "07_脚本", "d3_valve_block.py"))
    vb = importlib.util.module_from_spec(spec)
    vb.BUILD_ONLY = True
    spec.loader.exec_module(vb)
    blk, _ = vb.build()
    src = [fixed(blk, "VB55")]
    L, W, H, YC, ZG = vb.L, vb.W, vb.H, vb.YC, vb.ZG
    p = page("55", "A2", "锁闭阀块", "D3-55", "1:1", "45 钢调质", "12.0 kg")
    s = 1.0
    # 主视图：从前面(−Y)看，X 向右、Z 向上；俯视图在其下（第一角投影）；左视图在其右
    fv = view(p, src, V(0, -1, 0), 150, 300, s, V(1, 0, 0), label="主视图")
    tv = view(p, src, V(0, 0, 1), 150, 175, s, V(1, 0, 0), label="俯视图")
    lv = view(p, src, V(-1, 0, 0), 330, 300, s, V(0, -1, 0), label="左视图")
    for v in (fv, tv, lv):
        wait(v)
    sa = section(p, tv, src, V(L / 2, YC, H / 2), V(0, 1, 0), "A", 150, 70, s, V(1, 0, 0))   # 沿主油道纵剖
    sb = section(p, fv, src, V(185, YC, H / 2), V(1, 0, 0), "B", 470, 300, s, V(0, 1, 0))   # 过 V1 插装腔横剖
    wait(sa)
    wait(sb)
    doc.recompute()
    spin(40)
    # 外形与位置尺寸（主视图）
    dim(p, fv, "DistanceX", V(0, 0, 0), V(L, 0, 0), "%.0f", (0, -0.2), 0, -50)
    dim(p, fv, "DistanceY", V(L, 0, 0), V(L, 0, H), "%.0f", (0.1, -0.1), 135, 0)
    for x, t in ((55, None), (95, None), (145, None), (185, None)):
        dim(p, fv, "DistanceX", V(0, 0, H), V(x - vb.CAV["d1"] / 2, 0, H), None, None, 0, 45 + x / 6)
    # 俯视图：宽度、螺栓孔、插装孔
    dim(p, tv, "DistanceY", V(L, 0, H), V(L, W, H), "%.0f", (0, -0.2), 135, 0)
    dia(p, tv, V(185, YC, H), vb.CAV["d1"] / 2, "%.2f 3/4-16UNF-2B T-162A ×4", None, "Diameter", 40, 55)
    dia(p, tv, V(30, 12, H), 7.0, "4×%.0f 沉孔深9 / Ø9 通孔 (M8)", None, "Diameter", -60, -35)
    dim(p, tv, "DistanceX", V(30, 12, H), V(210, 12, H), "%.0f", (0.1, -0.1), 0, -52)
    dim(p, tv, "DistanceY", V(30, 12, H), V(30, 78, H), "%.0f", (0.1, -0.1), -135, 0)
    # 剖视 A-A：油道高度、油口
    note(p, ["A-A 沿主油道（Y=45）纵剖；B-B 过 V1 插装腔（X=185）横剖"], 30, 30, 3.5)
    holes = [
        "孔表（局部坐标：X 自前端面，Y 自前面，Z 自结合底面）",
        "H1 插装腔 V2/V4/V3/V1  X=55/95/145/185 Y=45  Sun T-162A：3/4-16UNF-2B 深14，Ø17.48H8 至深24，Ø12.70H8 至深33.3（尺寸待按 Sun 腔体图核实）",
        "H2 主油道 Ø6  Z=20 Y=45：有杆腔 X0~98（端口 S3），无杆腔 X120~240（端口 S2），两网络间隔 22",
        "H3 缸体结合口 Ø8  X=20/220 自底面至 Z20；O 形圈槽 Ø14H11/Ø21.2H11 深 2.0+0.1（O 形圈 14×2.65 GB/T 3452.1，FKM）",
        "H4 传感器口 S3/S2 G1/4 深14（ISO 1179-1，端面 Ø25 锪平 Ra1.6）  左端面/右端面 Z=20",
        "H5 油温传感器 T1 M10×1 深14+Ø8.5  X=125 前面 Z=20（TR31 护套型，直通无杆腔油道）",
        "H6 测压口 MP1/MP2 M10×1 深12（Minimess 类测压接头）  X=75/165 前面 Z=20",
        "H7 排气/工艺堵 PL1/PL2 M8×1 深10 + Ø4  X=75/165 顶面（最高点，首次注油排气）",
        "H8 外接油口 B/Ppre/T/A G1/4 深14 后面 X=55/95/145/145/185 Z=56，Ø6 通至插装腔侧口；T 口内 M6 阻尼塞座(22)",
        "H9 安装孔 4×Ø9 通，沉孔 Ø14 深9（M8×80 GB/T 70.1 12.9 级，拧紧 30 N·m）  孔距 180×66",
        "H10 定位销孔 2×Ø6H7 深10（底面对角 X8/Y8、X232/Y82）",
    ]
    note(p, holes, 25, 400, 3.2)
    req = ["技术要求", "1. 材料 45 钢调质 HB220~250，发黑；或 6061-T6（≤7 MPa）。未注倒角 C1，孔口去毛刺倒角 C0.5。",
           "2. 结合底面平面度 0.02，Ra0.8；插装腔、传感器口锪平面 Ra1.6；孔内交叉处去毛刺，清洁度 ISO 4406 -/16/13。",
           "3. 插装腔用 Sun 成形刀具加工，与底面垂直度 0.05；螺纹按 ASME B1.1。",
           "4. 油道最小壁厚 ≥3（校核 C07：最小 3.0，位于 O 形圈槽与结合口之间）。",
           "5. 加工完成后 10.5 MPa（1.5×7 MPa）保压 5 min 无渗漏；两网络间互窜检测零泄漏。",
           "6. 未注公差 GB/T 1804-m；未注形位公差 GB/T 1184-K。"]
    note(p, req, 330, 150, 3.3)
    export(p, "DWG-55_锁闭阀块")


# ======================================================================= 读出图模型
def load_tc():
    tc = App.openDocument(os.path.join(ROOT, "04_模型", "试验台出图模型.FCStd"))
    return tc, {o.PartNo: o for o in tc.Objects if hasattr(o, "PartNo")}


def at_origin(sh):
    s = sh.copy()
    b = s.BoundBox
    s.translate(V(-b.XMin, -b.YMin, -b.ZMin))
    return s


def dwg00(tc, P):
    allsh = Part.makeCompound([o.Shape for k, o in P.items() if not k.startswith("57") and k != "58"])
    src = [fixed(allsh, "TC_ALL")]
    p = page("00", "A1", "试验台总装图", "D3-00", "1:10", "-", "≈1090 kg")
    s = 0.1
    fv = view(p, src, V(0, -1, 0), 230, 400, s, V(1, 0, 0), False, "主视图（防护罩、前门未示）")
    tv = view(p, src, V(0, 0, 1), 230, 210, s, V(1, 0, 0), False, "俯视图")
    lv = view(p, src, V(-1, 0, 0), 450, 400, s, V(0, -1, 0), False, "左视图")
    iso = view(p, src, V(1, -1, 1), 620, 420, s * 1.0, None, False, "轴测图")
    for v in (fv, tv, lv, iso):
        wait(v)
    b = allsh.BoundBox
    dim(p, fv, "DistanceX", V(0, 0, 0), V(1800, 0, 0), "%.0f", None, 0, -55)
    dim(p, fv, "DistanceY", V(1800, 0, 0), V(1800, 0, 850), "台面高 %.0f", None, 110, 0)
    # 局部放大：尾座缸+阀块+加载单元 1:2
    sub = Part.makeCompound([P[k].Shape for k in ("51", "52", "53", "54", "66", "67", "68", "69", "70", "55", "26s",
                                                  "61", "19", "20", "21", "23", "24", "25", "30", "63", "64", "49",
                                                  "48", "62", "50", "50c", "43") if k in P])
    src2 = [fixed(sub, "TC_SUB")]
    dv = view(p, src2, V(0, -1, 0), 620, 210, 0.25, V(1, 0, 0), False, "局部视图 I（加载—尾座—锁闭阀块，1:4）")
    wait(dv)
    dim(p, dv, "DistanceX", V(880, 455, 1080), V(1640, 455, 1080), "%.0f", None, 0, -70)
    rows = ["明细（件号  名称  数量  备注）"]
    for k in ("41", "42", "43", "45", "46", "12", "44", "48", "47", "62", "63", "64", "49", "50", "51", "52", "53",
              "54", "26(66/67/68/69/70)", "55", "19", "20", "21", "23", "24", "25", "30", "61", "56", "57", "58",
              "59", "27", "28", "1", "3", "4", "8", "60"):
        kk = k.split("(")[0]
        nm = P[kk].PartName if kk in P else ("尾座液压缸 Ø63/Ø35-140" if kk == "26" else "")
        rows.append("%-5s %s  1" % (k, nm))
    note(p, rows[:21], 40, 560, 3.2)
    note(p, rows[21:], 150, 560, 3.2)
    note(p, ["技术要求", "1. 模拟主轴、顶尖、尾座套筒同轴度 Ø0.02（Z=1080，Y=500）。",
             "2. 锁闭阀块 55 直装尾座缸 66 顶面，两腔油口 O 形圈端面密封，锁闭腔内无软管。",
             "3. 楔块 1:10 加载，机械限位与 20 kN 力限；防护门 58 打开时伺服断使能、泵禁止启动。",
             "4. 外形 1800×860×1360，件号与 05_附图/numerals_structure.json 一致。"], 300, 110, 3.5)
    export(p, "DWG-00_试验台总装图")


def part_dwg(P, pno, title, mat, notes, dims_fn, size="A3", scale=0.5, stxt="1:2"):
    sh = at_origin(P[pno].Shape)
    m = sh.Volume * 7.85e-6
    src = [fixed(sh, "P" + pno)]
    p = page(pno, size, title, "D3-%s" % pno, stxt, mat, "%.2f kg" % m)
    b = sh.BoundBox
    fv = view(p, src, V(0, -1, 0), 110, 200, scale, V(1, 0, 0), True, "主视图")
    tv = view(p, src, V(0, 0, 1), 110, 95, scale, V(1, 0, 0), True, "俯视图")
    lv = view(p, src, V(-1, 0, 0), 245, 200, scale, V(0, -1, 0), True, "左视图")
    iso = view(p, src, V(1, -1, 1), 340, 215, scale * 0.8, None, False, "轴测")
    for v in (fv, tv, lv, iso):
        wait(v)
    doc.recompute()
    spin(20)
    dim(p, fv, "DistanceX", V(b.XMin, b.YMin, b.ZMin), V(b.XMax, b.YMin, b.ZMin), "%.0f", None, 0, -45)
    dim(p, fv, "DistanceY", V(b.XMax, b.YMin, b.ZMin), V(b.XMax, b.YMin, b.ZMax), "%.0f", None, 50, 0)
    dims_fn(p, fv, tv, lv, sh)
    note(p, ["技术要求"] + notes, 200, 120, 3.2)
    export(p, "DWG-%s_%s" % (pno, title))


def main():
    try:
        dwg55()
    except Exception:
        log(traceback.format_exc())
    try:
        tc, P = load_tc()
        try:
            dwg00(tc, P)
        except Exception:
            log(traceback.format_exc())

        def d63(p, fv, tv, lv, sh):
            # 楔块：俯视图斜面 1:10，长 200
            dim(p, tv, "DistanceY", V(0, 0, 158), V(0, 200, 158), "%.0f", (0, -0.1), -60, 0)
            dim(p, tv, "DistanceX", V(0, 0, 158), V(30, 0, 158), "%.0f", (0.02, -0.02), 0, -40)
            dim(p, tv, "DistanceX", V(0, 200, 158), V(50, 200, 158), "%.0f", (0.02, -0.02), 0, 40)
            dia(p, lv, V(27, 10, 78), 8.5, "Ø%.0f（滚珠丝杠螺母安装孔，按 SFU1605 法兰配作）", None, "Diameter", 40, 30)
        part_dwg(P, "63", "楔块", "GCr15 淬火 HRC58~62 / 或 40Cr 调质+表面淬火",
                 ["1. 斜面斜率 1:10（tanθ=0.1，θ=5.71°），斜面平面度 0.005，Ra0.4，与底面垂直度 0.01。",
                  "2. 斜面与从动楔座 64 配研，接触斑点 ≥80%；tanθ=0.1 不自锁，须伺服保持（≤0.08 时自锁，μ≈0.1 假设）。",
                  "3. 底面 Ra0.8，与加载座 48 导向面 H7/g6 配合。",
                  "4. 丝杠螺母孔与斜面平行度 0.01/100。未注公差 GB/T 1804-f。"], d63)

        def d64(p, fv, tv, lv, sh):
            dim(p, tv, "DistanceY", V(68, 0, 158), V(68, 120, 158), "%.0f", (0, -0.05), 60, 0)
        part_dwg(P, "64", "从动楔座", "GCr15 淬火 HRC58~62",
                 ["1. 斜面 1:10 与楔块 63 配研，平面度 0.005，Ra0.4。",
                  "2. 推力输出端面（接推力传感器 49）与 X 轴垂直度 0.005，Ra0.4。",
                  "3. 位移缩小比 1:10：丝杠导程 5 mm、楔块 Y 向 1 µm → 滑块 X 向 0.1 µm。",
                  "4. 斜面与导向面在一次装夹中精磨。未注公差 GB/T 1804-f。"], d64)

        def d51(p, fv, tv, lv, sh):
            dim(p, lv, "DistanceX", V(0, 0, 0), V(0, 150, 0), "%.0f", None, 0, -45)
            dim(p, fv, "DistanceY", V(0, 0, 0), V(0, 0, 115), "中心高 %.0f", (0.01, -0.01), -55, 0)
        part_dwg(P, "51", "工件模拟滑块", "45 钢调质 HB220~250（或 Q235 时效）",
                 ["1. 顶尖中心孔 60°（GB/T 145 B 型 B4），与导轨安装面距离 115±0.01（主轴中心高 1080）。",
                  "2. 中心孔轴线与导轨安装底面平行度 0.01，与推力受力面垂直度 0.01。",
                  "3. 底面与 2 组 HGH15 导轨滑块 50c 螺钉连接（孔位按滑块样本配作），底面平面度 0.01，Ra0.8。",
                  "4. 滑块行程 ≥0.5 mm，无间隙预紧。未注公差 GB/T 1804-m。"], d51)
    except Exception:
        log(traceback.format_exc())
    doc.saveAs(os.path.join(OUT, "工程图.FCStd"))
    log("ALL_DONE")
    LOG.close()


main()
try:
    import sys; os._exit(0)
except Exception:
    pass
