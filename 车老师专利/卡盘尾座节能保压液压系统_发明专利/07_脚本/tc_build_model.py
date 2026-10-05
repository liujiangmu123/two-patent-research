# -*- coding: utf-8 -*-
"""试验台出图模型构建（freecadcmd 无头运行）。

以 04_模型/试验台三维简化模型.FCStd（09 初稿模型的副本）为底稿，清除旧的方块示意体，按同一总体布置
（外形 1800×860×1360、台面高 850、模拟主轴中心高 1080，轴线 Y=500）重建为出图用的结构表达模型。
每个零件为 Part::Feature，带属性 PartNo（件号，供 numerals_structure.json 的 rep 引用）、Kind、Material、Structure。
坐标：X 沿床身（卡盘在 −X 端、尾座缸在 +X 端），Y 由前向后（Y=0 为台架前沿），Z 向上。单位 mm。
输出：04_模型/试验台出图模型.FCStd、试验台出图模型.step。

    freecadcmd -c "exec(open(r'...\\tc_build_model.py', encoding='utf-8').read())"
"""
import os
import FreeCAD as App
import Part

V = App.Vector
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) if "__file__" in globals() else \
    r"H:\Axinjihua\02动画项目\05动画Harness工作台\专利文档资料\车老师专利\卡盘尾座节能保压液压系统_发明专利"
SRC = os.path.join(ROOT, "04_模型", "试验台三维简化模型.FCStd")
OUT = os.path.join(ROOT, "04_模型", "试验台出图模型.FCStd")
STEP = os.path.join(ROOT, "04_模型", "试验台出图模型.step")

AY, AZ = 500.0, 1080.0          # 模拟主轴轴线


def box(x0, x1, y0, y1, z0, z1):
    return Part.makeBox(x1 - x0, y1 - y0, z1 - z0, V(x0, y0, z0))


def cylX(r, x0, x1, y=AY, z=AZ):
    return Part.makeCylinder(r, x1 - x0, V(x0, y, z), V(1, 0, 0))


def cylY(r, y0, y1, x, z=AZ):
    return Part.makeCylinder(r, y1 - y0, V(x, y0, z), V(0, 1, 0))


def cylZ(r, z0, z1, x, y=AY):
    return Part.makeCylinder(r, z1 - z0, V(x, y, z0), V(0, 0, 1))


def coneX(r0, r1, x0, x1, y=AY, z=AZ):
    return Part.makeCone(r0, r1, x1 - x0, V(x0, y, z), V(1, 0, 0))


def prismXY(pts, z0, z1):
    w = Part.makePolygon([V(x, y, z0) for x, y in pts] + [V(pts[0][0], pts[0][1], z0)])
    return Part.Face(w).extrude(V(0, 0, z1 - z0))


def fuse(*ss):
    s = ss[0]
    for t in ss[1:]:
        s = s.fuse(t)
    return s.removeSplitter()


PARTS = []      # (PartNo, 名称, 组, Kind, Material, shape)


def add(pno, name, grp, shape, kind="零件", mat="钢"):
    PARTS.append((pno, name, grp, kind, mat, shape))


# ------------------------------------------------------------------ 41 机架（型材框架）与 42 台面板
legs = [(0, 0), (1740, 0), (0, 740), (1740, 740), (870, 0), (870, 740)]
add("41", "机架", "机架", fuse(*[box(x, x + 60, y, y + 60, 0, 790) for x, y in legs],
                               box(0, 1800, 0, 60, 790, 850), box(0, 1800, 740, 800, 790, 850),
                               box(0, 60, 60, 740, 790, 850), box(1740, 1800, 60, 740, 790, 850),
                               box(0, 1800, 0, 60, 100, 150), box(0, 1800, 740, 800, 100, 150),
                               box(0, 60, 60, 740, 100, 150), box(1740, 1800, 60, 740, 100, 150)))
add("41a", "底层搁板", "机架", box(60, 1740, 60, 740, 150, 160))
add("41f", "调整脚", "机架", fuse(*[cylZ(30, -40, 0, x + 30, y + 30) for x, y in legs]))
add("42", "台面板", "机架", box(0, 1800, 0, 800, 850, 870))
add("43", "模拟床身", "机架", fuse(box(200, 1650, 380, 620, 870, 915), box(200, 1650, 400, 600, 915, 930)))

# ------------------------------------------------------------------ 卡盘模拟单元
add("12", "卡盘液压缸", "卡盘", fuse(cylX(65, 150, 290), cylX(55, 140, 150), cylX(55, 290, 300)))
add("12r", "卡盘缸拉杆", "卡盘", cylX(12.5, 300, 340))
add("12s", "卡盘缸支座", "卡盘", fuse(box(160, 280, 440, 560, 930, 950), box(200, 240, 450, 550, 950, 1018)))
add("44", "夹紧力传感器", "卡盘", fuse(*[coneX(35 if i % 2 == 0 else 15, 15 if i % 2 == 0 else 35, 304 + 6 * i, 310 + 6 * i)
                                         for i in range(5)]))
add("45", "主轴箱模拟座", "卡盘", box(340, 520, 400, 600, 930, 1180).cut(cylX(14, 339, 521)))
jaws = []
import math
for a in (90.0, 210.0, 330.0):
    t = math.radians(a)
    j = box(580, 605, -10, 10, 30, 92)
    j.rotate(V(0, 0, 0), V(1, 0, 0), a - 90.0)
    j.translate(V(0, AY, AZ))
    jaws.append(j)
add("46", "模拟卡盘", "卡盘", fuse(cylX(100, 520, 580), *jaws))
add("15", "回转接头泄漏模拟针阀", "卡盘", fuse(box(375, 425, 375, 425, 1180, 1205), cylZ(9, 1205, 1225, 400, 400),
                                               cylZ(16, 1225, 1240, 400, 400), cylY(6, 340, 375, 400, 1192)))

# ------------------------------------------------------------------ 微位移加载单元（伺服电机—丝杠—楔块—导轨—滑块）
K = 0.1                                       # 楔块斜率 1:10（位移缩小比 ≥1:10）
add("48", "加载座", "加载", fuse(box(600, 750, 430, 660, 930, 960), box(600, 640, 440, 560, 960, 1140),
                                box(635, 700, 640, 665, 960, 1080)).cut(cylY(10, 630, 670, 667, 1040)))
wedge = prismXY([(640, 430), (640, 630), (670 + K * 200, 630), (670, 430)], 962, 1120)
add("63", "楔块", "加载", wedge.cut(cylY(8.5, 420, 640, 667, 1040)))
fol = prismXY([(671 + K * 10, 440), (740, 440), (740, 560), (671 + K * 130, 560)], 962, 1120)
add("64", "从动楔座", "加载", fol)
add("62", "滚珠丝杠", "加载", cylY(8, 470, 660, 667, 1040))
add("65", "联轴器", "加载", cylY(16, 660, 680, 667, 1040))
add("47", "伺服电机", "加载", fuse(box(627, 707, 680, 695, 1000, 1080), box(632, 702, 695, 770, 1005, 1075),
                                 box(650, 685, 770, 782, 1020, 1060)))
add("47b", "电机支架", "加载", box(622, 712, 680, 785, 870, 1000))
add("50", "直线导轨", "加载", fuse(box(760, 970, 455, 475, 930, 948), box(760, 970, 525, 545, 930, 948)))
add("50c", "导轨滑块", "加载", fuse(*[box(x, x + 45, y, y + 34, 948, 965) for x in (778, 845) for y in (448, 518)]))
add("49", "推力传感器", "加载", fuse(cylX(28, 742, 768), cylX(12, 740, 742), cylX(12, 768, 770),
                                   cylY(5, 460, 472, 755, 1108)))
slider = fuse(box(770, 900, 440, 560, 965, 1140), box(860, 900, 410, 440, 1100, 1140))
add("51", "工件模拟滑块", "加载", slider.cut(coneX(0.1, 22, 878, 900)))
add("56", "位移传感器", "加载", fuse(cylX(10, 922, 1035, 425, 1120), cylX(3, 900, 922, 425, 1120)))
add("56b", "位移传感器支架", "加载", fuse(box(1035, 1055, 405, 445, 930, 1140)))

# ------------------------------------------------------------------ 尾座单元
add("52", "顶尖", "尾座", fuse(coneX(0.1, 20, 880, 920), cylX(20, 920, 990)))
add("53", "尾座套筒", "尾座", cylX(30, 990, 1205))
add("54", "尾座体", "尾座", fuse(box(1130, 1330, 400, 600, 930, 965), box(1140, 1320, 420, 580, 965, 1160),
                               box(1130, 1330, 400, 600, 1160, 1200)).cut(cylX(30.5, 1129, 1331)))
add("54h", "套筒锁紧手柄", "尾座", fuse(cylZ(8, 1200, 1250, 1230, 520), cylY(6, 450, 520, 1230, 1245),
                                    Part.makeSphere(12, V(1230, 445, 1245))))
# 26 尾座液压缸：方形缸体（便于阀块直装），缸径 63、杆径 35、行程 140，图示伸出 70
add("69", "前端盖", "尾座缸", box(1340, 1370, 455, 545, 1035, 1125).cut(cylX(17.6, 1339, 1371)))
bar = box(1370, 1610, 455, 545, 1035, 1125).cut(cylX(31.5, 1369, 1611))
for x in (1390, 1590):                             # 两腔油口直通阀块（无软管）
    bar = bar.cut(cylZ(4, 1090, 1126, x))
add("66", "缸筒", "尾座缸", bar)
add("70", "后端盖", "尾座缸", box(1610, 1640, 455, 545, 1035, 1125))
add("67", "活塞", "尾座缸", cylX(31.5, 1500, 1530).cut(Part.makeTorus(31.5, 2.2, V(1515, AY, AZ), V(1, 0, 0))))
add("68", "活塞杆", "尾座缸", cylX(17.5, 1205, 1500))
add("26s", "尾座缸支座", "尾座缸", box(1385, 1595, 465, 535, 930, 1025))
# 61 温控夹套：包覆缸筒两侧与底面
jk = box(1380, 1600, 445, 555, 1025, 1120).cut(box(1385, 1595, 450, 550, 1030, 1121))
add("61", "温控夹套", "尾座缸", jk.cut(box(1379, 1601, 455, 545, 1035, 1126)))
add("74", "温控介质接口", "尾座缸", fuse(cylY(6, 425, 445, 1400, 1050), cylY(6, 425, 445, 1580, 1050)))
# 55 锁闭阀块：直装缸体顶面（跨缸筒与后端盖），内部油道直通两腔，锁闭腔内无软管
ZG = 1140.0                                        # 阀块内水平油道高度
blk = box(1370, 1640, 455, 545, 1125, 1195)
CAV = {"20": 1390, "23": 1440, "21": 1540, "19": 1590}
for x in CAV.values():
    blk = blk.cut(cylZ(12, 1150, 1196, x))
for x in (1390, 1590):
    blk = blk.cut(cylZ(4, 1124, 1151, x))
blk = blk.cut(cylX(3, 1360, 1440, AY, ZG)).cut(cylX(3, 1490, 1641, AY, ZG))
blk = blk.cut(cylZ(3, ZG, 1151, 1440)).cut(cylZ(3, ZG, 1151, 1540))
blk = blk.cut(cylX(9, 1369, 1380, AY, ZG)).cut(cylX(9, 1630, 1641, AY, ZG))     # S3、S2 螺纹孔
blk = blk.cut(cylZ(3, ZG - 3, 1196, 1490)).cut(cylZ(9, 1180, 1196, 1490))       # T1 安装孔
for x in (1465, 1565):                             # 外接油口 P、T（后侧面）
    blk = blk.cut(cylY(4, 500, 546, x, 1178))
add("55", "锁闭阀块", "尾座缸", blk)
NAMES = {"19": "第一锁闭座阀V1", "20": "第二锁闭座阀V2", "21": "微泄座阀V3", "23": "预压座阀V4"}
for k, x in CAV.items():
    v = fuse(cylZ(9, 1150, 1158, x), cylZ(12, 1158, 1195, x), cylZ(9, 1195, 1205, x))
    v = v.cut(cylZ(4, 1149, 1185, x))
    add(k, NAMES[k], "尾座缸", v)
    add(k + "p", NAMES[k] + "阀芯", "尾座缸", fuse(Part.makeCone(1.5, 4.5, 6, V(x, AY, 1151), V(0, 0, 1)),
                                                 cylZ(4, 1157, 1185, x)))
    add(k + "c", NAMES[k] + "电磁线圈", "尾座缸", fuse(cylZ(19, 1205, 1255, x), cylZ(7, 1255, 1268, x)))
add("22", "阻尼孔", "尾座缸", cylZ(3, ZG + 3, 1150, 1540).cut(cylZ(0.8, ZG + 2, 1151, 1540)))
add("25", "有杆腔压力传感器S3", "尾座缸", fuse(cylX(9, 1369, 1380, AY, ZG).cut(cylX(3, 1368, 1381, AY, ZG)),
                                               cylX(11, 1349, 1369, AY, ZG), cylX(7, 1336, 1349, AY, ZG)))
add("24", "无杆腔压力传感器S2", "尾座缸", fuse(cylX(9, 1630, 1641, AY, ZG).cut(cylX(3, 1629, 1642, AY, ZG)),
                                               cylX(11, 1641, 1661, AY, ZG), cylX(7, 1661, 1674, AY, ZG)))
add("30", "油温传感器T1", "尾座缸", fuse(cylZ(2.5, ZG - 2, 1180, 1490), cylZ(9, 1180, 1196, 1490),
                                         cylZ(8, 1196, 1222, 1490), cylZ(6, 1222, 1240, 1490)))
add("73", "外接油口接头", "尾座缸", fuse(cylY(9, 545, 568, 1465, 1178).cut(cylY(4, 544, 569, 1465, 1178)),
                                      cylY(9, 545, 568, 1565, 1178).cut(cylY(4, 544, 569, 1565, 1178))))

# ------------------------------------------------------------------ 57 安全防护罩（型材框 + 后板，前后侧为透明板，图中不画板面）
gx0, gx1, gy0, gy1, gz0, gz1, b = 330, 1700, 320, 795, 870, 1360, 30
gr = [box(x, x + b, y, y + b, gz0, gz1) for x in (gx0, gx1 - b) for y in (gy0, gy1 - b)]
gr += [box(gx0, gx1, y, y + b, gz1 - b, gz1) for y in (gy0, gy1 - b)]
gr += [box(x, x + b, gy0, gy1, gz1 - b, gz1) for x in (gx0, gx1 - b)]
gr += [box(gx0, gx1, gy1 - b, gy1, gz0, gz0 + b)]
add("57", "安全防护罩", "防护", fuse(*gr))
add("57p", "防护罩后板", "防护", box(gx0 + b, gx1 - b, gy1 - 6, gy1, gz0 + b, gz1 - b))
add("57t", "防护门导轨", "防护", box(gx0, gx1, 300, 320, 1340, 1360))
door = box(400, 1600, 302, 318, 885, 1335).cut(box(430, 1570, 301, 319, 915, 1305))
add("58", "防护前门", "防护", door)
add("58h", "门把手", "防护", fuse(box(1540, 1550, 290, 302, 1080, 1090), box(1540, 1550, 290, 302, 1200, 1210),
                               box(1540, 1550, 284, 290, 1080, 1210)))
add("59", "门联锁开关", "防护", fuse(box(1700, 1740, 290, 330, 1260, 1330)))
add("59k", "联锁钥匙", "防护", box(1600, 1700, 304, 316, 1285, 1305))

# ------------------------------------------------------------------ 电控
add("27", "电控柜", "电控", box(20, 180, 40, 300, 870, 1300))
add("28", "触摸屏", "电控", box(40, 160, 30, 40, 1150, 1260))
add("76", "急停按钮", "电控", fuse(cylY(10, 26, 40, 100, 1080), cylY(18, 14, 26, 100, 1080)))

# ------------------------------------------------------------------ 75 液压站（底层搁板上）与 60 阀板
add("1", "油箱", "液压站", box(100, 700, 250, 650, 160, 440))
add("4", "电动机", "液压站", fuse(cylX(80, 180, 440, 450, 545), cylX(30, 160, 180, 450, 545), cylX(95, 440, 455, 450, 545)))
add("4b", "电机底座", "液压站", box(200, 420, 380, 520, 440, 465))
add("3", "定量液压泵", "液压站", fuse(cylX(60, 455, 490, 450, 545), box(490, 600, 400, 500, 495, 595)))
add("2", "吸油过滤器", "液压站", fuse(cylZ(25, 440, 510, 150, 600), cylZ(30, 510, 520, 150, 600)))
add("5", "溢流阀", "液压站", fuse(box(600, 690, 280, 360, 440, 500), cylX(12, 690, 730, 320, 470)))
add("8", "蓄能器", "液压站", fuse(cylZ(57, 160, 500, 820, 450), Part.makeSphere(57, V(820, 450, 500)).common(
    box(700, 940, 330, 570, 500, 560)), cylZ(15, 557, 580, 820, 450)))
add("60", "阀板", "阀板", box(940, 1700, 20, 40, 200, 800))
for pno, nm, x0, x1, z0, z1, sol in (("11", "卡盘换向阀", 980, 1120, 650, 710, True),
                                     ("18", "尾座换向阀", 1280, 1420, 650, 710, True),
                                     ("10", "卡盘减压阀", 1000, 1080, 540, 600, False),
                                     ("16", "尾座减压阀R1", 1260, 1340, 540, 600, False),
                                     ("17", "预压减压阀R2", 1370, 1450, 540, 600, False),
                                     ("6", "电磁卸荷阀", 1110, 1190, 440, 500, False),
                                     ("7", "单向阀", 980, 1050, 450, 490, False),
                                     ("29", "隔离座阀V0", 1480, 1540, 440, 500, False)):
    s = box(x0, x1, -20, 20, z0, z1)
    if sol:
        s = fuse(s, cylX(25, x0 - 45, x0, 0, 0.5 * (z0 + z1)), cylX(25, x1, x1 + 45, 0, 0.5 * (z0 + z1)))
    else:
        s = fuse(s, cylY(12, -50, -20, 0.5 * (x0 + x1), 0.5 * (z0 + z1)))
    add(pno, nm, "阀板", s)
add("9", "压力传感器与压力表组", "阀板", fuse(*[fuse(cylY(6, -15, 20, x, 300), cylY(25, -35, -15, x, 300))
                                              for x in (1560, 1630)]))


# ------------------------------------------------------------------ 写入文档
def main():
    doc = App.openDocument(SRC)
    for o in list(doc.Objects):
        try:
            doc.removeObject(o.Name)
        except Exception:  # noqa: BLE001
            pass
    groups = {}
    for pno, name, grp, kind, mat, shp in PARTS:
        g = groups.get(grp)
        if g is None:
            g = groups[grp] = doc.addObject("App::DocumentObjectGroup", "G_" + str(len(groups)))
            g.Label = grp
        o = doc.addObject("Part::Feature", "P_" + pno)
        o.Shape = shp
        o.Label = "%s_%s" % (pno, name)
        for prop, val in (("PartNo", pno), ("Kind", kind), ("Material", mat), ("Structure", pno),
                          ("PartName", name), ("Group_", grp)):
            o.addProperty("App::PropertyString", prop, "Patent")
            setattr(o, prop, val)
        g.addObject(o)
    doc.recompute()
    doc.saveAs(OUT)
    Part.export([o for o in doc.Objects if o.TypeId == "Part::Feature"], STEP)
    bad = [o.Label for o in doc.Objects if o.TypeId == "Part::Feature" and (not o.Shape.isValid() or not o.Shape.Solids)]
    print("TC_BUILD_DONE n=%d bad=%s" % (len(PARTS), bad))
    App.closeDocument(doc.Name)


main()
