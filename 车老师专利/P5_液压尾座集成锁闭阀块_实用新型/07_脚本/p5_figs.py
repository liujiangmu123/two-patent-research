# -*- coding: utf-8 -*-
r"""P5 集成锁闭阀块 说明书附图（图1~图N）生成（freecadcmd 无头运行）。

复制自 P1 的 07_脚本/tc_structure_figs.py（其又改自 InSAR 范本 v11_patent_figs.py），流程相同：零件 → 视图坐标 →
TechDraw.projectEx 可见轮廓 → 按印刷尺寸清理线条 → 剖视图画剖面线 → 深度缓冲求零件可见区域 → 引线布局优化。
P5 的改动：剖面线按零件分别给角度/间距（相邻零件不同），薄密封件涂黑；外购件（阀、传感器、接头）与轴、标准紧固件不剖；
孔、油道等结构要素用“hole”型标注（引线直接指到孔内，无圆点）。
输入：04_模型/P5_出图模型.FCStd（p5_build_model.py 生成）；标记表：05_附图/numerals.json。
输出：05_附图/标注版/图N.png|svg|json 与 05_附图/无标注版/图N.png|svg（几何相同、同一比例）。

    powershell -File 07_脚本\run_fc.ps1 p5_figs.py -Env FIGS=1,4      （FIGS 缺省时出全部图）
"""
import json
import math
import os
import time
import traceback

import FreeCAD as App
import Part
import TechDraw
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.collections import LineCollection  # noqa: E402
from matplotlib.text import Text  # noqa: E402

V = App.Vector
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
MODEL = os.path.join(ROOT, "04_模型", "P5_出图模型.FCStd")
OUT_L = os.path.join(ROOT, "05_附图", "标注版")
OUT_C = os.path.join(ROOT, "05_附图", "无标注版")
NUMS = {k: v for k, v in json.load(open(os.path.join(ROOT, "05_附图", "numerals.json"), encoding="utf-8")).items()
        if not k.startswith("_")}

PXMM = 10.0                     # 深度缓冲分辨率：每印刷毫米像素数
LW, LW_H, LW_L, LW_T = 0.18, 0.10, 0.12, 0.10   # 轮廓线、剖面线、引线、细线（印刷 mm）
FS = 14.0                       # 标号字号 pt（数字高约 3.4 mm，≥3.2 mm）
COL = 15.0                      # 左右标号栏宽（印刷 mm）
GAP = 5.4                       # 相邻标号最小间距（印刷 mm）
DOT = 0.33                      # 引线末端圆点半径（印刷 mm）
WMAX, HMAX = 165.0, 225.0       # 单图最大印刷尺寸（A4 版心 170×257 扣除图号）
DPI = 400
PT = 72.0 / 25.4
plt.rcParams.update({"font.family": "Times New Roman", "mathtext.fontset": "stix", "svg.fonttype": "none"})
NONMETAL = ("PEEK", "POM", "EPDM", "PA66", "尼龙", "聚碳", "NBR")
NEVER = ()
# 剖面线：PartNo → (角度°, 印刷间距 mm, 是否交叉)。相邻零件方向相反或间距不同（GB/T 4457.5）；O 形圈截面很小，用密交叉线近似涂黑
HATCH = {"2": (45.0, 1.5, False), "11": (45.0, 2.6, False), "12": (135.0, 1.5, False), "13": (135.0, 1.5, False),
         "14": (45.0, 2.6, False), "15": (135.0, 1.0, False), "73": (135.0, 0.7, False), "76": (135.0, 0.55, False),
         "27": (45.0, 0.22, True), "14s": (45.0, 0.3, True), "12s": (45.0, 0.3, True)}
HATCH["11"] = (135.0, 2.6, False)      # 缸筒与阀块（45°）方向相反，与端盖（135°/1.5）间距不同


# ================================================================== 模型与位姿
class Model:
    def __init__(self):
        self.doc = App.openDocument(MODEL)
        self.objs = [o for o in self.doc.Objects if o.TypeId == "Part::Feature" and hasattr(o, "PartNo")]
        self.by_pno = {}
        for o in self.objs:
            self.by_pno.setdefault(o.PartNo, []).append(o)


def pose_of(o, *a, **k):
    return App.Placement()


SHIFT = [V(0, 0, 0)]


def point_world(num, *a, **k):
    return V(*NUMS[num]["point"]) + SHIFT[0]


# ================================================================== 视图
def view_rot(d, up):
    w = V(*d)
    w.normalize()
    u = V(*up).cross(w)
    u.normalize()
    v = w.cross(u)
    inv = App.Rotation(u, v, w, "ZXY").inverted()
    assert (inv.multVec(w) - V(0, 0, 1)).Length < 1e-6
    return inv


def to_screen(shape, rinv):
    s = shape.copy()
    s.transformShape(App.Placement(V(0, 0, 0), rinv).toMatrix(), True)
    return s


ABOVE = Part.makeBox(2e4, 2e4, 2e4, V(-1e4, -1e4, 0.0))


def build_items(M, spec):
    """返回 [(key, obj, shape_world, sectioned)]。基础 11 与地面以下部分不画，跨地面零件在 Z=0 截断。"""
    yaw, pitch, dz, A = spec.get("yaw", 0.0), spec.get("pitch", 20.0), spec.get("dz", 0.0), spec.get("A", 0.0)
    sec = spec.get("section")
    crop = spec.get("crop")
    nosec = set(spec.get("nosec", ()))
    items = []
    for o in M.objs:
        if getattr(o, "Virtual", False) or o.Kind == "焊缝" or o.PartNo in NEVER or not spec["filter"](o):
            continue
        s = o.Shape.copy()
        s.translate(SHIFT[0])
        extra = spec.get("crop_part", {}).get(o.PartNo)
        if extra is not None:
            s = s.common(Part.makeBox(*extra))
            if s.isNull() or s.Volume < 1e-3:
                continue
        is_sec = False
        if sec:
            bb = s.BoundBox
            ax_ = "x" if sec == "x" else "y"
            lo_, hi_ = (bb.XMin, bb.XMax) if ax_ == "x" else (bb.YMin, bb.YMax)
            secf = set(spec.get("sec_force", ("27", "14s", "12s")))
            unsec = (o.Kind in ("标准件", "外购件") or o.PartNo in nosec) and o.PartNo not in secf
            neg = spec.get("sec_keep") == "neg"          # 保留剖切面负侧（观察者在正侧）
            if (not neg and hi_ <= 0.0) or (neg and lo_ >= 0.0):
                continue
            if not unsec and lo_ < 0.0 < hi_:
                if ax_ == "x":
                    half = Part.makeBox(1e4, 1e4, 1e4, V(-1e4 if neg else 0.0, -5e3, -5e3))
                else:
                    half = Part.makeBox(1e4, 1e4, 1e4, V(-5e3, -1e4 if neg else 0.0, -5e3))
                s = s.common(half)
                is_sec = True
        if crop:
            x0, x1, y0, y1, z0, z1 = crop
            bb = s.BoundBox
            if bb.XMax < x0 or bb.XMin > x1 or bb.YMax < y0 or bb.YMin > y1 or bb.ZMax < z0 or bb.ZMin > z1:
                continue
            if bb.XMin < x0 or bb.XMax > x1 or bb.YMin < y0 or bb.YMax > y1 or bb.ZMin < z0 or bb.ZMax > z1:
                s = s.common(Part.makeBox(x1 - x0, y1 - y0, z1 - z0, V(x0, y0, z0)))
        if s.isNull() or not s.Solids:
            continue
        if o.Name == "P42" and len(s.Solids) > 1 and not sec:
            for i, so in enumerate(s.Solids):
                items.append(("%s#%d" % (o.Name, i), o, so, False))
            continue
        items.append((o.Name, o, s, is_sec))
    return items


# ================================================================== 投影与线条清理
def hlr(shapes):
    """只取可见锐边（0）与可见轮廓线（3）：不画切线（光滑过渡线）、缝合线、虚线。"""
    if not shapes:
        return []
    res = TechDraw.projectEx(Part.makeCompound(shapes), V(0, 0, 1))
    out = []
    for gi in (0, 3):
        c = res[gi]
        if c is not None and not c.isNull():
            out += c.Edges
    return out


def polylines(edges, dfl):
    pls = []
    for e in edges:
        try:
            if e.Length < 1e-6:
                continue
            if isinstance(e.Curve, Part.Line):
                pts = [e.Vertexes[0].Point, e.Vertexes[-1].Point]
            else:
                pts = e.discretize(Deflection=dfl)
            pls.append(np.array([[p.x, p.y] for p in pts]))
        except Exception:  # noqa: BLE001
            continue
    return pls


def rdp(pts, tol):
    """Ramer–Douglas–Peucker 折线简化（迭代实现）。"""
    n = len(pts)
    if n < 3:
        return pts
    keep = np.zeros(n, bool)
    keep[0] = keep[-1] = True
    stack = [(0, n - 1)]
    while stack:
        a, b = stack.pop()
        if b - a < 2:
            continue
        p, q = pts[a], pts[b]
        d = q - p
        L = math.hypot(d[0], d[1])
        seg = pts[a + 1:b]
        if L < 1e-12:
            dist = np.hypot(seg[:, 0] - p[0], seg[:, 1] - p[1])
        else:
            dist = np.abs(d[0] * (seg[:, 1] - p[1]) - d[1] * (seg[:, 0] - p[0])) / L
        i = int(np.argmax(dist))
        if dist[i] > tol:
            k = a + 1 + i
            keep[k] = True
            stack += [(a, k), (k, b)]
    return pts[keep]


def clean_lines(pls, s, eps=0.18, run_min=0.6, len_min=0.3, dot=0.4, q=25.0):
    """按印刷尺寸清理线条：与已保留线条相距 < eps 且连续重合 ≥ run_min 的部分删去；印刷长度 < len_min 的碎线、
    外廓 < dot 的小圈删去；长线优先保留。返回模型坐标折线。"""
    step = 1.0 / q
    P = []
    for pl in pls:
        pm = pl * s
        seg = np.diff(pm, axis=0)
        L = np.hypot(seg[:, 0], seg[:, 1])
        tot = float(L.sum())
        if tot < len_min:
            continue
        ext = pm.max(0) - pm.min(0)
        if math.hypot(ext[0], ext[1]) < dot:
            continue
        cum = np.concatenate([[0.0], np.cumsum(L)])
        n = max(2, int(math.ceil(tot / step)) + 1)
        t = np.linspace(0.0, tot, n)
        P.append((tot, np.stack([np.interp(t, cum, pm[:, 0]), np.interp(t, cum, pm[:, 1])], 1)))
    if not P:
        return []
    allp = np.concatenate([p for _, p in P])
    xmin, ymin = allp.min(0) - 1.0
    xmax, ymax = allp.max(0) + 1.0
    W, H = int((xmax - xmin) * q) + 3, int((ymax - ymin) * q) + 3
    occ = np.zeros((H, W), bool)
    r = max(1, int(round(eps * q)))
    dy, dx = np.mgrid[-r:r + 1, -r:r + 1]
    disk = (dx * dx + dy * dy) <= r * r
    ody, odx = dy[disk], dx[disk]
    P.sort(key=lambda t: -t[0])
    out = []
    for tot, pts in P:
        ix = ((pts[:, 0] - xmin) * q).astype(int)
        iy = ((pts[:, 1] - ymin) * q).astype(int)
        cov = occ[iy, ix]
        if cov.all():
            continue
        keep = np.ones(len(pts), bool)
        if cov.any():
            d = np.diff(np.concatenate([[0], cov.astype(int), [0]]))
            for a, b in zip(np.nonzero(d == 1)[0], np.nonzero(d == -1)[0]):
                if (b - a) * step >= run_min:
                    keep[a:b] = False
        d = np.diff(np.concatenate([[0], keep.astype(int), [0]]))
        for a, b in zip(np.nonzero(d == 1)[0], np.nonzero(d == -1)[0]):
            if (b - a - 1) * step < len_min:
                continue
            piece = rdp(pts[a:b], 0.015)
            out.append(piece / s)
            yy = (iy[a:b][:, None] + ody[None, :]).ravel()
            xx = (ix[a:b][:, None] + odx[None, :]).ravel()
            ok = (yy >= 0) & (yy < H) & (xx >= 0) & (xx < W)
            occ[yy[ok], xx[ok]] = True
    return out


def section_faces(shape):
    out = []
    for f in shape.Faces:
        if f.Surface.__class__.__name__ != "Plane":
            continue
        bb = f.BoundBox
        if abs(bb.ZMin) < 1e-4 and abs(bb.ZMax) < 1e-4:
            out.append(f)
    return out


class Raster:
    """深度缓冲：每个像素记录最前面的零件（三角形按深度排序绘制）。q = 像素 / 模型单位。"""

    def __init__(self, scr_items, box, q):
        self.q = q
        self.x0, self.y1 = box[0], box[3]
        W = int(math.ceil((box[1] - box[0]) * q)) + 4
        H = int(math.ceil((box[3] - box[2]) * q)) + 4
        self.keys = []
        tris, ids, zs = [], [], []
        tol = max(0.6 / q, 0.02)
        for key, s, is_sec in scr_items:
            sec_faces = set(f.hashCode() for f in section_faces(s)) if is_sec else set()
            kid = len(self.keys)
            self.keys.append(key)
            sid = None
            if sec_faces:
                sid = len(self.keys)
                self.keys.append("SEC|" + key)
            for f in s.Faces:
                try:
                    pts, tr = f.tessellate(tol)
                except Exception:  # noqa: BLE001
                    continue
                if not tr:
                    continue
                Pp = np.array([[p.x, p.y, p.z] for p in pts])
                T = np.array(tr)
                tris.append(Pp[T])
                use = sid if (sid is not None and f.hashCode() in sec_faces) else kid
                ids.append(np.full(len(T), use, dtype=np.int32))
                zs.append(Pp[T][:, :, 2].mean(axis=1) + (1e-3 if use == sid else 0.0))
        self.img = np.zeros((H, W), dtype=np.int32) - 1
        if not tris:
            return
        tris = np.concatenate(tris)
        ids = np.concatenate(ids)
        zs = np.concatenate(zs)
        order = np.argsort(zs)
        im = Image.new("I", (W, H), -1)
        dr = ImageDraw.Draw(im)
        px = (tris[:, :, 0] - self.x0) * q
        py = (self.y1 - tris[:, :, 1]) * q
        for i in order:
            dr.polygon([(px[i, 0], py[i, 0]), (px[i, 1], py[i, 1]), (px[i, 2], py[i, 2])], fill=int(ids[i]))
        self.img = np.array(im, dtype=np.int32)

    def mask(self, keys):
        ids = [i for i, k in enumerate(self.keys) if k in keys or (k.startswith("SEC|") and k[4:] in keys)]
        if not ids:
            return np.zeros_like(self.img, dtype=bool)
        return np.isin(self.img, ids)

    def owner(self, x, y):
        r, c = int((self.y1 - y) * self.q), int((x - self.x0) * self.q)
        if 0 <= r < self.img.shape[0] and 0 <= c < self.img.shape[1] and self.img[r, c] >= 0:
            return self.keys[self.img[r, c]].replace("SEC|", "")
        return None

    def to_model(self, r, c):
        return self.x0 + (c + 0.5) / self.q, self.y1 - (r + 0.5) / self.q


def hatch_segments(R, sec_key, angle, spacing_px, cross=False):
    idx = [i for i, k in enumerate(R.keys) if k == "SEC|" + sec_key]
    if not idx:
        return []
    m = R.img == idx[0]
    m = ndimage.binary_erosion(m, iterations=1)          # 剖面线离轮廓线留一点间隙
    if m.sum() < 4:
        return []
    rr, cc = np.nonzero(m)
    r0, r1, c0, c1 = rr.min(), rr.max(), cc.min(), cc.max()
    segs = []
    for ang in ((angle, angle + 90.0) if cross else (angle,)):
        t = math.radians(ang)
        d = np.array([math.cos(t), -math.sin(t)])
        n = np.array([-d[1], d[0]])
        corners = np.array([[c0, r0], [c1, r0], [c0, r1], [c1, r1]], dtype=float)
        proj_n = corners @ n
        proj_d = corners @ d
        ts = np.arange(proj_d.min() - 2, proj_d.max() + 2, 0.5)
        for k in range(math.floor(proj_n.min() / spacing_px), math.ceil(proj_n.max() / spacing_px) + 1):
            base = n * (k * spacing_px + 0.5 * spacing_px)
            pts = base[None, :] + ts[:, None] * d[None, :]
            cs, rs = pts[:, 0], pts[:, 1]
            ok = (rs >= 0) & (rs < m.shape[0]) & (cs >= 0) & (cs < m.shape[1])
            inside = np.zeros(len(ts), dtype=bool)
            inside[ok] = m[rs[ok].astype(int), cs[ok].astype(int)]
            if not inside.any():
                continue
            dif = np.diff(np.concatenate([[0], inside.astype(int), [0]]))
            for a, b in zip(np.nonzero(dif == 1)[0], np.nonzero(dif == -1)[0] - 1):
                if b - a < 3:
                    continue
                segs.append([R.to_model(rs[a], cs[a]), R.to_model(rs[b], cs[b])])
    return segs


# ================================================================== 标注：候选落点
def anchor_cands(R, mask, k=12):
    """零件可见区域内的候选落点：先取离区域边界足够远的像素，再用最远点采样取 k 个分散的点。
    返回 [(x, y, 离边界距离 · 模型单位)]。"""
    if mask.sum() < 3:
        return []
    dt = ndimage.distance_transform_edt(mask)
    m = dt.max()
    thr = max(0.45 * m, min(m, 0.9 * PXMM))
    rr, cc = np.nonzero(dt >= thr)
    if len(rr) > 8000:
        sel = np.random.default_rng(1).choice(len(rr), 8000, replace=False)
        rr, cc = rr[sel], cc[sel]
    pts = np.stack([rr, cc], 1).astype(float)
    i0 = int(np.argmax(dt[rr, cc]))
    chosen = [i0]
    dmin = np.hypot(pts[:, 0] - pts[i0, 0], pts[:, 1] - pts[i0, 1])
    for _ in range(k - 1):
        j = int(np.argmax(dmin))
        if dmin[j] < 1.5 * PXMM:
            break
        chosen.append(j)
        dmin = np.minimum(dmin, np.hypot(pts[:, 0] - pts[j, 0], pts[:, 1] - pts[j, 1]))
    out = []
    for j in chosen:
        r, c = int(pts[j, 0]), int(pts[j, 1])
        x, y = R.to_model(r, c)
        out.append((x, y, dt[r, c] / R.q))
    return out


# ================================================================== 标注：引线布局优化
def seg_cross(A, E):
    """n 条线段 A[i]→E[i] 两两是否相交（真相交）。"""
    def cr(u, v):
        return u[..., 0] * v[..., 1] - u[..., 1] * v[..., 0]
    a, b, c, d = A[:, None, :], E[:, None, :], A[None, :, :], E[None, :, :]
    o1, o2 = cr(b - a, c - a), cr(b - a, d - a)
    o3, o4 = cr(d - c, a - c), cr(d - c, b - c)
    X = (o1 * o2 < 0) & (o3 * o4 < 0)
    np.fill_diagonal(X, False)
    return X


def pt_seg_dist(Pp, A, B):
    """点集 Pp(n) 到线段 A→B(m) 的距离矩阵 (m, n)。"""
    AB = B - A
    L2 = (AB ** 2).sum(1)[:, None] + 1e-18
    AP = Pp[None, :, :] - A[:, None, :]
    t = np.clip((AP * AB[:, None, :]).sum(2) / L2, 0.0, 1.0)
    proj = A[:, None, :] + t[..., None] * AB[:, None, :]
    dd = Pp[None, :, :] - proj
    return np.hypot(dd[..., 0], dd[..., 1])


def spread(des, lo, hi, gap):
    """des 从上到下（递减）排列的期望坐标 → 互相间距 ≥ gap 的坐标，尽量不超出 [lo, hi]。"""
    n = len(des)
    y = list(des)
    for i in range(n):
        y[i] = min(y[i], hi) if i == 0 else min(y[i], y[i - 1] - gap)
    if n and y[-1] < lo:
        y[-1] = lo
        for i in range(n - 2, -1, -1):
            y[i] = max(y[i], y[i + 1] + gap)
    return y


def text_w(num):
    return len(num) * 0.5 * FS / PT          # 数字宽度（印刷 mm）


def place_labels(labels, box, s, tb, R=None, obst=None):
    """labels：[{num, cands:[(x,y,dt)], side, kind}]。求每个标注的落点与所在侧，使总代价最小：
    引线长度 + 交叉（重罚）+ 从其他落点旁掠过 + 落点彼此太近 + 引线过陡 + 落点离轮廓太近。"""
    n = len(labels)
    if n == 0:
        return [], {"crossings": 0, "min_pass_mm": None}
    sides = ("T", "B") if tb else ("L", "R")

    def opts(l):
        ss = [l["side"]] if l.get("side") else list(sides)
        return [(ci, sd) for ci in range(len(l["cands"])) for sd in ss]

    def layout(st):
        A = np.array([labels[i]["cands"][st[i][0]][:2] for i in range(n)])
        E = np.zeros_like(A)
        if not tb:
            lo, hi = box[2] - 10.0 / s, box[3] + 10.0 / s
            for sd in ("L", "R"):
                dy = [labels[i].get("ly", 0.0) / s for i in range(n)]      # P5：标号期望位置相对落点的竖向偏移（印刷 mm）
                idx = sorted([i for i in range(n) if st[i][1] == sd], key=lambda i: -(A[i, 1] + dy[i]))
                ys = spread([A[i, 1] + dy[i] for i in idx], lo, hi, GAP / s)
                xe = box[0] - 2.4 / s if sd == "L" else box[1] + 2.4 / s
                for i, y in zip(idx, ys):
                    E[i] = (xe, y)
        else:
            lo, hi = box[0] - 8.0 / s, box[1] + 8.0 / s
            for sd in ("T", "B"):
                idx = sorted([i for i in range(n) if st[i][1] == sd], key=lambda i: A[i, 0])
                xs = [A[i, 0] for i in idx]
                for k in range(1, len(xs)):
                    g = (0.5 * (text_w(labels[idx[k - 1]]["num"]) + text_w(labels[idx[k]]["num"])) + 2.5) / s
                    xs[k] = max(xs[k], xs[k - 1] + g)
                if xs and xs[-1] > hi:
                    xs[-1] = hi
                    for k in range(len(xs) - 2, -1, -1):
                        g = (0.5 * (text_w(labels[idx[k]]["num"]) + text_w(labels[idx[k + 1]]["num"])) + 2.5) / s
                        xs[k] = min(xs[k], xs[k + 1] - g)
                ye = box[3] + 6.2 / s if sd == "T" else box[2] - 6.2 / s
                for i, x in zip(idx, xs):
                    E[i] = (x, ye)
        return A, E

    def cost(st):
        A, E = layout(st)
        seg = E - A
        c = np.hypot(seg[:, 0], seg[:, 1]).sum() * s
        X = seg_cross(A, E)
        c += 5000.0 * X.sum() / 2
        D = pt_seg_dist(A, A, E) * s
        np.fill_diagonal(D, np.inf)
        c += (np.clip(2.0 - D, 0, None) * 400.0).sum()
        AA = np.hypot(A[:, None, 0] - A[None, :, 0], A[:, None, 1] - A[None, :, 1]) * s
        np.fill_diagonal(AA, np.inf)
        c += (np.clip(3.0 - AA, 0, None) * 60.0).sum() / 2
        if tb:
            c += 3.0 * np.clip(np.abs(seg[:, 0]) - 0.9 * np.abs(seg[:, 1]), 0, None).sum() * s
        else:
            c += 3.0 * np.clip(np.abs(seg[:, 1]) - 0.9 * np.abs(seg[:, 0]), 0, None).sum() * s
        dq = np.array([labels[i]["cands"][st[i][0]][2] for i in range(n)]) * s
        c += (np.clip(2.0 - dq, 0, None) * 15.0).sum()
        if R is not None:                        # 引线穿过的图线条数（沿引线采样深度缓冲，零件编号变化一次记一次）
            pts = A[:, None, :] + TS[None, :, None] * seg[:, None, :]
            rr = ((R.y1 - pts[..., 1]) * R.q).astype(int)
            cc = ((pts[..., 0] - R.x0) * R.q).astype(int)
            ok = (rr >= 0) & (rr < R.img.shape[0]) & (cc >= 0) & (cc < R.img.shape[1])
            ids = np.full(rr.shape, -1, dtype=np.int32)
            ids[ok] = R.img[rr[ok], cc[ok]]
            c += 2.0 * (np.diff(ids, axis=1) != 0).sum()
        if obst is not None and len(obst):       # 不从图中符号（O、d、H、S1、ψ 等）旁掠过
            Do = pt_seg_dist(obst[:, :2], A, E) * s
            c += (np.clip(obst[None, :, 2] - Do, 0, None) * 400.0).sum()
        return c

    TS = np.linspace(0.0, 1.0, 140)

    state = []
    for l in labels:
        best = None
        for ci, sd in opts(l):
            x, y, dtm = l["cands"][ci]
            edge = {"L": x - box[0], "R": box[1] - x, "T": box[3] - y, "B": y - box[2]}[sd]
            sc = edge * s - 3.0 * min(dtm * s, 2.0)
            if best is None or sc < best[0]:
                best = (sc, ci, sd)
        state.append((best[1], best[2]))
    cur = cost(state)
    for _ in range(10):
        improved = False
        for i in range(n):
            best_c, best_o = cur, state[i]
            for o in opts(labels[i]):
                if o == state[i]:
                    continue
                old = state[i]
                state[i] = o
                c = cost(state)
                state[i] = old
                if c < best_c - 1e-9:
                    best_c, best_o = c, o
            if best_o != state[i]:
                state[i], cur, improved = best_o, best_c, True
        if not improved:
            break
    A, E = layout(state)
    X = seg_cross(A, E)
    D = pt_seg_dist(A, A, E) * s
    np.fill_diagonal(D, np.inf)
    placed = []
    for i, l in enumerate(labels):
        placed.append(dict(l, a=tuple(A[i]), e=tuple(E[i]), side=state[i][1], dt_mm=l["cands"][state[i][0]][2] * s))
    return placed, {"crossings": int(X.sum() // 2), "min_pass_mm": float(D.min()) if n > 1 else None}


# ================================================================== 绘制工具
def wave(p, q, s, amp=0.5, wl=4.0):
    p, q = np.array(p), np.array(q)
    L = np.linalg.norm(q - p)
    if L < 1e-9:
        return np.array([p, q])
    d = (q - p) / L
    n = np.array([-d[1], d[0]])
    t = np.linspace(0, L, max(8, int(L * s / 0.3)))
    return p[None, :] + t[:, None] * d[None, :] + (amp / s) * np.sin(2 * math.pi * t * s / wl)[:, None] * n[None, :]


def clip_circle(pls, c, r):
    out = []
    for pl in pls:
        pts = [pl[0]]
        for a, b in zip(pl[:-1], pl[1:]):
            L = np.linalg.norm(b - a)
            k = max(1, int(L / (r / 200.0)))
            for j in range(1, k + 1):
                pts.append(a + (b - a) * j / k)
        pts = np.array(pts)
        ins = np.hypot(pts[:, 0] - c[0], pts[:, 1] - c[1]) <= r
        cur = []
        for p, i in zip(pts, ins):
            if i:
                cur.append(p)
            elif len(cur) > 1:
                out.append(np.array(cur))
                cur = []
            else:
                cur = []
        if len(cur) > 1:
            out.append(np.array(cur))
    return out


def artist_extent(fig, ax):
    """画布上全部内容（线、面片、文字）的数据坐标范围。"""
    fig.canvas.draw()
    rend = fig.canvas.get_renderer()
    inv = ax.transData.inverted()
    xs, ys = [], []
    for a in list(ax.lines) + list(ax.collections) + list(ax.patches) + list(ax.texts):
        if not a.get_visible():
            continue
        if isinstance(a, Text):
            if not a.get_text():
                continue
            bb = a.get_window_extent(rend)
            (x0, y0), (x1, y1) = inv.transform([[bb.x0, bb.y0], [bb.x1, bb.y1]])
            xs += [x0, x1]
            ys += [y0, y1]
        elif isinstance(a, LineCollection):
            for sgm in a.get_segments():
                if len(sgm):
                    xs += [sgm[:, 0].min(), sgm[:, 0].max()]
                    ys += [sgm[:, 1].min(), sgm[:, 1].max()]
        elif hasattr(a, "get_xydata"):
            d = a.get_xydata()
            if len(d):
                xs += [np.nanmin(d[:, 0]), np.nanmax(d[:, 0])]
                ys += [np.nanmin(d[:, 1]), np.nanmax(d[:, 1])]
        elif isinstance(a, matplotlib.patches.Patch) and a is not ax.patch:
            v = a.get_patch_transform().transform(a.get_path().vertices)
            xs += [v[:, 0].min(), v[:, 0].max()]
            ys += [v[:, 1].min(), v[:, 1].max()]
    return min(xs), max(xs), min(ys), max(ys)


def new_ax(box, s):
    xlo, xhi, ylo, yhi = box[0] - 40 / s, box[1] + 40 / s, box[2] - 40 / s, box[3] + 40 / s
    fig = plt.figure(figsize=((xhi - xlo) * s / 25.4, (yhi - ylo) * s / 25.4))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(xlo, xhi)
    ax.set_ylim(ylo, yhi)
    ax.axis("off")
    return fig, ax


def finalize(fig, ax, s):
    x0, x1, y0, y1 = artist_extent(fig, ax)
    m = 1.5 / s
    x0, x1, y0, y1 = x0 - m, x1 + m, y0 - m, y1 + m
    W, H = (x1 - x0) * s, (y1 - y0) * s
    fig.set_size_inches(W / 25.4, H / 25.4)
    ax.set_xlim(x0, x1)
    ax.set_ylim(y0, y1)
    return W, H


def draw_geom(ax, spec, s, pls, ph_pls, hatches, c2r, rinv):
    crop = spec.get("crop")
    wav, norm = [], []
    if crop and spec.get("wavy") and not c2r:
        lines = []
        for k_, nvec in enumerate((V(1, 0, 0), V(0, 1, 0), V(0, 0, 1))):
            rn = rinv.multVec(nvec)
            if abs(rn.z) > 1e-6:
                continue
            for c in (crop[2 * k_], crop[2 * k_ + 1]):
                if abs(c) < 5e3:
                    lines.append((rn.x, rn.y, c))
        for pl in pls:
            hit = any(np.all(np.abs(pl[:, 0] * a + pl[:, 1] * b - c) < 0.05) for a, b, c in lines)
            (wav if hit else norm).append(pl)
    else:
        norm = pls
    ax.add_collection(LineCollection(norm, colors="k", linewidths=LW * PT, capstyle="round", joinstyle="round"))
    for pl in wav:
        ax.plot(*wave(pl[0], pl[-1], s).T, color="k", lw=LW_T * PT)
    if ph_pls:
        ax.add_collection(LineCollection(ph_pls, colors="k", linewidths=LW_T * PT,
                                         linestyles=[(0, (8, 1.8, 1.2, 1.8, 1.2, 1.8))]))
    if hatches:
        ax.add_collection(LineCollection(hatches, colors="k", linewidths=LW_H * PT))
    if c2r:
        ax.add_patch(plt.Circle(c2r[0], c2r[1], fill=False, lw=LW_T * PT, color="k"))


def draw_labels(ax, placed, s, box, tb):
    for l in placed:
        a, e = np.array(l["a"]), np.array(l["e"])
        u = (e - a) / max(np.linalg.norm(e - a), 1e-9)
        a2 = a
        if l["kind"] == "point":
            mark(ax, a, s, 0.8)
            a2 = a + u * 0.8 / s
        ax.plot([a2[0], e[0]], [a2[1], e[1]], color="k", lw=LW_L * PT, solid_capstyle="butt")
        if l["kind"] == "part":
            ax.add_patch(plt.Circle(a, DOT / s, color="k", lw=0))
        if tb:
            if l["side"] == "T":
                ax.text(e[0], e[1] + 0.7 / s, l["num"], fontsize=FS, ha="center", va="bottom")
            else:
                ax.text(e[0], e[1] - 0.7 / s, l["num"], fontsize=FS, ha="center", va="top")
        elif l["side"] == "L":
            ax.text(e[0] - 0.7 / s, e[1], l["num"], fontsize=FS, ha="right", va="center")
        else:
            ax.text(e[0] + 0.7 / s, e[1], l["num"], fontsize=FS, ha="left", va="center")


def arrow(ax, p, q, s, lw=LW_L, head=2.4, text=None, toff=(0, 0), fs=FS, ha="center", va="center", style="-"):
    p, q = np.array(p), np.array(q)
    d = q - p
    L = np.linalg.norm(d)
    if L < 1e-9:
        return
    u = d / L
    n = np.array([-u[1], u[0]])
    hl, hw = head / s, head * 0.33 / s
    b = q - u * hl
    ax.plot([p[0], b[0]], [p[1], b[1]], color="k", lw=lw * PT, linestyle=style)
    ax.add_patch(plt.Polygon([q, b + n * hw, b - n * hw], closed=True, color="k", lw=0))
    if text:
        mm = 0.5 * (p + q)
        ax.text(mm[0] + toff[0] / s, mm[1] + toff[1] / s, text, fontsize=fs, ha=ha, va=va)


def dim(ax, p, q, off, s, text, toff=(0, 0)):
    """尺寸线：p→q，沿法向偏 off（印刷 mm），两端箭头 + 尺寸界线。"""
    p, q = np.array(p), np.array(q)
    u = (q - p) / np.linalg.norm(q - p)
    n = np.array([-u[1], u[0]])
    a, b = p + n * off / s, q + n * off / s
    sg = np.sign(off)
    for e0, e1 in ((p, a), (q, b)):
        ax.plot([e0[0] + n[0] * 0.8 / s * sg, e1[0] + n[0] * 1.5 / s * sg],
                [e0[1] + n[1] * 0.8 / s * sg, e1[1] + n[1] * 1.5 / s * sg], color="k", lw=LW_T * PT)
    mm = 0.5 * (a + b)
    arrow(ax, mm, a, s, lw=LW_T)
    arrow(ax, mm, b, s, lw=LW_T)
    ax.text(mm[0] + toff[0] / s, mm[1] + toff[1] / s, text, fontsize=FS, ha="center", va="center")


def mark(ax, p, s, r=0.9, cross=True):
    ax.add_patch(plt.Circle(p, r / s, fill=False, lw=LW_L * PT, color="k"))
    if cross:
        ax.plot([p[0] - 1.6 * r / s, p[0] + 1.6 * r / s], [p[1], p[1]], color="k", lw=LW_T * PT)
        ax.plot([p[0], p[0]], [p[1] - 1.6 * r / s, p[1] + 1.6 * r / s], color="k", lw=LW_T * PT)


def angle_arc(ax, c, r, a0, a1, s, text, tr=1.25):
    t = np.radians(np.linspace(a0, a1, 60))
    ax.plot(c[0] + r * np.cos(t), c[1] + r * np.sin(t), color="k", lw=LW_T * PT)
    am = math.radians(0.5 * (a0 + a1))
    ax.text(c[0] + tr * r * math.cos(am), c[1] + tr * r * math.sin(am), text, fontsize=FS, ha="center", va="center")


def chain(ax, p, q, s):
    ax.plot([p[0], q[0]], [p[1], q[1]], color="k", lw=LW_T * PT, linestyle=(0, (8, 1.8, 1.2, 1.8)))


# ================================================================== 单图
def rep_keys(M, scr_keys, reps):
    keys = set()
    for r_ in reps:
        pno, _, si = r_.partition("#")
        for o in M.by_pno.get(pno, []):
            if si:
                keys.add(o.Name + "#" + si)
            else:
                keys.add(o.Name)
                keys |= {k for k in scr_keys if k.startswith(o.Name + "#")}
    return keys


def fit_scale(box, spec):
    Wd, Hd = box[1] - box[0], box[3] - box[2]
    tb = spec.get("cols") == "TB"
    wa = spec.get("wmax", WMAX) - (12.0 if tb else 2 * COL)
    ha = spec.get("hmax", HMAX) - (26.0 if tb else 4.0) - spec.get("top_mm", 0.0) - spec.get("bottom_mm", 0.0)
    return min(wa / Wd, ha / Hd, spec.get("smax", 10.0))


def annot_obstacles(spec, P, s, box):
    """在草稿画布上跑一遍图中符号绘制，取出文字与标记圆的位置作为引线避让点 [(x, y, 避让半径 mm)]。"""
    if not spec.get("annot"):
        return None
    fig, ax = new_ax(box, s)
    spec["annot"](ax, P, s, box)
    fig.canvas.draw()
    rend = fig.canvas.get_renderer()
    inv = ax.transData.inverted()
    out = []
    for t in ax.texts:
        bb = t.get_window_extent(rend)
        (x0, y0), (x1, y1) = inv.transform([[bb.x0, bb.y0], [bb.x1, bb.y1]])
        r = 0.5 * math.hypot(x1 - x0, y1 - y0) * s + 1.2
        out.append((0.5 * (x0 + x1), 0.5 * (y0 + y1), r))
    for pch in ax.patches:
        if isinstance(pch, matplotlib.patches.Circle) and pch.get_radius() * s < 3.0:
            out.append((pch.center[0], pch.center[1], pch.get_radius() * s + 1.2))
    plt.close(fig)
    return np.array(out) if out else None


def collect_labels(M, spec, R, kept, P):
    labels, missing = [], []
    keys_all = [k for k, _, _ in kept]
    for ent in spec.get("labels", []):
        num, opt = (ent, {}) if isinstance(ent, str) else (ent[0], ent[1])
        d = NUMS[num]
        if "point" in d or "at" in opt:
            pw = (V(*opt["at"]) if "at" in opt else V(*d["point"])) + SHIFT[0]
            p = P(pw)
            labels.append(dict(num=num, name=d["name"], kind="hole" if d.get("hole", True) else "point", side=opt.get("side"),
                               cands=[(p[0], p[1], 1e3)], ly=opt.get("ly", 0.0)))
            continue
        if d.get("vector"):
            p = spec["vec_anchor"][num](P)
            labels.append(dict(num=num, name=d["name"], kind="vec", side=opt.get("side"), cands=[(p[0], p[1], 1e3)]))
            continue
        keys = rep_keys(M, keys_all, opt.get("rep", d["rep"]))
        cands = anchor_cands(R, R.mask(keys))
        if not cands:
            missing.append(num)
            continue
        labels.append(dict(num=num, name=d["name"], kind="part", side=opt.get("side"), cands=cands, keys=sorted(keys),
                           ly=opt.get("ly", 0.0)))
    return labels, missing


def render(M, fid, spec, cache):
    t0 = time.time()
    SHIFT[0] = V(*spec.get("shift", (0, 0, 0)))
    rinv = view_rot(spec["dir"], spec.get("up", (0, 0, 1)))
    P = lambda p: (rinv.multVec(p).x, rinv.multVec(p).y)   # noqa: E731
    items = cache.get(spec.get("same_items_as")) if spec.get("same_items_as") else None
    if items is None:
        items = build_items(M, spec)
    cache[fid] = items
    scr = [(k, to_screen(s, rinv), sec) for k, o, s, sec in items]
    lab_reps = []
    for ent in spec.get("labels", []):
        num, opt = (ent, {}) if isinstance(ent, str) else (ent[0], ent[1])
        if "rep" in NUMS[num]:
            lab_reps += opt.get("rep", NUMS[num]["rep"])
    protect = rep_keys(M, [k for k, _, _ in scr], lab_reps)
    detail = spec.get("detail")
    if detail:
        c2 = P(detail["center"]())
        box0 = (c2[0] - detail["r"], c2[0] + detail["r"], c2[1] - detail["r"], c2[1] + detail["r"])
    else:
        bbs = [sh.BoundBox for _, sh, _ in scr]
        box0 = (min(b.XMin for b in bbs), max(b.XMax for b in bbs), min(b.YMin for b in bbs), max(b.YMax for b in bbs))
    s_est = fit_scale(box0, spec)
    minp = spec.get("min_part_mm", 1.3)
    kept, dropped = [], 0
    for k, sh, sec in scr:                      # 省略在本图比例下看不清的小零件（被标注者除外）
        b = sh.BoundBox
        if k not in protect and math.hypot(b.XLength, b.YLength) * s_est < minp:
            dropped += 1
            continue
        kept.append((k, sh, sec))
    edges = hlr([sh for _, sh, _ in kept])
    ph_edges = []
    if spec.get("phantom"):
        ph = build_items(M, dict(spec, **spec["phantom"]))
        ph_edges = hlr([to_screen(s, rinv) for _, _, s, _ in ph])
    if detail:
        box = box0
    else:
        bbs = [e.BoundBox for e in edges + ph_edges]
        box = (min(b.XMin for b in bbs), max(b.XMax for b in bbs), min(b.YMin for b in bbs), max(b.YMax for b in bbs))
    s = fit_scale(box, spec)
    raw = polylines(edges, 0.02 / s)
    raw_ph = polylines(ph_edges, 0.02 / s)
    if detail:
        raw = clip_circle(raw, c2, detail["r"])
        raw_ph = clip_circle(raw_ph, c2, detail["r"])
    R = Raster(kept, (box[0] - 2 / s, box[1] + 2 / s, box[2] - 2 / s, box[3] + 2 / s), PXMM * s)
    s0 = s
    if detail:
        rr, cc = np.mgrid[0:R.img.shape[0], 0:R.img.shape[1]]
        xm, ym = R.x0 + (cc + 0.5) / R.q, R.y1 - (rr + 0.5) / R.q
        R.img[np.hypot(xm - c2[0], ym - c2[1]) > detail["r"] * 0.94] = -1
    labels, missing = collect_labels(M, spec, R, kept, P)
    tb = spec.get("cols") == "TB"
    c2r = (c2, detail["r"]) if detail else None
    for it in range(4):                         # 超出版心则整体缩小重排
        pls = clean_lines(raw, s)
        ph_pls = clean_lines(raw_ph, s)
        hatches = []
        if spec.get("section"):
            k = 0
            for key, o, sh, sec in items:
                if not sec:
                    continue
                nm = any(t in o.Material for t in NONMETAL)
                ang, sp, cr = HATCH.get(o.PartNo, (45.0 if k % 2 == 0 else 135.0, 1.5, nm))
                k += 1
                hatches += hatch_segments(R, key, ang, sp * spec.get("hatch_scale", 1.0) * R.q / s, cross=cr)
        placed, stats = place_labels(labels, box, s, tb, R, annot_obstacles(spec, P, s, box))
        fig, ax = new_ax(box, s)
        draw_geom(ax, spec, s, pls, ph_pls, hatches, c2r, rinv)
        draw_labels(ax, placed, s, box, tb)
        if spec.get("annot"):
            spec["annot"](ax, P, s, box)
        W, H = finalize(fig, ax, s)
        f = min(spec.get("wmax", WMAX) / W, HMAX / H)
        if f >= 0.999:
            break
        plt.close(fig)
        s *= f * 0.985
    os.makedirs(OUT_L, exist_ok=True)
    os.makedirs(OUT_C, exist_ok=True)
    fn = os.path.join(OUT_L, "图%d" % fid)
    fig.savefig(fn + ".png", dpi=DPI, facecolor="white")
    fig.savefig(fn + ".svg", facecolor="white")
    plt.close(fig)
    # 无标注版：同一比例、同一几何，只去掉标号、引线与说明性符号
    fig, ax = new_ax(box, s)
    draw_geom(ax, spec, s, pls, ph_pls, hatches, c2r, rinv)
    Wc, Hc = finalize(fig, ax, s)
    fc = os.path.join(OUT_C, "图%d" % fid)
    fig.savefig(fc + ".png", dpi=DPI, facecolor="white")
    fig.savefig(fc + ".svg", facecolor="white")
    plt.close(fig)
    # 落点复核：落点像素的最前零件必须是所标零件
    check = []
    for l in placed:
        own = R.owner(*l["a"]) if l["kind"] == "part" else "(几何点)"
        ok = (l["kind"] != "part") or (own in l.get("keys", []))
        check.append({"num": l["num"], "name": l["name"], "side": l["side"], "anchor_part": own, "ok": ok,
                      "inside_mm": round(min(l["dt_mm"], 99.0), 2)})
    rep = {"fig": fid, "title": spec["title"], "scale": round(s, 5), "size_mm": [round(W, 1), round(H, 1)],
           "size_clean_mm": [round(Wc, 1), round(Hc, 1)], "labels": [l["num"] for l in placed], "missing": missing,
           "crossings": stats["crossings"], "min_leader_pass_mm": stats["min_pass_mm"] and round(stats["min_pass_mm"], 2),
           "all_anchors_ok": all(c["ok"] for c in check), "anchors": check, "n_items": len(items),
           "dropped_small": dropped, "n_lines": len(pls), "n_hatch": len(hatches), "t_s": round(time.time() - t0, 1)}
    with open(fn + ".json", "w", encoding="utf-8") as fh:
        json.dump(rep, fh, ensure_ascii=False, indent=1)
    return rep


# ================================================================== 图定义
def grp(*gs):
    return lambda o: o.Group_ in gs


def f_whole(o):
    return o.PartNo not in ("41f",)


def fig_specs():
    """图1 装配纵剖；图2 轴测；图3 主视；图4 后视；图5、图6 横剖（分别过无杆腔、有杆腔锁闭侧）；图7 图1 局部放大。
    "at" 为孔、油道等结构要素的标注落点（未平移的模型坐标，须位于该图可见的孔内或孔边）。"""
    F = {}
    allp = lambda o: True                      # noqa: E731
    blk = lambda o: o.Group_ != "缸"          # noqa: E731
    YC = 45.0
    # ---- 图1：过缸轴线（亦为各阀孔、锁闭油道轴线）的竖直平面 Y=45 剖开，自前侧看
    F[1] = dict(title="尾座液压缸与集成锁闭阀块装配剖视图", dir=(0, -1, 0), up=(0, 0, 1), section="y", shift=(0.0, -YC, 0.0),
                filter=allp, wavy=True, crop=(-75.0, 1e4, -1e4, 1e4, -1e4, 1e4), min_part_mm=0.4, cols="TB",
                nosec={"15"},
                labels=["2", "11", "12", "13", "14", "15", "16", "17", "20", "25", "26", "33", "35",
                        "41", "42", "43", "44", "45", "72", "73", "74"])
    # ---- 图2：轴测（前、左、上方）
    blk2 = lambda o: o.Group_ != "缸" and o.PartNo != "29"                # noqa: E731  轴测图不画定位销
    blk3 = lambda o: o.Group_ != "缸" and o.PartNo not in ("28", "29")    # noqa: E731  单独阀块的正投影不画螺栓、销
    above = (1000.0, 1000.0, 1000.0, V(-500.0, -500.0, 0.0))             # 螺栓只画阀块安装面以上部分
    F[2] = dict(title="集成锁闭阀块轴测图", dir=(-0.55, -1.0, 0.7), up=(0, 0, 1), filter=blk2, min_part_mm=0.6,
                crop_part={"28": above},
                labels=["2", "28", "41", "42", "43", "44", "45", "71", "72", "74", "75"])
    # ---- 图3：主视（前侧面）
    F[3] = dict(title="集成锁闭阀块主视图", dir=(0, -1, 0), up=(0, 0, 1), filter=blk3, min_part_mm=0.5, cols="TB",
                labels=["2", "41", "42", "43", "44", "45", "71", "72", "74", "75", ("64", {"at": (224, 0, 7.2)}), "20"])
    # ---- 图4：后视（后侧面，外接油口）
    F[4] = dict(title="集成锁闭阀块后视图", dir=(0, 1, 0), up=(0, 0, 1), filter=blk3, min_part_mm=0.5, cols="TB",
                labels=["2", "41", "42", "43", "44", "45", "51", "52", "53", "54", "55", "74"])
    # ---- 图5：过泄放阀孔轴线、垂直于缸轴的平面 X=176 剖开，自后端向前看（无杆腔锁闭侧）；剖切面后方的其他阀与接头省略不画
    f5 = lambda o: o.Group_ == "缸" or o.PartNo in ("2", "43", "43c", "43p", "43o", "71", "76")   # noqa: E731
    F[5] = dict(title="沿泄放阀孔轴线的横向剖视图", dir=(1, 0, 0), up=(0, 0, 1), section="x", sec_keep="neg",
                shift=(-176.0, 0.0, 0.0), filter=f5, min_part_mm=0.4,
                labels=["2", "11", "16", "43", "71", "76", ("33", {"at": (176, 54.4, 35.0)}), ("53", {"at": (176, 80, 40)}),
                        ("61", {"at": (176, 28, 14), "side": "L", "ly": -55.0}), ("25", {"at": (176, 46.5, 12.2)})])
    # ---- 图6：过安全阀孔轴线、垂直于缸轴的平面 X=121.5 剖开（有杆腔锁闭侧）；剖切面后方的其他阀省略不画
    f6 = lambda o: o.Group_ == "缸" or o.PartNo in ("2", "45", "45p", "45o", "75")   # noqa: E731
    F[6] = dict(title="沿安全阀孔轴线的横向剖视图", dir=(1, 0, 0), up=(0, 0, 1), section="x", sec_keep="neg",
                shift=(-121.5, 0.0, 0.0), filter=f6, min_part_mm=0.4,
                labels=["2", "11", "14", "15", "45", "75", ("35", {"at": (121.5, 36.6, 44)}), ("55", {"at": (121.5, 80, 44)}),
                        ("65", {"at": (121.5, 28, 24)}), ("26", {"at": (121.5, 45, 14)})])
    # ---- 图7：图1 中第一锁闭阀孔、第一主孔道与油温传感器套管处的局部放大
    F[7] = dict(title="图1 的局部放大图", dir=(0, -1, 0), up=(0, 0, 1), section="y", shift=(0.0, -YC, 0.0), filter=allp,
                nosec={"15"}, same_items_as=1, min_part_mm=0.2, hatch_scale=0.8,
                detail={"center": lambda: V(226.0, 0.0, 8.0), "r": 44.0},
                labels=["2", "13", "18", ("21", {"at": (226.0, 45, 0.25), "side": "L", "ly": -9.0}), "23", "25", "27", "31",
                        "36", "41", "63", "73", "74"])
    # ---- 图8：图1 中第二锁闭阀孔、第二主孔道与第二测压孔处的局部放大
    F[8] = dict(title="图1 的另一局部放大图", dir=(0, -1, 0), up=(0, 0, 1), section="y", shift=(0.0, -YC, 0.0), filter=allp,
                nosec={"15"}, same_items_as=1, min_part_mm=0.2, hatch_scale=0.8,
                detail={"center": lambda: V(34.0, 0.0, 12.0), "r": 44.0},
                labels=["2", "12", "19", ("22", {"at": (24.0, 45, 0.25), "side": "L", "ly": -9.0}), "24", "26", "27", "32",
                        ("34", {"at": (64.8, 45, 38)}), "42", "62", "72"])
    return F


def main():
    M = Model()
    F = fig_specs()
    sel = os.environ.get("FIGS", "")
    ids = [int(x) for x in sel.split(",") if x.strip()] or sorted(F)
    cache, reps = {}, []
    for fid in ids:
        spec = F[fid]
        if spec.get("same_items_as") and spec["same_items_as"] not in cache:
            cache[spec["same_items_as"]] = build_items(M, F[spec["same_items_as"]])
        try:
            reps.append(render(M, fid, spec, cache))
        except Exception:  # noqa: BLE001
            reps.append({"fig": fid, "error": traceback.format_exc()[-2500:]})
    os.makedirs(OUT_L, exist_ok=True)
    with open(os.path.join(OUT_L, "_report_%s.json" % (sel.replace(",", "_") or "all")), "w", encoding="utf-8") as fh:
        json.dump(reps, fh, ensure_ascii=False, indent=1)


main()
