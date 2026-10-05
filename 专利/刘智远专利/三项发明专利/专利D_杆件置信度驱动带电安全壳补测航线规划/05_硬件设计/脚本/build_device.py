# -*- coding: utf-8 -*-
# 专利D 机载实时评估装置 FreeCAD 无界面建模脚本 (freecadcmd build_device.py)
import os, json, math, datetime
import FreeCAD as App, Part
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
MOD = os.path.join(ROOT, "模型"); os.makedirs(MOD, exist_ok=True)
V = App.Vector

def box(l, w, h, x, y, z): return Part.makeBox(l, w, h, V(x, y, z))
def cyl(r, h, x, y, z, d=V(0, 0, 1)): return Part.makeCylinder(r, h, V(x, y, z), d)

parts = {}  # 标号: (名称, shape, 爆炸偏移z, 密度g/cm3)
# 10 减振安装板(与机体快拆接口) 180x130x4 铝合金
p10 = box(180, 130, 4, -90, -65, 0)
for sx in (-75, 75):
    for sy in (-52, 52): p10 = p10.cut(cyl(3.2, 4, sx, sy, 0))
parts[10] = ("减振安装板", p10, 0, 2.7)
# 11 硅胶减振球 x4
d11 = None
for sx in (-60, 60):
    for sy in (-42, 42):
        s = Part.makeSphere(8, V(sx, sy, 12)); d11 = s if d11 is None else d11.fuse(s)
parts[11] = ("硅胶减振球(4只)", d11, 25, 1.1)
# 12 下壳体(散热底座) 150x110x30, 壁厚2.5 + 底部散热鳍片
h12 = box(150, 110, 30, -75, -55, 20).cut(box(145, 105, 28, -72.5, -52.5, 22.5))
for i in range(-6, 7):
    h12 = h12.fuse(box(2, 100, 8, i * 10 - 1, -50, 12.5)) if False else h12
parts[12] = ("下壳体", h12, 55, 2.7)
# 13 计算载板(含Jetson Orin NX模组) 103x90x1.6 + 模组70x45x5
b13 = box(103, 90, 1.6, -60, -45, 26).fuse(box(70, 45, 5, -50, -22.5, 27.6))
parts[13] = ("计算载板与边缘计算模组", b13, 80, 2.0)
# 14 散热器+风扇 70x50x14 鳍片
f14 = box(72, 50, 3, -51, -25, 32.6)
for i in range(9): f14 = f14.fuse(box(1.5, 50, 11, -50 + i * 8.5, -25, 35.6))
parts[14] = ("均热板散热器与风扇", f14, 110, 2.7)
# 15 接口与电源板(以太网/MAVLink/电场采集ADC/DC-DC) 40x90
parts[15] = ("接口与电源板", box(40, 90, 1.6, 47, -45, 26).fuse(box(30, 20, 6, 52, -10, 27.6)), 80, 2.0)
# 16 4G/图传模块 52x30x6
parts[16] = ("4G/图传回传模块", box(52, 30, 6, 47, 20, 40), 125, 2.0)
# 17 上盖(带进/出风格栅) 150x110x20
c17 = box(150, 110, 20, -75, -55, 50).cut(box(145, 105, 17.5, -72.5, -52.5, 50))
for i in range(8): c17 = c17.cut(box(4, 50, 3, -48 + i * 8.5, -25, 67.5))
parts[17] = ("上盖(进风格栅)", c17, 160, 2.7)
# 18 侧面航插接口(激光雷达以太网/飞控/电源) 3只
c18 = None
for k, y in enumerate((-30, 0, 30)):
    s = cyl(7, 12, 75, y, 35, V(1, 0, 0)); c18 = s if c18 is None else c18.fuse(s)
parts[18] = ("侧面航空插头组", c18, 55, 7.8)
# 19 绝缘桅杆(玻纤管) 直径12 长120, 20 工频电场传感头(球形双电极) 直径50
parts[19] = ("绝缘桅杆", cyl(6, 120, -55, 0, 70), 200, 1.9)
e20 = Part.makeSphere(25, V(-55, 0, 215)).cut(box(60, 60, 2, -85, -30, 214))
parts[20] = ("工频电场传感头(分体球电极)", e20, 230, 1.2)
# 21 天线 x2
a21 = cyl(4, 80, 60, 45, 70).fuse(cyl(4, 80, 60, -45, 70))
parts[21] = ("4G/图传天线", a21, 200, 1.5)

doc = App.newDocument("PatentD_Device")
rec = {"time": datetime.datetime.now().isoformat(), "freecad": App.Version()[:3], "parts": []}
edges = {"assembled": {}, "exploded": {}}
def proj(p):  # 等轴测投影
    a, b = math.radians(30), math.radians(30)
    return [(p.x - p.y) * math.cos(a), p.z + (p.x + p.y) * math.sin(b) * 0.5]
tot = 0
for k, (nm, sh, dz, rho) in parts.items():
    o = doc.addObject("Part::Feature", "P%d" % k); o.Label = "%d_%s" % (k, nm); o.Shape = sh
    m = sh.Volume / 1000 * rho; tot += m
    bb = sh.BoundBox
    rec["parts"].append({"ref": k, "name": nm, "volume_mm3": round(sh.Volume, 1), "mass_g": round(m, 1),
                         "bbox_mm": [round(bb.XLength, 1), round(bb.YLength, 1), round(bb.ZLength, 1)]})
    for key, off in (("assembled", 0), ("exploded", dz)):
        lines = []
        s2 = sh.copy(); s2.translate(V(0, 0, off))
        for e in s2.Edges:
            try:
                if e.Length < 1e-6: continue
                pts = e.discretize(24)
            except Exception:
                continue
            lines.append([proj(p) for p in pts])
        edges[key][str(k)] = lines
doc.recompute()
fc = os.path.join(MOD, "机载实时评估装置.FCStd"); doc.saveAs(fc)
import Import
Import.export(doc.Objects, os.path.join(MOD, "机载实时评估装置.step"))
comp = Part.makeCompound([p[1] for p in parts.values()]); bb = comp.BoundBox
rec["envelope_mm"] = [round(bb.XLength, 1), round(bb.YLength, 1), round(bb.ZLength, 1)]
rec["structural_mass_g_est"] = round(tot, 1)
rec["outputs"] = ["模型/机载实时评估装置.FCStd", "模型/机载实时评估装置.step", "模型/edges_iso.json"]
json.dump(edges, open(os.path.join(MOD, "edges_iso.json"), "w"))
json.dump(rec, open(os.path.join(MOD, "构建记录.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("OK", rec["envelope_mm"], rec["structural_mass_g_est"])
