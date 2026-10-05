# -*- coding: utf-8 -*-
# 专利E 地面同步测振相机装置 参数化建模（freecadcmd 无界面执行）
import os, json, math, datetime
import FreeCAD as App, Part
from FreeCAD import Vector as V

BASE = os.environ.get("PE_BASE") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MOD = os.path.join(BASE, "模型")
os.makedirs(MOD, exist_ok=True)

# 部件定义：编号, 名称, 形体, 质量kg（估算）
parts = []
def add(no, name, shp, mass, explode=(0, 0, 0)):
    parts.append(dict(no=no, name=name, shp=shp, mass=mass, ex=explode))

H0 = 1200.0  # 三脚架顶面高度 mm
# 地钉基座 + 三脚架腿（31）
legs = None
for k in range(3):
    a = math.radians(90 + 120 * k)
    foot = V(650 * math.cos(a), 650 * math.sin(a), 0)
    top = V(60 * math.cos(a), 60 * math.sin(a), H0 - 40)
    d = top.sub(foot)
    leg = Part.makeCylinder(16, d.Length, foot, d)
    spike = Part.makeCone(20, 2, 180, foot.sub(V(0, 0, 180)), V(0, 0, 1))
    pad = Part.makeCylinder(70, 12, foot.sub(V(0, 0, 12)))
    s = leg.fuse(spike).fuse(pad)
    legs = s if legs is None else legs.fuse(s)
add(31, "水平调节三脚架及地钉基座", legs, 6.5, (0, 0, -300))
# 调平基座（32）：三螺钉调平盘 + 水准泡
lev = Part.makeCylinder(110, 40, V(0, 0, H0 - 40))
for k in range(3):
    a = math.radians(30 + 120 * k)
    lev = lev.fuse(Part.makeCylinder(12, 60, V(85 * math.cos(a), 85 * math.sin(a), H0 - 50)))
lev = lev.fuse(Part.makeCylinder(80, 20, V(0, 0, H0)))
lev = lev.cut(Part.makeSphere(14, V(60, 0, H0 + 24)))
add(32, "三螺钉调平基座", lev, 1.2, (0, 0, -150))
# 双轴云台（33）：方位转台 + U形叉架 + 俯仰轴
z1 = H0 + 20
pan = Part.makeCylinder(90, 70, V(0, 0, z1))
fork = Part.makeBox(240, 180, 20, V(-120, -90, z1 + 70))
fork = fork.fuse(Part.makeBox(240, 20, 220, V(-120, -110, z1 + 70)))
fork = fork.fuse(Part.makeBox(240, 20, 220, V(-120, 90, z1 + 70)))
tilt = Part.makeCylinder(25, 300, V(0, -150, z1 + 230), V(0, 1, 0))
add(33, "双轴云台（方位/俯仰电机与编码器）", pan.fuse(fork).fuse(tilt), 3.8, (0, 0, 0))
# 相机托板（34）
zc = z1 + 230
plate = Part.makeBox(420, 150, 12, V(-200, -75, zc - 70))
add(34, "相机快装托板", plate, 0.4, (0, 0, 120))
# 工业相机机身（11）
cam = Part.makeBox(60, 60, 60, V(-30, -30, zc - 58))
cam = cam.fuse(Part.makeCylinder(8, 20, V(-50, 0, zc - 28), V(1, 0, 0)))  # 接口
add(11, "全局快门高帧率工业相机", cam, 0.3, (0, 0, 250))
# 长焦镜头（12）
lens = Part.makeCylinder(42, 180, V(30, 0, zc - 28), V(1, 0, 0))
lens = lens.fuse(Part.makeCylinder(48, 40, V(170, 0, zc - 28), V(1, 0, 0)))
add(12, "长焦定焦镜头", lens, 0.9, (350, 0, 250))
# IMU（13）贴装于相机托板背面
imu = Part.makeBox(40, 40, 18, V(-150, -20, zc - 58))
add(13, "惯性测量单元IMU", imu, 0.05, (-150, 0, 300))
# 遮阳/防风罩（14）：壳体带前窗
hood = Part.makeBox(440, 170, 150, V(-210, -85, zc - 60))
hood = hood.cut(Part.makeBox(430, 160, 145, V(-205, -80, zc - 58)))
hood = hood.cut(Part.makeCylinder(52, 20, V(220, 0, zc - 28), V(1, 0, 0)).translate(V(-15, 0, 0)))
roof = Part.makeBox(520, 230, 6, V(-250, -115, zc + 95))
add(14, "遮阳防风罩（前置光学窗）", hood.fuse(roof), 1.6, (0, 0, 600))
# GNSS 授时天线（21）
ant = Part.makeCylinder(8, 120, V(-180, 0, zc + 101))
ant = ant.fuse(Part.makeCylinder(45, 25, V(-180, 0, zc + 221)))
add(21, "GNSS授时天线", ant, 0.25, (0, 0, 850))
# 边缘计算盒（22）挂于三脚架中柱
box = Part.makeBox(220, 160, 70, V(-110, -80, 700))
fins = None
for i in range(8):
    f = Part.makeBox(4, 160, 15, V(-100 + 27 * i, -80, 770))
    fins = f if fins is None else fins.fuse(f)
add(22, "边缘计算盒（含GNSS授时模块与触发板）", box.fuse(fins), 2.2, (400, 0, 0))
# 电池箱（23）
bat = Part.makeBox(300, 200, 180, V(-150, -100, 30))
bat = bat.fuse(Part.makeBox(120, 20, 30, V(-60, -10, 210)))
add(23, "锂电池箱（含电源管理）", bat, 7.0, (0, -500, 0))
# 太阳能板（24）斜置支架
sp = Part.makeBox(670, 540, 30, V(0, 0, 0))
sp.rotate(V(0, 0, 0), V(1, 0, 0), 35)
sp.translate(V(-335, -1250, 300))
st = Part.makeCylinder(15, 450, V(0, -1000, 0))
add(24, "太阳能板及支架", sp.fuse(st), 5.5, (0, -400, 0))

doc = App.newDocument("CameraStation")
rec = []
edges_out = {}
for p in parts:
    o = doc.addObject("Part::Feature", "P%d" % p["no"])
    o.Label = "%d_%s" % (p["no"], p["name"])
    o.Shape = p["shp"]
    bb = p["shp"].BoundBox
    rec.append(dict(编号=p["no"], 名称=p["name"], 估算质量kg=p["mass"],
                    包围盒mm=[round(bb.XLength), round(bb.YLength), round(bb.ZLength)]))
    pl = []
    for e in p["shp"].Edges:
        try:
            pts = e.discretize(Deflection=2.0) if e.Length > 1 else []
        except Exception:
            pts = []
        if len(pts) >= 2:
            pl.append([[q.x, q.y, q.z] for q in pts])
    edges_out[p["no"]] = dict(name=p["name"], edges=pl, explode=list(p["ex"]),
                              center=[bb.Center.x, bb.Center.y, bb.Center.z])
doc.recompute()
fc = os.path.join(MOD, "地面同步测振相机装置.FCStd")
doc.saveAs(fc)
import Import
Import.export(doc.Objects, os.path.join(MOD, "地面同步测振相机装置.step"))
with open(os.path.join(MOD, "edges.json"), "w", encoding="utf-8") as f:
    json.dump(edges_out, f)
allbb = doc.Objects[0].Shape.BoundBox
for o in doc.Objects[1:]:
    allbb.add(o.Shape.BoundBox)
json.dump(dict(时间=datetime.datetime.now().isoformat(timespec="seconds"),
               FreeCAD=".".join(App.Version()[:3]), 部件=rec,
               总质量kg=round(sum(p["mass"] for p in parts), 2),
               整机包络mm=[round(allbb.XLength), round(allbb.YLength), round(allbb.ZLength)],
               输出=["地面同步测振相机装置.FCStd", "地面同步测振相机装置.step"]),
          open(os.path.join(MOD, "构建记录.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)
print("OK", len(parts))
