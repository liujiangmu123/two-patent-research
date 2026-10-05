# -*- coding: utf-8 -*-
"""专利A 同步采集载荷 三维结构模型（freecadcmd 无界面执行）
运行: freecadcmd.exe build_model.py
坐标: X=航向(前), Y=左, Z=上; 原点=快拆接口下表面中心(无人机云台接口面)。单位 mm / g。
输出: ../模型/专利A_同步采集载荷.FCStd, .step, 构建记录.json, _proj.json(投影线, 供 render_figs.py 出图)
"""
import os, json, math
import FreeCAD as App, Part, TechDraw
V = App.Vector
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.normpath(os.path.join(HERE, '..', '模型'))
os.makedirs(OUT, exist_ok=True)

TILT = 0.0          # 激光头当前俯仰角(°), 机构行程 ±30°
ZC = -160.0         # 耳轴(俯仰轴)中心高度
DENS = {'6061-T6铝合金': 2.70e-3, '碳纤维板T700': 1.60e-3, '硅橡胶': 1.15e-3, 'PA12+30%GF': 1.30e-3,
        '40Cr钢(调质)': 7.85e-3, '锡青铜ZCuSn10P1': 8.80e-3, 'PVC/FEP线缆(折算)': 2.0e-3}
parts = []  # dict(no, name, shape, material, mass_g(None->按体积), src)

def box(lx, ly, lz, x0, y0, z0):
    return Part.makeBox(lx, ly, lz, V(x0, y0, z0))
def cyl(r, h, p, d):
    return Part.makeCylinder(r, h, V(*p), V(*d))
def add(no, name, shp, mat, mass=None, src='', spec=''):
    parts.append(dict(no=no, name=name, shape=shp, material=mat, mass=mass, src=src, spec=spec))
def rot_tilt(shp):
    s = shp.copy(); s.rotate(V(0, 0, ZC), V(0, 1, 0), TILT); return s
def tube(pts, r=3.0):
    sh = []
    for a, b in zip(pts[:-1], pts[1:]):
        a, b = V(*a), V(*b); d = b - a
        sh.append(Part.makeCylinder(r, d.Length, a, d))
        sh.append(Part.makeSphere(r, b))
    s = sh[0]
    for t in sh[1:]: s = s.fuse(t)
    return s.removeSplitter()

# ---- 1 挂架(上板) / 11 快拆 / 12 减振器 ----
hp = box(220, 180, 6, -110, -90, -6)
for x, y in [(80, 65), (80, -65), (-80, 65), (-80, -65)]:
    hp = hp.cut(cyl(4.2, 6, (x, y, -6), (0, 0, 1)))
hp = hp.cut(box(120, 60, 6, -60, -30, -6))  # 减重窗
add(1, '挂架上板', hp, '碳纤维板T700', spec='220×180×6')
qr = cyl(45, 12, (0, 0, 0), (0, 0, 1)).fuse(cyl(32, 8, (0, 0, 12), (0, 0, 1))).cut(cyl(36, 9, (0, 0, 3), (0, 0, 1))).cut(cyl(24, 8, (0, 0, 12), (0, 0, 1)))
for k in range(3):  # 卡口凸耳
    a = math.radians(120 * k)
    lug = box(14, 10, 4, 30, -5, 16); lug.rotate(V(0, 0, 0), V(0, 0, 1), 120 * k); qr = qr.fuse(lug)
add(11, '快拆接口(卡口式, 含12芯弹簧针电连接器)', qr, '6061-T6铝合金', spec='Φ90×20, 3瓣卡口')
for i, (x, y) in enumerate([(80, 65), (80, -65), (-80, 65), (-80, -65)]):
    add(12, f'减振器{i+1}(硅橡胶球形阻尼)', cyl(11, 40, (x, y, -46), (0, 0, 1)), '硅橡胶', spec='Φ22×40, 邵氏40A')

# ---- 2 主框架: 下板 + 两侧耳板(叉架) ----
lp = box(420, 170, 6, -210, -85, -52)
lp = lp.cut(box(100, 70, 6, -50, -35, -52)).cut(cyl(22, 6, (160, 0, -52), (0, 0, 1)))
add(2, '主框架下板', lp, '碳纤维板T700', spec='420×170×6')
for s in (1, -1):
    y0 = 56 if s > 0 else -62
    ear = box(100, 6, 150, -50, y0, -202)
    ear = ear.cut(cyl(9, 6, (0, y0, ZC), (0, 1, 0)))
    add(2, '主框架耳板' + ('L' if s > 0 else 'R'), ear, '6061-T6铝合金', spec='100×6×150, 轴孔Φ18')

# ---- 3 激光扫描头(miniVUX-3UAV, 243×99×85, 1.55 kg 无风扇) + 7 INS 刚性固定于其上 ----
sc = box(243, 99, 85, -121.5, -49.5, ZC - 42.5)
win = cyl(30, 99, (60, -49.5, ZC - 42.5), (0, 1, 0))  # 扫描窗示意(圆柱外凸)
sc = sc.fuse(win.common(box(80, 99, 20, 20, -49.5, ZC - 62.5)))
add(3, '激光扫描头(RIEGL miniVUX-3UAV)', rot_tilt(sc), '外购件', 1550,
    'S02 RIEGL miniVUX-3UAV规格书: 243×99×85 mm, approx.1.55 kg(无风扇), 11–34 V DC typ.18 W, FOV 360°, 最小量程3 m',
    '243×99×85')
ins = box(67, 60, 15, -33.5, -30, ZC + 42.5)
add(7, 'GNSS/INS(Applanix APX-15 UAV级)', rot_tilt(ins), '外购件', 60,
    '型号尺寸/质量为厂商公开值, 待原始规格书核对', '67×60×15')

# ---- 4 倾角调节机构 ----
for s in (1, -1):
    y0 = 49.5 if s > 0 else -76
    add(41, '耳轴' + ('L' if s > 0 else 'R'), cyl(8, 26.5, (0, y0, ZC), (0, 1, 0)), '40Cr钢(调质)', spec='Φ16, 双列角接触轴承支承')
wg = cyl(30, 10, (0, 64, ZC), (0, 1, 0)).cut(cyl(8, 10, (0, 64, ZC), (0, 1, 0)))
add(43, '蜗轮(z=60, m=1)', rot_tilt(wg), '锡青铜ZCuSn10P1', spec='Φ60×10, 速比60:1 自锁')
add(43, '蜗杆', cyl(6, 60, (-30, 69, ZC + 36), (1, 0, 0)), '40Cr钢(调质)', spec='Φ12×60, 导程角<4°自锁')
add(43, '蜗杆支座', box(8, 14, 14, -38, 62, ZC + 29).fuse(box(8, 14, 14, 30, 62, ZC + 29)), '6061-T6铝合金')
add(42, '俯仰驱动电机(Φ28减速步进/伺服)', cyl(14, 42, (38, 69, ZC + 36), (1, 0, 0)), '外购件', 120, '选型待定, 质量为估算', 'Φ28×42')
add(44, '绝对式角度编码器(磁编码, 14 bit)', cyl(16, 12, (0, -88, ZC), (0, 1, 0)), '外购件', 25, '选型待定, 分辨率0.022°', 'Φ32×12')
for a in (30, -30, 0):
    r = 34.0
    pos = (r * math.sin(math.radians(a + 180)) if a else 0, -68, ZC + r * math.cos(math.radians(a + 180)) if a else ZC - 40)
    if a == 0: continue
    add(45, f'机械限位块({a:+d}°)', box(10, 6, 10, pos[0] - 5, -68, pos[2] - 5), '6061-T6铝合金', spec='±30°硬限位, 带聚氨酯缓冲')
arm = box(6, 4, 46, -3, -72, ZC - 46); arm.rotate(V(0, 0, ZC), V(0, 1, 0), TILT)
add(45, '限位摆杆(随耳轴)', arm, '6061-T6铝合金')
lk = cyl(5, 30, (25, -92, ZC + 20), (0, -1, 0)).fuse(cyl(9, 10, (25, -122, ZC + 20), (0, -1, 0)))
add(46, '锁止夹紧螺钉(抱紧弧槽)', lk, '40Cr钢(调质)', spec='M10, 断电/运输锁止')

# ---- 5 俯视相机 / 6 仰视相机(全局快门工业相机+定焦镜头) ----
def camera(p, d):
    c = V(*p); d = V(*d).normalize()
    body = box(29, 29, 30, -14.5, -14.5, 0); lens = cyl(15, 32, (0, 0, 30), (0, 0, 1))
    m = body.fuse(lens)
    ax = V(0, 0, 1).cross(d)
    if ax.Length > 1e-9:
        m.rotate(V(0, 0, 0), ax, math.degrees(V(0, 0, 1).getAngle(d)))
    elif d.z < 0:
        m.rotate(V(0, 0, 0), V(1, 0, 0), 180)
    m.translate(c); return m
add(5, '俯视测绘相机(全局快门, 12.3 MP, 镜头f=8 mm)', camera((160, 0, -58), (0, 0, -1)), '外购件', 110,
    '参考 Sony IMX304 全局快门传感器类工业相机(29×29×30 mm), 型号质量待核对')
add(5, '俯视相机安装座', box(50, 50, 6, 135, -25, -58).cut(cyl(16, 6, (160, 0, -58), (0, 0, 1))), '6061-T6铝合金')
ca = math.radians(25)
add(6, '仰视相机(全局快门, 镜头f=6 mm, 前倾25°)', camera((185, 0, -46), (math.sin(ca), 0, math.cos(ca))), '外购件', 105,
    '同5, 镜头视场覆盖塔头内侧, 型号质量待核对')

# ---- 7/8/9 电子舱 ----
add(8, '同步板(PPS硬触发+曝光中点回传, MCU+CPLD)', box(90, 60, 14, 40, -30, -46), 'FR4+元件(折算)', 60, '自研')
add(9, '机载计算单元(Jetson Orin NX 16G+载板, 带散热)', box(103, 90, 38, -208, -45, -46), '外购件', 280,
    'NVIDIA Jetson Orin NX 模组70×45 mm, 载板尺寸质量为估算, 待核对')

# ---- 13 线缆 ----
cab = [
    ('激光头数据/供电/PPS线', [(-60, 52, ZC + 30), (-60, 70, ZC + 70), (-60, 70, -58), (-100, 40, -40)]),
    ('同步板-俯视相机触发/回传', [(130, 0, -40), (160, 24, -46), (160, 24, -70)]),
    ('同步板-仰视相机', [(130, 10, -36), (180, 20, -40)]),
    ('同步板-计算单元', [(40, 30, -36), (0, 75, -36), (-150, 46, -36)]),
    ('计算单元-快拆电连接器', [(-110, 0, -8), (-60, 0, -8), (-20, 0, 0)]),
]
for nm, pts in cab:
    add(13, '线缆:' + nm, tube(pts, 3), 'PVC/FEP线缆(折算)')

# ================= 文档 / 导出 =================
doc = App.newDocument('PatentA_Payload')
objs = []
for i, p in enumerate(parts):
    o = doc.addObject('Part::Feature', f'P{p["no"]}_{i:02d}')
    o.Label = f'{p["no"]}_{p["name"]}'; o.Shape = p['shape']; objs.append(o)
    vol = p['shape'].Volume
    p['volume_mm3'] = vol
    if p['mass'] is None:
        p['mass'] = vol * DENS.get(p['material'], 1.85e-3)
    sol = p['shape'].Solids
    if sol:
        w = sum(s.Volume for s in sol)
        p['com'] = [sum(s.Volume * s.CenterOfMass[k] for s in sol) / w for k in range(3)]
    else:
        p['com'] = list(p['shape'].BoundBox.Center)
doc.recompute()
doc.saveAs(os.path.join(OUT, '专利A_同步采集载荷.FCStd'))
import Import
Import.export(objs, os.path.join(OUT, '专利A_同步采集载荷.step'))

M = sum(p['mass'] for p in parts)
cg = [sum(p['mass'] * p['com'][k] for p in parts) / M for k in range(3)]
allc = Part.makeCompound([p['shape'] for p in parts]); bb = allc.BoundBox
rec = dict(model='专利A_同步采集载荷.FCStd', step='专利A_同步采集载荷.step', freecad=App.Version()[:3],
           coord='X航向前,Y左,Z上; 原点=快拆接口下表面中心', tilt_deg=TILT, pitch_axis_z=ZC,
           envelope_mm=[round(bb.XLength, 1), round(bb.YLength, 1), round(bb.ZLength, 1)],
           total_mass_g=round(M, 1), cg_mm=[round(c, 1) for c in cg],
           parts=[dict(no=p['no'], name=p['name'], material=p['material'], spec=p['spec'], source=p['src'],
                       volume_cm3=round(p['volume_mm3'] / 1000, 2), mass_g=round(p['mass'], 1),
                       com_mm=[round(c, 1) for c in p['com']],
                       bbox_mm=[round(v, 1) for v in (p['shape'].BoundBox.XMin, p['shape'].BoundBox.XMax,
                                                       p['shape'].BoundBox.YMin, p['shape'].BoundBox.YMax,
                                                       p['shape'].BoundBox.ZMin, p['shape'].BoundBox.ZMax)])
                  for p in parts])
json.dump(rec, open(os.path.join(OUT, '构建记录.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

# ================= 投影(隐藏线消除) =================
def edges2d(shp, d):
    res = TechDraw.projectEx(shp, V(*d))
    lines = []
    for idx in (0, 3):  # 可见硬边 + 可见轮廓
        s = res[idx]
        if s is None or s.isNull(): continue
        for e in s.Edges:
            n = max(2, int(e.Length / 2) + 1) if e.Curve.TypeId != 'Part::GeomLine' else 2
            pts = e.discretize(n)
            lines.append([[round(q.x, 2), round(q.y, 2)] for q in pts])
    return lines
def mapper(d):
    o = TechDraw.projectEx(Part.makeSphere(0.5, V(0, 0, 0)), V(*d))[3].BoundBox.Center
    cols = []
    for ax in (V(100, 0, 0), V(0, 100, 0), V(0, 0, 100)):
        c = TechDraw.projectEx(Part.makeSphere(0.5, ax), V(*d))[3].BoundBox.Center
        cols.append([(c.x - o.x) / 100, (c.y - o.y) / 100])
    return cols  # 2D = x*cols[0]+y*cols[1]+z*cols[2]
def P2(m, p):
    return [p[0] * m[0][0] + p[1] * m[1][0] + p[2] * m[2][0], p[0] * m[0][1] + p[1] * m[1][1] + p[2] * m[2][1]]

ISO = (1, -1, 0.8)
views = {}
def anchor(shp):
    # 标注锚点: 取零件实体上距离包围盒中心最近的顶点/重心
    return list(shp.BoundBox.Center)
def label_set(shapes_by_no, m):
    out = {}
    for no, sh in shapes_by_no.items():
        out[str(no)] = P2(m, anchor(sh))
    return out
def group_by_no(plist, key=lambda p: p['shape']):
    g = {}
    for p in plist:
        g.setdefault(p['no'], []).append(key(p))
    return {k: (Part.makeCompound(v) if len(v) > 1 else v[0]) for k, v in g.items()}
G = group_by_no(parts)
for nm, d in [('iso', ISO), ('front', (0, -1, 0)), ('top', (0, 0, 1)), ('side', (1, 0, 0))]:
    m = mapper(d); views[nm] = dict(lines=edges2d(allc, d), labels=label_set(G, m))

# 爆炸图
EX = {1: (0, 0, 120), 11: (0, 0, 200), 12: (0, 0, 60), 2: (0, 0, 0), 3: (0, 0, -170), 7: (0, 0, -60),
      41: (0, 0, -170), 43: (0, 110, -170), 42: (0, 150, -110), 44: (0, -110, -170), 45: (0, -70, -170),
      46: (0, -150, -110), 5: (60, 0, -60), 6: (110, 0, 60), 8: (0, 0, 90), 9: (-60, 0, 70), 13: None}
exs = []
for p in parts:
    off = EX.get(p['no'])
    if off is None: continue
    s = p['shape'].copy()
    if p['name'].startswith('主框架耳板'):
        off = (0, 60 if 'L' in p['name'] else -60, 0)
    s.translate(V(*off)); exs.append((p['no'], s))
exc = Part.makeCompound([s for _, s in exs])
m = mapper(ISO)
gexp = {}
for no, s in exs: gexp.setdefault(no, []).append(s)
gexp = {k: Part.makeCompound(v) for k, v in gexp.items()}
views['explode'] = dict(lines=edges2d(exc, ISO), labels=label_set(gexp, m))

# 倾角机构剖视: 以 X=0 平面(过耳轴轴线)剖切, 自+X向-X看(保留 x<=0 部分)
mech_nos = {2, 3, 7, 41, 42, 43, 44, 45, 46}
mech = [p for p in parts if p['no'] in mech_nos and not p['name'].startswith('主框架下板')]
half = box(400, 400, 400, -400, -200, ZC - 200)
cut_parts = []
for p in mech:
    c = p['shape'].common(half)
    if c.Volume > 1e-3: cut_parts.append((p['no'], c))
cc = Part.makeCompound([c for _, c in cut_parts])
dsec = (1, 0, 0); ms = mapper(dsec)
faces = []
for no, c in cut_parts:
    for f in c.Faces:
        if abs(f.BoundBox.XMax) < 1e-4 and abs(f.BoundBox.XMin) < 1e-4:
            poly = [P2(ms, [q.x, q.y, q.z]) for q in f.OuterWire.discretize(80)]
            inner = [[P2(ms, [q.x, q.y, q.z]) for q in w.discretize(60)] for w in f.Wires if not w.isSame(f.OuterWire)]
            faces.append(dict(no=no, outer=poly, inner=inner))
gs = {}
for no, c in cut_parts: gs.setdefault(no, []).append(c)
gs = {k: Part.makeCompound(v) for k, v in gs.items()}
views['section'] = dict(lines=edges2d(cc, dsec), labels=label_set(gs, ms), faces=faces)
views['meta'] = dict(cg=cg, mass=M, iso_map=mapper(ISO), front_map=mapper((0, -1, 0)), ZC=ZC)
json.dump(views, open(os.path.join(OUT, '_proj.json'), 'w', encoding='utf-8'))
print('OK parts=%d mass=%.1f g cg=%s env=%s' % (len(parts), M, [round(c, 1) for c in cg], rec['envelope_mm']))
