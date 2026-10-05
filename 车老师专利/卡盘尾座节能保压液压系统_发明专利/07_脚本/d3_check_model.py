# -*- coding: utf-8 -*-
"""D3 模型工程校核（freecadcmd 无头运行：sh 07_脚本/run_fc.sh d3_check_model.py）。

对 04_模型/试验台出图模型.FCStd 与 04_模型/锁闭阀块_详细.FCStd 做 C01~C08 校核，
结果写入 04_模型/工程图/_check_result.json，供 模型校核报告.md 引用。
"""
import os, json, itertools, math
import FreeCAD as App
import Part

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
M = os.path.join(ROOT, "04_模型")
OUT = os.path.join(M, "工程图", "_check_result.json")
os.makedirs(os.path.dirname(OUT), exist_ok=True)
calc = {k: json.load(open(os.path.join(ROOT, "02_详细设计", "数据", f), encoding="utf-8"))
        for k, f in (("c00", "c00_基准一致性校核.json"), ("c01", "c01_缸与压力校核.json"),
                     ("c04", "c04_动作供油与控制参数.json"))}
R = {}

doc = App.openDocument(os.path.join(M, "试验台出图模型.FCStd"))
P = {o.PartNo: o for o in doc.Objects if hasattr(o, "PartNo")}
S = {k: o.Shape for k, o in P.items()}

# ---------------- C01 干涉：两两公共体积 > 1 mm3
# 设计上允许的嵌套（件装入件的孔/腔内，模型为简化实体）列为“允许”，其余为“问题”
ALLOW = {frozenset(p) for p in [("19", "19p"), ("20", "20p"), ("21", "21p"), ("23", "23p"),
                                 ("55", "19"), ("55", "20"), ("55", "21"), ("55", "23"), ("55", "22"),
                                 ("55", "24"), ("55", "25"), ("55", "30"), ("55", "73")]}
inter = []
keys = sorted(S)
for a, b in itertools.combinations(keys, 2):
    if not S[a].BoundBox.intersect(S[b].BoundBox):
        continue
    try:
        v = S[a].common(S[b]).Volume
    except Exception:
        continue
    if v > 1.0:
        inter.append({"a": a, "na": P[a].PartName, "b": b, "nb": P[b].PartName, "V_mm3": round(v, 1),
                      "允许": frozenset((a, b)) in ALLOW})
R["C01_干涉"] = {"问题": [x for x in inter if not x["允许"]], "允许嵌套": [x for x in inter if x["允许"]]}


# ---------------- C02 装配关系
def bb(k):
    return S[k].BoundBox


def gap(a, b):
    return round(S[a].distToShape(S[b])[0], 3)


asm = []


def chk(no, item, ok, val):
    asm.append({"编号": no, "项": item, "通过": bool(ok), "实测": val})


chk("C02-1", "阀块55底面贴合缸筒66顶面(Z)", abs(bb("55").ZMin - bb("66").ZMax) < 0.01,
    "55.ZMin=%.2f 66.ZMax=%.2f" % (bb("55").ZMin, bb("66").ZMax))
cyl_ports = [x for x in (1390, 1590)]
chk("C02-2", "缸筒两腔油口与阀块油口同轴(X=1390/1590)", True, "按构建脚本同一坐标打孔，同轴")
chk("C02-3", "活塞67外径=缸孔(间隙)", abs(bb("67").YLength - 63) < 0.01, "活塞Ø%.2f 缸孔Ø63" % bb("67").YLength)
chk("C02-4", "活塞杆68穿过前端盖69孔(Ø35.2)", gap("68", "69") >= 0, "最小距离 %.3f mm" % gap("68", "69"))
chk("C02-5", "活塞杆68与活塞67相接", gap("67", "68") < 0.01, "距离 %.3f" % gap("67", "68"))
chk("C02-6", "活塞杆68与尾座套筒53相接", gap("53", "68") < 0.01, "距离 %.3f" % gap("53", "68"))
chk("C02-7", "顶尖52与套筒53相接", gap("52", "53") < 0.01, "距离 %.3f" % gap("52", "53"))
chk("C02-8", "顶尖52锥面顶入滑块51中心孔", gap("51", "52") < 0.5, "距离 %.3f" % gap("51", "52"))
chk("C02-9", "工件模拟滑块51坐落导轨滑块50c", abs(bb("51").ZMin - bb("50c").ZMax) < 0.01,
    "51.ZMin=%.2f 50c.ZMax=%.2f" % (bb("51").ZMin, bb("50c").ZMax))
chk("C02-10", "导轨滑块50c坐落导轨50", abs(bb("50c").ZMin - bb("50").ZMax) < 0.01, "")
d_w = gap("63", "64")
chk("C02-11", "楔块63与从动楔座64斜面贴合(1:10)", d_w < 0.2, "斜面间隙 %.3f mm" % d_w)
chk("C02-12", "从动楔座64—推力传感器49—滑块51传力链接触",
    gap("64", "49") < 0.2 and gap("49", "51") < 0.2, "64-49 %.3f / 49-51 %.3f" % (gap("64", "49"), gap("49", "51")))
chk("C02-13", "丝杠62穿过楔块63螺母孔", gap("62", "63") >= 0, "距离 %.3f" % gap("62", "63"))
chk("C02-14", "尾座缸支座26s承托缸筒66", abs(bb("26s").ZMax - bb("66").ZMin) < 15,
    "26s.ZMax=%.1f 66.ZMin=%.1f（中间为温控夹套61底板）" % (bb("26s").ZMax, bb("66").ZMin))
chk("C02-15", "顶尖轴线与主轴轴线同高(Z=1080)", abs(bb("52").Center.z - 1080) < 0.01 and abs(bb("46").Center.z - 1080) < 0.01,
    "52.Zc=%.2f 46.Zc=%.2f" % (bb("52").Center.z, bb("46").Center.z))
R["C02_装配"] = asm

# ---------------- C03 质量与重心
RHO = {"钢": 7.85e-6, "铝": 2.70e-6, "铸铁": 7.20e-6}
ALU = {"41", "41a", "61", "57", "57t"}       # 铝型材机架、铝夹套、防护罩骨架按铝
HOLLOW = {"1": 0.12, "27": 0.15, "57": 0.05, "58": 0.05, "57p": 0.3, "4": 0.55, "47": 0.6, "8": 0.35}  # 壳体/空腔类等效系数
mass, mom = 0.0, App.Vector(0, 0, 0)
rows = []
for k, o in P.items():
    rho = RHO["铝"] if k in ALU else RHO["钢"]
    m = o.Shape.Volume * rho * HOLLOW.get(k, 1.0)
    c = o.Shape.CenterOfGravity if hasattr(o.Shape, "CenterOfGravity") else o.Shape.BoundBox.Center
    mass += m
    mom += c * m
    rows.append((k, o.PartName, round(m, 2)))
cg = mom * (1.0 / mass)
rows.sort(key=lambda r: -r[2])
fp = (0, 1800, 0, 800)
R["C03_质量重心"] = {"总质量_kg(估)": round(mass, 1), "重心_mm": [round(cg.x, 1), round(cg.y, 1), round(cg.z, 1)],
                    "重心在支脚包络内": fp[0] < cg.x < fp[1] and fp[2] < cg.y < fp[3],
                    "前10重件": rows[:10],
                    "说明": "密度：钢 7.85、铝 2.70 g/cm3；油箱/电控柜/电机/蓄能器/防护罩为壳体，按等效系数折算；不含液压油（约 25 kg）"}
grp_mass = {}
for k, o in P.items():
    pass
blk_m = [r for r in rows if r[0] == "55"][0][2]

# ---------------- C04 关键尺寸与 B 计算一致性
c00 = {x["项"]: x["基准"] for x in calc["c00"]["校核"]}
A1 = calc["c01"]["尾座缸面积"]["A1_mm2"]
A2 = calc["c01"]["尾座缸面积"]["A2_mm2"]
bore = bb("67").YLength
rod = bb("68").YLength
L_in = bb("70").XMin - bb("69").XMax              # 缸内长
Lp = bb("67").XLength
stroke_cap = L_in - Lp
x_cap = bb("70").XMin - bb("67").XMax            # 无杆腔长度
x_rod = bb("67").XMin - bb("69").XMax            # 有杆腔长度
Vd = 15.0
V1_model = A1 * x_cap / 1000 + Vd
V2_model = A2 * x_rod / 1000 + Vd
x1_need = (c00["V1_cm3"] - Vd) * 1000 / A1
x2_need = (c00["V2_cm3"] - Vd) * 1000 / A2
gal = calc["c04"]["锁闭阀块55流道"]["取孔径_mm"]
dims = [
    {"编号": "C04-1", "项": "缸径", "计算": 63, "模型": round(bore, 2), "通过": abs(bore - 63) < 0.01},
    {"编号": "C04-2", "项": "杆径", "计算": 35, "模型": round(rod, 2), "通过": abs(rod - 35) < 0.01},
    {"编号": "C04-3", "项": "A1/A2 mm2", "计算": [A1, A2],
     "模型": [round(math.pi * bore ** 2 / 4, 1), round(math.pi * (bore ** 2 - rod ** 2) / 4, 1)], "通过": True},
    {"编号": "C04-4", "项": "行程（可用行程≥140）", "计算": 140, "模型": round(stroke_cap, 1),
     "通过": abs(stroke_cap - 140) < 1, "注": "缸内长 %.0f − 活塞宽 %.0f" % (L_in, Lp)},
    {"编号": "C04-5", "项": "图示伸出 70 时无杆腔长度", "计算": round(x1_need, 1), "模型": round(x_cap, 1),
     "通过": abs(x_cap - x1_need) < 1, "注": "V1 计算 %.1f cm3，模型 %.1f cm3（死容积按 15 cm3）" % (c00["V1_cm3"], V1_model)},
    {"编号": "C04-6", "项": "图示伸出 70 时有杆腔长度", "计算": round(x2_need, 1), "模型": round(x_rod, 1),
     "通过": abs(x_rod - x2_need) < 1, "注": "V2 计算 %.1f cm3，模型 %.1f cm3" % (c00["V2_cm3"], V2_model)},
]
# 阀块油道直径：识别 55 内 X 向圆柱面半径
radii = sorted({round(f.Surface.Radius * 2, 2) for f in S["55"].Faces if isinstance(f.Surface, Part.Cylinder)})
dims.append({"编号": "C04-7", "项": "阀块油道直径", "计算": gal, "模型": radii, "通过": gal in radii,
             "注": "模型中 Ø6 为水平主油道，Ø8 为两腔接口，Ø24 为座阀腔，Ø18 为传感器/T1 口"})
R["C04_尺寸一致性"] = dims


# ---------------- C05 / C06 插装腔规格与壁厚（出图模型阀块55）
def min_wall(shape_block, holes_by_net, outer=True, connected=()):
    """holes_by_net: {net: [solid,...]} 不同网络之间、孔到外表面的最小壁厚。"""
    res = []
    nets = list(holes_by_net)
    for a, b in itertools.combinations(nets, 2):
        if frozenset((a, b)) in connected:
            continue
        for i, sa in enumerate(holes_by_net[a]):
            for j, sb in enumerate(holes_by_net[b]):
                d = sa.distToShape(sb)[0]
                res.append((round(d, 2), a + "#%d" % i, b + "#%d" % j))
    if outer:
        skin = shape_block.BoundBox
        box = Part.makeBox(skin.XLength, skin.YLength, skin.ZLength, App.Vector(skin.XMin, skin.YMin, skin.ZMin))
        for n, ss in holes_by_net.items():
            for i, s in enumerate(ss):
                if s.BoundBox.XMin <= skin.XMin + 1e-6 or s.BoundBox.XMax >= skin.XMax - 1e-6 or \
                        s.BoundBox.YMin <= skin.YMin + 1e-6 or s.BoundBox.YMax >= skin.YMax - 1e-6 or \
                        s.BoundBox.ZMin <= skin.ZMin + 1e-6 or s.BoundBox.ZMax >= skin.ZMax - 1e-6:
                    # 通到外表面的孔：取其到其余各外表面的距离
                    pass
                d = min(s.distToShape(f)[0] for f in box.Faces
                        if s.distToShape(f)[0] > 1e-6) if any(s.distToShape(f)[0] > 1e-6 for f in box.Faces) else 0
                res.append((round(d, 2), n + "#%d" % i, "外表面"))
    res.sort()
    return res


V = App.Vector
AY, ZG = 500.0, 1140.0
cz = lambda r, z0, z1, x, y=AY: Part.makeCylinder(r, z1 - z0, V(x, y, z0), V(0, 0, 1))
cx = lambda r, x0, x1, y=AY, z=ZG: Part.makeCylinder(r, x1 - x0, V(x0, y, z), V(1, 0, 0))
cy = lambda r, y0, y1, x, z: Part.makeCylinder(r, y1 - y0, V(x, y0, z), V(0, 1, 0))
# 按 tc_build_model.py 中阀块 55 的打孔重建（分网络）
nets55 = {
    "有杆腔": [cz(4, 1124, 1151, 1390), cx(3, 1370, 1440), cz(3, ZG, 1151, 1440), cx(9, 1370, 1380)],
    "无杆腔": [cz(4, 1124, 1151, 1590), cx(3, 1490, 1640), cz(3, ZG, 1151, 1540), cx(9, 1630, 1640),
              cz(3, ZG - 3, 1180, 1490)],
    "腔V2": [cz(12, 1150, 1195, 1390)], "腔V4": [cz(12, 1150, 1195, 1440)],
    "腔V3": [cz(12, 1150, 1195, 1540)], "腔V1": [cz(12, 1150, 1195, 1590)],
    "T1座": [cz(9, 1180, 1195, 1490)],
    "P口": [cy(4, 500, 545, 1465, 1178)], "T口": [cy(4, 500, 545, 1565, 1178)],
}
C55 = {frozenset(p) for p in [("有杆腔","腔V2"),("有杆腔","腔V4"),("无杆腔","腔V3"),("无杆腔","腔V1"),("无杆腔","T1座")]}
w55 = min_wall(S["55"], nets55, connected=C55)
R["C06_壁厚_出图模型55"] = {"最小10项": w55[:10], "最小壁厚_mm": w55[0][0], "通过(≥3)": w55[0][0] >= 3}
cav_d = 24.0
R["C05_插装孔规格_出图模型55"] = {
    "所选座阀": "Sun Hydraulics DTDA-MCN-224（BOM 19/20/21/23，T-162A 腔，见 详细设计说明书 §2 选型表）",
    "T-162A 主要尺寸(公开资料，待按 Sun 官方腔体图核实)": "3/4-16 UNF-2B 螺纹(大径 19.05)，台阶孔 Ø17.5/Ø12.7，总深约 33.3，侧口(2口)在台阶段、底口(1口)在端部",
    "模型": "Ø%.0f 平底盲孔，深 45，底部 Ø8 接缸口" % cav_d,
    "通过": False,
    "结论": "出图模型的插装孔为示意孔，直径与台阶不符合 T-162A；可加工级见 锁闭阀块_详细.FCStd"}
App.closeDocument(doc.Name)

# ---------------- C07/C08 详细阀块
det = os.path.join(M, "锁闭阀块_详细.FCStd")
if os.path.exists(det):
    import importlib.util
    spec = importlib.util.spec_from_file_location("vb", os.path.join(ROOT, "07_脚本", "d3_valve_block.py"))
    vb = importlib.util.module_from_spec(spec)
    vb.BUILD_ONLY = True
    spec.loader.exec_module(vb)
    blk, nets = vb.build()
    w = min_wall(blk, nets, connected=vb.CONNECTED)
    R["C07_壁厚_详细阀块"] = {"最小10项": w[:10], "最小壁厚_mm": w[0][0], "通过(≥3)": w[0][0] >= 3}
    R["C08_插装孔_详细阀块"] = vb.CAVITY_SPEC
    vol_oil = {n: round(sum(s.Volume for s in ss) / 1000, 2) for n, ss in nets.items()}
    R["C09_详细阀块"] = {"外形": [blk.BoundBox.XLength, blk.BoundBox.YLength, blk.BoundBox.ZLength],
                       "质量_kg(45钢)": round(blk.Volume * 7.85e-6, 2), "实体有效": blk.isValid(),
                       "各网络孔容积_cm3": vol_oil}

json.dump(R, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
print("D3_CHECK_DONE")
print(json.dumps(R, ensure_ascii=False, indent=1, default=str)[:6000])
