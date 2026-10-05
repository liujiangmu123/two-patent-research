# -*- coding: utf-8 -*-
r"""P5 模型校核（freecadcmd 无头运行，只读打开 04_模型/P5_出图模型.FCStd）。

检查：
  1 两腔锁闭油液容积（CAD 布尔求体积）：阀块侧 = 锁闭孔系 ∪ 阀座以下的阀孔 − 插入元件；缸体侧 = 端盖油道
  2 孔系互通关系：不同压力网络之间相交体积必须为 0（设计连通的阀孔—油道除外）
  3 不同压力孔系之间、孔系与螺栓孔/销孔之间的最小壁厚（distToShape）
  4 插入元件与阀块本体干涉体积
输出：04_模型/_check_report.json
用法：powershell -File 07_脚本\run_fc.ps1 p5_check_model.py
"""
import itertools
import json
import os
import time

import FreeCAD as App
import Part

V = App.Vector
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
B = json.load(open(os.path.join(ROOT, "00_设计基准", "P5_设计基准.json"), encoding="utf-8"))
H = B["阀块本体"]["外形_LxWxH"][2]
t0 = time.time()
doc = App.openDocument(os.path.join(ROOT, "04_模型", "P5_出图模型.FCStd"))
NET = {o.Net: o.Shape for o in doc.Objects if hasattr(o, "Net")}
PARTS = [o for o in doc.Objects if hasattr(o, "PartNo")]
X = B["座阀阀孔"]["布置"]
XV2, XV4, XV3, XV1 = X["第二锁闭阀孔_V2"], X["预压阀孔_V4"], X["泄放阀孔_V3"], X["第一锁闭阀孔_V1"]
XRV = B["安全阀孔"]["X"]
YC = 45.0


def cav_lower(x, kind):
    zb = H - (40.0 if kind == "22" else 33.0)
    d = 19.0 if kind == "22" else 15.5
    h = B["死容积附加项_assumption"]["阀座以上统计截止高度_相对孔底_mm"] if kind == "22" else 4.0
    return Part.makeCylinder(d / 2, h, V(x, YC, zb), V(0, 0, 1))


def fuse(ss):
    s = ss[0]
    for t in ss[1:]:
        s = s.fuse(t)
    return s


def near(o, x, tol=15.0):
    bb = o.Shape.BoundBox
    return abs(0.5 * (bb.XMin + bb.XMax) - x) < tol


rep = {"生成时间": time.strftime("%Y-%m-%d %H:%M:%S"), "模型": "04_模型/P5_出图模型.FCStd"}

# ------------------------------------------------------------------ 1 锁闭容积
def by(pno, x=None):
    return [o for o in PARTS if o.PartNo == pno and (x is None or near(o, x))]


# PartNo 即附图标记（V1.1）：42/44/45 座阀与安全阀（p 后缀为阀芯），72 第二压力传感器，75 测压排气接头，27 端面密封圈，
# 41/43 座阀，71 第一压力传感器，73 油温传感器套管，76 阻尼孔螺塞
ins_R = by("42", XV2) + by("44", XV4) + by("45", XRV) + by("42p") + by("44p") + by("45p")
ins_R += by("72") + [o for o in by("75") if near(o, B["测压与测温"]["测压排气孔_有杆腔"]["X"], 5)] + by("27", XV2)
ins_C = by("41", XV1) + by("43", XV3) + by("41p") + by("43p")
ins_C += by("71") + by("73") + by("76") + [o for o in by("75") if near(o, B["测压与测温"]["测压排气孔_无杆腔"]["X"], 5)] + by("27", XV1)
vol = {}
for side, keys, cavs, ins in (("有杆腔", [k for k in NET if k.startswith("R_")], [(XV2, "22"), (XV4, "22"), (XRV, "20")], ins_R),
                              ("无杆腔", [k for k in NET if k.startswith("C_")], [(XV1, "22"), (XV3, "22")], ins_C)):
    holes = fuse([NET[k] for k in keys] + [cav_lower(x, kd) for x, kd in cavs])
    oil = holes.cut(fuse([o.Shape for o in ins]))
    item = {"孔系与阀孔下部并集_cm3": round(holes.Volume / 1000, 3), "扣除插入元件后_cm3": round(oil.Volume / 1000, 3),
            "插入元件": sorted(set(o.Label for o in ins))}
    # 分项（各孔单独体积，未扣重叠，供与手算对照）
    item["分项_未扣重叠_cm3"] = {k: round(NET[k].Volume / 1000, 3) for k in keys}
    vol[side] = item
vol["缸体油道_有杆腔_cm3"] = round(NET["Y_缸体油道_有杆腔"].Volume / 1000, 3)
vol["缸体油道_无杆腔_cm3"] = round(NET["Y_缸体油道_无杆腔"].Volume / 1000, 3)
rep["锁闭容积_CAD"] = vol

# ------------------------------------------------------------------ 2 互通关系
groups = {
    "有杆腔锁闭": [k for k in NET if k.startswith("R_")],
    "无杆腔锁闭": [k for k in NET if k.startswith("C_")],
    "B口": ["X_B口"], "PP口": ["X_PP口"], "安全阀回油口": ["X_RV回油口"], "T口": ["X_T口"], "A口": ["X_A口"],
    "螺栓孔": ["Z_螺栓孔"], "销孔": ["Z_销孔"],
}
G = {g: fuse([NET[k] for k in ks]) for g, ks in groups.items()}
cav = {k: NET[k] for k in NET if k.startswith("K_")}
inter = []
for a, b in itertools.combinations(G, 2):
    v = G[a].common(G[b]).Volume
    inter.append({"对": [a, b], "相交体积_mm3": round(v, 4), "ok": v < 1e-3})
# 阀孔：每个阀孔只允许与一个锁闭网络（下部）和一个外侧口（上部）相交
design = {"K_V2": ("有杆腔锁闭", "B口"), "K_V4": ("有杆腔锁闭", "PP口"), "K_RV": ("有杆腔锁闭", "安全阀回油口"),
          "K_V3": ("无杆腔锁闭", "T口"), "K_V1": ("无杆腔锁闭", "A口")}
cav_links = []
for k, s in cav.items():
    hits = [g for g in G if s.common(G[g]).Volume > 1e-3]
    cav_links.append({"阀孔": k, "相交网络": hits, "ok": sorted(hits) == sorted(design[k])})
rep["互通关系"] = {"网络两两相交": inter, "阀孔连通": cav_links,
               "全部正确": all(i["ok"] for i in inter) and all(c["ok"] for c in cav_links)}

# ------------------------------------------------------------------ 3 最小壁厚
walls = []
pairs = [(a, b) for a, b in itertools.combinations(G, 2) if not (a in ("螺栓孔", "销孔") and b in ("螺栓孔", "销孔"))]
for a, b in pairs:
    d = G[a].distToShape(G[b])[0]
    walls.append({"对": [a, b], "最小壁厚_mm": round(d, 2)})
# 锁闭网络与相邻阀孔上部（第二阀口段，外侧压力）之间
for k, s in cav.items():
    up = s.common(Part.makeBox(400, 200, 40, V(-50, -50, H - 28.0 if k != "K_RV" else H - 21.0)))
    for g in ("有杆腔锁闭", "无杆腔锁闭"):
        d = G[g].distToShape(up)[0]
        walls.append({"对": [g, k + "第二阀口段"], "最小壁厚_mm": round(d, 2)})
walls.sort(key=lambda w: w["最小壁厚_mm"])
rep["最小壁厚"] = walls

# ------------------------------------------------------------------ 4 干涉
blk = [o for o in PARTS if o.PartNo == "2"][0].Shape
itf = []
for o in PARTS:
    if o.PartNo == "2":
        continue
    v = blk.common(o.Shape).Volume
    if v > 0.5:
        itf.append({"零件": o.Label, "与阀块本体干涉_mm3": round(v, 2)})
rep["干涉"] = {"超过0.5mm3的": itf, "ok": not itf}
rep["耗时_s"] = round(time.time() - t0, 1)
with open(os.path.join(ROOT, "04_模型", "_check_report.json"), "w", encoding="utf-8") as fh:
    json.dump(rep, fh, ensure_ascii=False, indent=1)
print("CHECK_DONE", json.dumps({k: rep[k] for k in ("锁闭容积_CAD",)}, ensure_ascii=False)[:1500])
print("互通全部正确", rep["互通关系"]["全部正确"], "干涉ok", rep["干涉"]["ok"], itf[:5])
print("最小壁厚前5", walls[:5])
App.closeDocument(doc.Name)
