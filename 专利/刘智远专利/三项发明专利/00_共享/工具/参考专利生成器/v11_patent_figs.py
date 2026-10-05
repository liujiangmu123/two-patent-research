# -*- coding: utf-8 -*-
"""V11 发明专利说明书附图生成（freecadcmd 无头运行）。

输入：出图表达模型（与 V11 生产模型布置、尺寸完全一致，只省略 ≤2 mm 倒角/圆角、孔口锪角、刻线刻字、滚花等细节）。
流程：取零件 → 按工作位姿（ψ=0、ε=20°）放置 → 去掉承载基础与地面以下部分（跨地面的零件在地面处截断）→
      旋转到视图坐标 → TechDraw.projectEx 求可见轮廓（只取可见锐边与轮廓线）→ 按印刷尺寸合并重合线条、删碎线 →
      剖视图画剖面线 → 深度缓冲求每个零件的可见区域。
标注（按专利附图惯例）：只标注权利要求与说明书中要叙述的结构件，标准紧固件（螺栓、螺钉、螺母、垫圈、销、挡圈）不标；
      引线为细实线，末端落在零件可见面内并画小圆点（虚拟几何点画圆圈十字）；标号排在图形两侧的竖列中；
      引线布局由优化求得：引线互不交叉、不从其他标注点旁掠过、落点离零件轮廓有足够距离。
输出两套：附图/标注版/图N.png|svg|json 与 附图/无标注版/图N.png|svg（几何完全相同、同一比例）。

    FIGS=1,2,3 freecadcmd v11_patent_figs.py        （缺省全部）
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
MODEL = os.environ.get("V11_FCSTD", os.path.join(ROOT, "06_发明专利申请_V11", "出图模型", "InSAR_GNSS_V11_出图表达模型.FCStd"))
FIG_ROOT = os.environ.get("V11_FIG_ROOT", os.path.join(ROOT, "06_发明专利申请_V11"))     # V12：输出到 08_… 版本目录
OUT_L = os.path.join(FIG_ROOT, "附图", "标注版")
OUT_C = os.path.join(FIG_ROOT, "附图", "无标注版")
NUMS = {k: v for k, v in json.load(open(os.path.join(HERE, "v11_patent_numerals.json"), encoding="utf-8")).items()
        if not k.startswith("_")}

X45, OZ = 707.0, 915.0
O = V(X45, 0.0, OZ)
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
NONMETAL = ("PEEK", "POM", "EPDM", "PA66", "尼龙", "ASA", "玻璃钢", "聚碳", "锚固胶")
NEVER = ("11", "4542", "W632")  # 承载基础、锚固胶、地下焊缝：任何附图都不画


# ================================================================== 模型与位姿
class Model:
    def __init__(self):
        self.doc = App.openDocument(MODEL)
        self.objs = [o for o in self.doc.Objects if o.TypeId == "Part::Feature" and hasattr(o, "PartNo")]
        self.by_pno = {}
        for o in self.objs:
            self.by_pno.setdefault(o.PartNo, []).append(o)


def pl_M(yaw, pitch, dz=0.0):
    y = App.Placement(V(0, 0, 0), App.Rotation(V(0, 0, 1), yaw), O)
    p = App.Placement(V(0, 0, 0), App.Rotation(V(0, 1, 0), -pitch), O)
    return App.Placement(V(0, 0, dz), App.Rotation()).multiply(y).multiply(p)


ROT_WITH_ARM = {"14", "142", "143", "1431", "31", "33", "32", "35", "351", "36", "361", "362", "34", "144", "1441",
                "1442", "391", "392", "393", "394", "395"}


def pose_of(o, yaw=0.0, pitch=20.0, dz=0.0, A=0.0):
    g = o.MotionGroup
    if g == "M":
        pl = pl_M(yaw - A, pitch, dz)
    elif g == "R":
        pl = App.Placement(V(0, 0, dz), App.Rotation())
    else:
        pl = App.Placement()
    if A and (g in ("R", "M") or o.PartNo in ROT_WITH_ARM):
        pl = App.Placement(V(0, 0, 0), App.Rotation(V(0, 0, 1), A)).multiply(pl)
    return pl


def point_world(num, yaw=0.0, pitch=20.0, dz=0.0, A=0.0):
    d = NUMS[num]
    p = V(*d["point"])
    if d.get("group", "F") == "M":
        p = pl_M(yaw - A, pitch, dz).multVec(p)
        if A:
            p = App.Rotation(V(0, 0, 1), A).multVec(p)
    return p


def o_world(yaw=0.0, pitch=20.0, dz=0.0, A=0.0):
    p = V(O.x, O.y, O.z + dz)
    return App.Rotation(V(0, 0, 1), A).multVec(p) if A else p


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
        pl = pose_of(o, yaw, pitch, dz, A)
        if not pl.isIdentity():
            s.transformShape(pl.toMatrix(), True)
        bb = s.BoundBox
        if bb.ZMax <= 0.5:
            continue
        if bb.ZMin < -0.5:
            s = s.common(ABOVE)
            if s.isNull() or not s.Solids:
                continue
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
            unsec = o.Kind in ("标准件",) or o.PartNo in nosec
            if hi_ <= 0.0:
                continue
            if not unsec and lo_ < 0.0:
                half = Part.makeBox(1e4, 1e4, 1e4, V(0.0, -5e3, -5e3) if ax_ == "x" else V(-5e3, 0.0, -5e3))
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
                idx = sorted([i for i in range(n) if st[i][1] == sd], key=lambda i: -A[i, 1])
                ys = spread([A[i, 1] for i in idx], lo, hi, GAP / s)
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
        if "point" in d:
            p = P(point_world(num, spec.get("yaw", 0), spec.get("pitch", 20), spec.get("dz", 0), spec.get("A", 0)))
            labels.append(dict(num=num, name=d["name"], kind="point", side=opt.get("side"), cands=[(p[0], p[1], 1e3)]))
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
        labels.append(dict(num=num, name=d["name"], kind="part", side=opt.get("side"), cands=cands, keys=sorted(keys)))
    return labels, missing


def render(M, fid, spec, cache):
    t0 = time.time()
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
            angs = spec.get("hatch_angle", {})
            k = 0
            for key, o, sh, sec in items:
                if not sec:
                    continue
                nm = any(t in o.Material for t in NONMETAL)
                ang = angs.get(o.PartNo, 45.0 if k % 2 == 0 else 135.0)
                k += 1
                hatches += hatch_segments(R, key, ang, spec.get("hatch_mm", 1.5) * R.q / s, cross=nm)
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
def st(o, *ks):
    return any(o.Structure.startswith(str(k)) for k in ks)


def f_whole(o):
    return o.PartNo != "632"          # 接地引线地面段只在图 12 表达，整机图中省略


def annot_fig3(ax, P, s, box):
    """剖切符号：粗短画 + 投射方向箭头 + 字母。A-A 为 y=0 平面（自 -Y 向 +Y 投射），B-B 为 x=0 平面（自 -X 向 +X 投射）。"""
    for letter, pts, dvec in (("A", ((560.0, 0.0), (850.0, 0.0)), (0.0, 1.0)), ("B", ((0.0, -205.0), (0.0, 205.0)), (1.0, 0.0))):
        for k, (x, y) in enumerate(pts):
            p = np.array(P(V(x, y, 2300)))
            d = np.array(dvec)
            n = np.array([-d[1], d[0]])
            ax.plot([p[0] - d[0] * 2.2 / s, p[0] + d[0] * 2.2 / s], [p[1] - d[1] * 2.2 / s, p[1] + d[1] * 2.2 / s],
                    color="k", lw=0.5 * PT)
            b = p + d * 2.2 / s
            arrow(ax, b, b + d * 5.3 / s, s, lw=LW_L, head=2.2)
            sg = 1.0 if k == 1 else -1.0
            t_ = b + d * 4.5 / s + n * sg * 3.0 / s * (1 if letter == "A" else -1)
            ax.text(t_[0], t_[1], letter, fontsize=FS, ha="center", va="center")


def annot_fig5(ax, P, s, box):
    ax.text(0.5 * (box[0] + box[1]), box[3] + 4.0 / s, "B-B", fontsize=FS, ha="center", va="bottom")


def annot_fig9(ax, P, s, box):
    o2 = np.array(P(o_world()))
    mark(ax, o2, s, 0.8)
    ax.text(o2[0] + 2.2 / s, o2[1] + 2.2 / s, "$O$", fontsize=FS, ha="left", va="bottom")
    top = np.array(P(V(632.0 - 14.0, 0, 850.0)))
    apex = np.array(P(V(632.0, 0, 880.0)))
    x_d = P(V(632.0 - 30.0, 0, 0))[0]
    for y, xe in ((top[1], top[0]), (apex[1], apex[0])):
        ax.plot([x_d - 1.5 / s, xe], [y, y], color="k", lw=LW_T * PT)
    mm = np.array([x_d, 0.5 * (top[1] + apex[1])])
    arrow(ax, mm, (x_d, top[1]), s, lw=LW_T)
    arrow(ax, mm, (x_d, apex[1]), s, lw=LW_T)
    ax.text(x_d - 1.6 / s, mm[1], "$H$", fontsize=FS, ha="right", va="center")
    arrow(ax, apex, o2, s, lw=0.25, head=2.8, text="$\\boldsymbol{q}_0$", toff=(4.5, -1.5))
    ax.text(0.5 * (box[0] + box[1]), box[3] + 4.0 / s, "A-A", fontsize=FS, ha="center", va="bottom")


def vec_anchor_37(P, pose=None):
    kw = pose or {}
    a = np.array(P(point_world("25", **kw)))
    b = np.array(P(point_world("43", **kw)))
    return tuple(a + 0.62 * (b - a))


def annot_fig13(ax, P, s, box):
    p25 = np.array(P(point_world("25")))
    p425 = np.array(P(V(632.0, 0, 880.0)))
    p43 = np.array(P(point_world("43")))
    mark(ax, p425, s, 0.6, cross=False)
    arrow(ax, p25, p425, s, lw=0.25, head=3.0, text="$\\boldsymbol{S}_1$", toff=(-5.5, 0))
    arrow(ax, p425, p43, s, lw=0.25, head=3.0, text="$\\boldsymbol{S}_2$", toff=(-6.0, 1.0))
    arrow(ax, p25, p43, s, lw=0.4, head=3.4)
    xr = P(V(-125.0, 0, 0))[0]
    ref = P(V(0, 0, 850.0))[1]
    chain(ax, (xr - 1.5 / s, ref), (P(V(560, 0, 0))[0], ref), s)
    ax.plot([xr - 1.5 / s, p25[0]], [p25[1], p25[1]], color="k", lw=LW_T * PT)
    mm = (xr, 0.5 * (ref + p25[1]))
    arrow(ax, mm, (xr, ref), s, lw=LW_T)
    arrow(ax, mm, (xr, p25[1]), s, lw=LW_T)
    ax.text(xr - 1.6 / s, mm[1], "$c$", fontsize=FS, ha="right", va="center")
    yl = box[2] - 7.0 / s
    chain(ax, (p25[0], yl - 1.5 / s), (p25[0], box[2] + 4.0 / s), s)
    chain(ax, (p425[0], yl - 1.5 / s), (p425[0], p425[1] - 1.2 / s), s)
    mm = (0.5 * (p25[0] + p425[0]), yl)
    arrow(ax, mm, (p25[0], yl), s, lw=LW_T)
    arrow(ax, mm, (p425[0], yl), s, lw=LW_T)
    ax.text(mm[0], yl + 1.2 / s, "$L$", fontsize=FS, ha="center", va="bottom")


def annot_fig14(ax, P, s, box):
    A, psi = 35.0, 70.0
    kw = {"A": A, "yaw": psi}
    p25 = np.array(P(point_world("25", **kw)))
    p425 = np.array(P(App.Rotation(V(0, 0, 1), A).multVec(V(632.0, 0, 880.0))))
    pO = np.array(P(o_world(A=A)))
    p43 = np.array(P(point_world("43", **kw)))
    mark(ax, p425, s, 0.6, cross=False)
    mark(ax, pO, s, 0.7)
    ax.text(pO[0] + 1.8 / s, pO[1] - 1.5 / s, "$O$", fontsize=FS, ha="left", va="top")
    chain(ax, p25, (p25[0] + 870.0, p25[1]), s)
    angle_arc(ax, p25, 250.0, 0.0, A, s, "$A$", tr=1.12)
    dim(ax, p25, p425, 10.0, s, "$L$", toff=(-3.0, 4.0))
    chain(ax, pO, (pO[0] + 300.0, pO[1]), s)
    b = pO + 330.0 * np.array([math.cos(math.radians(psi)), math.sin(math.radians(psi))])
    arrow(ax, pO, b, s, lw=LW_L, head=2.8, style=(0, (8, 1.8, 1.2, 1.8)))
    angle_arc(ax, pO, 150.0, 0.0, psi, s, "$\\psi$", tr=1.25)
    arrow(ax, p25, p43, s, lw=0.4, head=3.4)


def annot_fig15(ax, P, s, box):
    pO = np.array(P(o_world()))
    mark(ax, pO, s, 0.7)
    ax.text(pO[0] + 2.0 / s, pO[1] - 1.8 / s, "$O$", fontsize=FS, ha="left", va="top")
    chain(ax, pO, (pO[0] + 175.0, pO[1]), s)
    p43 = np.array(P(point_world("43", pitch=10.0)))
    arrow(ax, pO, p43, s, lw=0.25, head=2.8, text="$\\boldsymbol{d}$", toff=(0.0, 4.0))
    for e, r, t in ((10.0, 115.0, "$\\varepsilon_1$"), (32.0, 150.0, "$\\varepsilon_2$")):
        chain(ax, pO, (pO[0] + (r + 22) * math.cos(math.radians(e)), pO[1] + (r + 22) * math.sin(math.radians(e))), s)
        angle_arc(ax, pO, r, 0.0, e, s, t, tr=1.2)


def annot_fig7(ax, P, s, box):
    r = 150.0
    c = np.array(P(o_world() + V(0, 0, 10.0)))
    ax.add_patch(plt.Circle(c, r, fill=False, lw=LW_T * PT, color="k"))
    e = c + r * np.array([0.707, -0.707])
    f = e + np.array([8.0 / s, -8.0 / s])
    ax.plot([e[0], f[0]], [e[1], f[1]], color="k", lw=LW_L * PT)
    ax.text(f[0] + 0.8 / s, f[1] - 0.8 / s, "I", fontsize=FS, ha="left", va="top")


def fig_specs():
    """每张图只标注说明书要叙述的结构件；标准紧固件一律不标。"""
    right_top = lambda o: o.MotionGroup in ("R", "M")  # noqa: E731
    arm = {"34", "391", "392", "393", "394", "395"}
    rod = {"38", "381", "3811", "425"}
    refl_only = lambda o: o.PartNo in ("42", "44")      # noqa: E731
    iso = (0.55, -1.0, 0.6)
    F = {}
    F[1] = dict(title="整机立体图", dir=iso, filter=f_whole,
                labels=["1", "2", "3", "4", "5", "6", "13", "21", "42", "45", "53", "61"])
    F[2] = dict(title="整机主视图", dir=(0, -1, 0), filter=f_whole,
                labels=["12", "13", "14", "15", "21", "24", "31", "34", "35", "41", "42", "44", "451", "453",
                        "454", "51", "53", "61", "611", "62"])
    F[3] = dict(title="整机俯视图", dir=(0, 0, 1), up=(0, 1, 0), filter=f_whole, annot=annot_fig3, cols="TB",
                labels=["12", "21", "31", "42", "44", "454", "53", "61", "611"])
    F[4] = dict(title="基础支撑结构立体图", dir=(0.9, -1.0, 0.65),
                filter=lambda o: st(o, 1) and o.PartNo not in ("W13", "W15"),
                crop=(-1e4, 1e4, -1e4, 1e4, -2e3, 520.0),
                labels=["12", "13", "132", "15", "151"])
    F[5] = dict(title="GNSS测量结构剖视图", dir=(-1, 0, 0), section="x", wavy=True, annot=annot_fig5,
                filter=lambda o: st(o, 2) or o.PartNo in ("131", "13"),
                crop=(-1e4, 1e4, -190.0, 190.0, 1945.0, 2260.0), nosec={"22", "243", "248"}, top_mm=10.0,
                labels=["13", "131", "241", "242", "243", "23", "22", "21", "25"])
    F[6] = dict(title="偏置连接结构立体图", dir=(1.0, 0.75, 0.7),
                filter=lambda o: (st(o, 3) and o.MotionGroup == "F") or o.PartNo in {"13", "456"} | rod,
                crop_part={"13": (230, 230, 200, V(-115, -115, 735))},
                labels=["13", "14", "141", "31", "32", "33", "34", "36", "38", "39", "456"])
    F[7] = dict(title="角反射器安装结构立体图", dir=iso, annot=annot_fig7,
                filter=lambda o: right_top(o) or o.PartNo in arm | rod,
                crop_part={"34": (100, 100, 100, V(575, -50, 800))},
                labels=["34", "41", "421", "422", "423", "43", "44", "451", "453", "454", "455", "457"])
    F[8] = dict(title="图7中I处局部放大图", dir=iso, same_items_as=7, min_part_mm=0.6,
                filter=lambda o: right_top(o) or o.PartNo in arm | rod,
                crop_part={"34": (100, 100, 100, V(575, -50, 800))},
                detail=dict(center=lambda: o_world() + V(0, 0, 10.0), r=150.0), wmax=150.0,
                labels=["34", "38", "39", "411", "412", "413", "425", "44", "455", "456"])
    F[9] = dict(title="A—A剖视图", dir=(0, -1, 0), section=True, wavy=True, annot=annot_fig9, min_part_mm=0.6,
                filter=lambda o: right_top(o) or o.PartNo in arm | rod,
                crop=(588.0, 842.0, -1e4, 1e4, 738.0, 1072.0), nosec={"412", "414", "22"}, hatch_mm=1.6, top_mm=10.0,
                labels=["34", "38", "391", "392", "411", "412", "413", "414", "424", "425", "44", "455", "456"])
    F[10] = dict(title="地面支撑组件立体图", dir=(0.9, -1.0, 0.6),
                 filter=lambda o: o.MotionGroup == "R" and st(o, 4) and o.Shape.BoundBox.ZMax < 870,
                 labels=["451", "452", "453", "454", "455", "456", "457"])
    F[11] = dict(title="防护供电结构立体图（拆去柜门）", dir=(-1.0, -0.4, 0.28),
                 filter=lambda o: (st(o, 5) and o.PartNo not in ("510", "5101", "5102", "5103")) or o.PartNo in ("64", "13"),
                 crop_part={"13": (230, 230, 760, V(-115, -115, 430))},
                 labels=["13", "51", "52", "53", "54", "55", "57", "58", "64"])
    F[12] = dict(title="防雷接地结构立体图", dir=(-0.8, -1.0, 0.45),
                 filter=lambda o: ((st(o, 6) and o.PartNo != "64") or st(o, 1, 2)) and o.PartNo not in ("W13", "W15", "W62", "W611"),
                 labels=["12", "13", "21", "61", "611", "62", "632"])
    up_part = lambda o: o.Shape.BoundBox.ZMax > 760  # noqa: E731
    F[13] = dict(title="空间偏置量测定关系图（主视方向）", dir=(0, -1, 0), wavy=True,
                 filter=lambda o: ((st(o, 2, 3) or o.PartNo in ("13", "131")) or right_top(o)) and up_part(o),
                 crop=(-1e4, 1e4, -1e4, 1e4, 760.0, 1e4), annot=annot_fig13, bottom_mm=12.0,
                 vec_anchor={"37": lambda P: vec_anchor_37(P)},
                 labels=["13", "25", "31", "34", ("37", {"side": "R"}), "38", "425", "43", "44"])
    F[14] = dict(title="空间偏置量测定关系图（俯视方向）", dir=(0, 0, 1), up=(0, 1, 0), A=35.0, yaw=70.0,
                 filter=lambda o: (o.PartNo in ("13", "141", "1411") or (st(o, 3) and o.MotionGroup == "F")
                                   or o.MotionGroup == "R" or o.PartNo in rod),
                 phantom=dict(filter=refl_only, phantom=None), crop=(-1e4, 1e4, -1e4, 1e4, 760.0, 1e4),
                 annot=annot_fig14, top_mm=6.0, vec_anchor={"37": lambda P: vec_anchor_37(P, {"A": 35.0, "yaw": 70.0})},
                 labels=["14", "25", "31", "34", ("37", {"side": "R"}), "425", "43"])
    F[15] = dict(title="姿态调节示意图", dir=(0, -1, 0), pitch=10.0,
                 filter=lambda o: right_top(o) or o.PartNo in arm | rod,
                 crop_part={"34": (100, 100, 100, V(575, -50, 800))},
                 phantom=dict(pitch=32.0, filter=refl_only, phantom=None),
                 annot=annot_fig15, labels=["41", "42", "43", "44", "45"])
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


if not getattr(App, "_V11_FIGS_DONE", False):
    App._V11_FIGS_DONE = True
    main()
