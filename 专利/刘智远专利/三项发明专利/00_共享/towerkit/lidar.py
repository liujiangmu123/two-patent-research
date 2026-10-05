# -*- coding: utf-8 -*-
"""机载激光扫描仿真：角钢两肢薄板几何、均匀网格加速的光线投射（numba 并行）、扫描器与航迹模型。

坐标：世界系 ENU（x 东/横担方向，y 北，z 上）；机体系 x 前、y 左、z 上；传感器系 x 为视轴。
扫描器：
  * ``rotating``：多线旋转式（自转轴为传感器 z），如 Hesai XT32；
  * ``rosette``：非重复花瓣式（Livox Avia 类），视轴 x，两轴正弦组合充满视场。
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
from numba import njit, prange

from . import sections as S
from .graph import TrussGraph


# ====================================================================== 几何
@dataclass
class Geometry:
    P0: np.ndarray      # (K,3) 薄板原点（肢背线起点）
    U: np.ndarray       # (K,3) 沿杆轴单位向量
    Lu: np.ndarray      # (K,) 长度
    W: np.ndarray       # (K,3) 肢宽方向单位向量
    Lw: np.ndarray      # (K,) 肢宽
    N: np.ndarray       # (K,3) 法向
    member: np.ndarray  # (K,) 所属杆件（附加物为 -2）
    n_members: int
    grid: tuple = field(default=None, repr=False)


def _perp(v, u):
    v = v - (v @ u) * u
    n = np.linalg.norm(v)
    return v / n if n > 1e-9 else None


def build_geometry(g: TrussGraph, include_attachments: bool = True, cell: float = 0.6) -> Geometry:
    P0, U, Lu, W, Lw, mem = [], [], [], [], [], []
    X = g.nodes
    base = g.meta.get("base_nodes", [])
    cen_xy = np.mean(X[base, :2], axis=0) if base else np.zeros(2)

    def add_angle(p0, p1, b, e, legs=None):
        d = p1 - p0
        L = float(np.linalg.norm(d))
        if L < 1e-6:
            return
        u = d / L
        if legs is None:
            mid = 0.5 * (p0 + p1)
            to_c = np.array([cen_xy[0] - mid[0], cen_xy[1] - mid[1], 0.0])
            w1 = _perp(to_c, u) if np.linalg.norm(to_c) > 1e-6 else None
            if w1 is None:
                w1 = _perp(np.array([1.0, 0.0, 0.0]), u)
                if w1 is None:
                    w1 = _perp(np.array([0.0, 1.0, 0.0]), u)
            w2 = np.cross(u, w1)
            legs = (w1, w2)
        for w in legs:
            P0.append(p0); U.append(u); Lu.append(L); W.append(w); Lw.append(b); mem.append(e)

    for e in range(g.n_members):
        a, b = X[g.mi[e]], X[g.mj[e]]
        bw = S.angle(g.sec[e]).b if g.sec[e] else 0.07
        legs = None
        if g.cat[e] == "main" and g.part[e] == "body":
            sx = np.sign(0.5 * (a[0] + b[0]) - cen_xy[0]) or 1.0
            sy = np.sign(0.5 * (a[1] + b[1]) - cen_xy[1]) or 1.0
            u = (b - a) / np.linalg.norm(b - a)
            w1, w2 = _perp(np.array([-sx, 0, 0.0]), u), _perp(np.array([0, -sy, 0.0]), u)
            legs = (w1, w2) if w1 is not None and w2 is not None else None
        off = np.asarray(g.bend[e], float)
        if np.linalg.norm(off) > 1e-9:
            m = 0.5 * (a + b) + off
            add_angle(a, m, bw, e); add_angle(m, b, bw, e)
        else:
            add_angle(a, b, bw, e, legs)
    if include_attachments:
        for att in g.meta.get("attachments", []):
            c, s = np.asarray(att["center"], float), float(att["size"])
            h = s / 2
            for ax in range(3):
                for sg in (-1, 1):
                    o = c.copy(); o[ax] += sg * h
                    ua = np.eye(3)[(ax + 1) % 3]; wa = np.eye(3)[(ax + 2) % 3]
                    P0.append(o - h * ua - h * wa); U.append(ua); Lu.append(s); W.append(wa); Lw.append(s)
                    mem.append(-2)
    P0, U, W = np.asarray(P0), np.asarray(U), np.asarray(W)
    N = np.cross(U, W)
    N /= np.linalg.norm(N, axis=1, keepdims=True)
    geom = Geometry(P0, U, np.asarray(Lu), W, np.asarray(Lw), N, np.asarray(mem, np.int64), g.n_members)
    geom.grid = _build_grid(geom, cell)
    return geom


def _build_grid(geom: Geometry, cell: float):
    c0 = geom.P0
    c1 = geom.P0 + geom.U * geom.Lu[:, None]
    c2 = geom.P0 + geom.W * geom.Lw[:, None]
    c3 = c1 + geom.W * geom.Lw[:, None]
    allc = np.stack([c0, c1, c2, c3], axis=1)
    lo, hi = allc.min(axis=1), allc.max(axis=1)
    gmin = lo.min(axis=0) - 0.05
    gmax = hi.max(axis=0) + 0.05
    dims = np.maximum(np.ceil((gmax - gmin) / cell).astype(np.int64), 1)
    i0 = np.clip(((lo - gmin) / cell).astype(np.int64), 0, dims - 1)
    i1 = np.clip(((hi - gmin) / cell).astype(np.int64), 0, dims - 1)
    cstart, citems = _fill_grid(i0, i1, dims)
    return gmin, float(cell), dims, cstart, citems


@njit(cache=True)
def _fill_grid(i0, i1, dims):
    ncell = dims[0] * dims[1] * dims[2]
    cnt = np.zeros(ncell + 1, np.int64)
    K = i0.shape[0]
    for k in range(K):
        for x in range(i0[k, 0], i1[k, 0] + 1):
            for y in range(i0[k, 1], i1[k, 1] + 1):
                for z in range(i0[k, 2], i1[k, 2] + 1):
                    cnt[x + dims[0] * (y + dims[1] * z) + 1] += 1
    for c in range(ncell):
        cnt[c + 1] += cnt[c]
    pos = cnt[:-1].copy()
    items = np.empty(cnt[-1], np.int64)
    for k in range(K):
        for x in range(i0[k, 0], i1[k, 0] + 1):
            for y in range(i0[k, 1], i1[k, 1] + 1):
                for z in range(i0[k, 2], i1[k, 2] + 1):
                    c = x + dims[0] * (y + dims[1] * z)
                    items[pos[c]] = k
                    pos[c] += 1
    return cnt, items


@njit(parallel=True, cache=True)
def _cast(orig, dirs, tmax, P0, U, Lu, W, Lw, Nn, gmin, cell, dims, cstart, citems, out_t, out_k):
    nr = orig.shape[0]
    gmax0 = gmin[0] + dims[0] * cell
    gmax1 = gmin[1] + dims[1] * cell
    gmax2 = gmin[2] + dims[2] * cell
    for r in prange(nr):
        o0, o1, o2 = orig[r, 0], orig[r, 1], orig[r, 2]
        d0, d1, d2 = dirs[r, 0], dirs[r, 1], dirs[r, 2]
        out_t[r] = -1.0
        out_k[r] = -1
        # 与网格包围盒求交（slab）
        t0, t1 = 0.0, tmax
        ok = True
        for ax in range(3):
            o = o0 if ax == 0 else (o1 if ax == 1 else o2)
            d = d0 if ax == 0 else (d1 if ax == 1 else d2)
            lo = gmin[ax]
            hi = gmax0 if ax == 0 else (gmax1 if ax == 1 else gmax2)
            if abs(d) < 1e-12:
                if o < lo or o > hi:
                    ok = False
            else:
                ta, tb = (lo - o) / d, (hi - o) / d
                if ta > tb:
                    ta, tb = tb, ta
                if ta > t0:
                    t0 = ta
                if tb < t1:
                    t1 = tb
        if not ok or t0 > t1:
            continue
        te = t0 + 1e-7
        px, py, pz = o0 + d0 * te, o1 + d1 * te, o2 + d2 * te
        ix = min(max(int((px - gmin[0]) / cell), 0), dims[0] - 1)
        iy = min(max(int((py - gmin[1]) / cell), 0), dims[1] - 1)
        iz = min(max(int((pz - gmin[2]) / cell), 0), dims[2] - 1)
        sx = 1 if d0 > 0 else -1
        sy = 1 if d1 > 0 else -1
        sz = 1 if d2 > 0 else -1
        inf = 1e30
        tdx = abs(cell / d0) if abs(d0) > 1e-12 else inf
        tdy = abs(cell / d1) if abs(d1) > 1e-12 else inf
        tdz = abs(cell / d2) if abs(d2) > 1e-12 else inf
        nbx = gmin[0] + (ix + (1 if sx > 0 else 0)) * cell
        nby = gmin[1] + (iy + (1 if sy > 0 else 0)) * cell
        nbz = gmin[2] + (iz + (1 if sz > 0 else 0)) * cell
        tmx = (nbx - o0) / d0 if abs(d0) > 1e-12 else inf
        tmy = (nby - o1) / d1 if abs(d1) > 1e-12 else inf
        tmz = (nbz - o2) / d2 if abs(d2) > 1e-12 else inf
        best = t1
        bk = -1
        while True:
            c = ix + dims[0] * (iy + dims[1] * iz)
            for q in range(cstart[c], cstart[c + 1]):
                k = citems[q]
                den = d0 * Nn[k, 0] + d1 * Nn[k, 1] + d2 * Nn[k, 2]
                if abs(den) < 1e-12:
                    continue
                t = ((P0[k, 0] - o0) * Nn[k, 0] + (P0[k, 1] - o1) * Nn[k, 1] + (P0[k, 2] - o2) * Nn[k, 2]) / den
                if t <= 1e-6 or t >= best:
                    continue
                vx, vy, vz = o0 + t * d0 - P0[k, 0], o1 + t * d1 - P0[k, 1], o2 + t * d2 - P0[k, 2]
                a = vx * U[k, 0] + vy * U[k, 1] + vz * U[k, 2]
                if a < 0.0 or a > Lu[k]:
                    continue
                b = vx * W[k, 0] + vy * W[k, 1] + vz * W[k, 2]
                if b < 0.0 or b > Lw[k]:
                    continue
                best = t
                bk = k
            tnext = min(tmx, min(tmy, tmz))
            if bk >= 0 and best <= tnext:
                break
            if tnext > t1:
                break
            if tmx <= tmy and tmx <= tmz:
                ix += sx; tmx += tdx
                if ix < 0 or ix >= dims[0]:
                    break
            elif tmy <= tmz:
                iy += sy; tmy += tdy
                if iy < 0 or iy >= dims[1]:
                    break
            else:
                iz += sz; tmz += tdz
                if iz < 0 or iz >= dims[2]:
                    break
        if bk >= 0:
            out_t[r] = best
            out_k[r] = bk


def cast_rays(geom: Geometry, orig: np.ndarray, dirs: np.ndarray, tmax: float = 300.0):
    """返回 (t, plate)；未命中 t=-1, plate=-1。"""
    gmin, cell, dims, cstart, citems = geom.grid
    nr = len(orig)
    out_t = np.empty(nr); out_k = np.empty(nr, np.int64)
    _cast(np.ascontiguousarray(orig, float), np.ascontiguousarray(dirs, float), float(tmax), geom.P0, geom.U,
          geom.Lu, geom.W, geom.Lw, geom.N, gmin, cell, dims, cstart, citems, out_t, out_k)
    return out_t, out_k


# ====================================================================== 扫描器与航迹
@dataclass
class Scanner:
    kind: str = "rosette"            # rosette | rotating
    prr: float = 240e3               # 点频 pts/s
    fov_h: float = 70.4              # 花瓣式水平视场（°）
    fov_v: float = 77.2              # 花瓣式竖直视场（°）
    f1: float = 1013.0               # 花瓣式两轴扫描频率（Hz，非整数比 → 非重复）
    f2: float = 1291.7
    n_lines: int = 32                # 旋转式线数
    v_fov: tuple = (-16.0, 15.0)     # 旋转式竖直视场
    rot_hz: float = 10.0
    range_sigma: float = 0.02        # 测距噪声 m
    divergence: float = math.radians(0.15)           # 光斑发散角 rad（Avia 0.28°×0.03°，取等效 0.15°）
    max_range: float = 190.0
    name: str = "LivoxAvia-like"

    def directions(self, t: np.ndarray) -> np.ndarray:
        """时间序列 → 传感器系单位方向。"""
        if self.kind == "rosette":
            ah = math.radians(self.fov_h) / 2
            av = math.radians(self.fov_v) / 2
            yaw = ah * np.sin(2 * np.pi * self.f1 * t)
            pit = av * np.sin(2 * np.pi * self.f2 * t + 0.7)
            # 六通道错位，提高瞬时覆盖
            ch = (np.arange(len(t)) % 6) - 2.5
            yaw = yaw + ch * 0.0035
            d = np.stack([np.cos(pit) * np.cos(yaw), np.cos(pit) * np.sin(yaw), np.sin(pit)], axis=1)
        else:
            k = np.arange(len(t))
            el = np.radians(np.linspace(self.v_fov[0], self.v_fov[1], self.n_lines))[k % self.n_lines]
            az = 2 * np.pi * self.rot_hz * t
            d = np.stack([np.cos(el) * np.cos(az), np.cos(el) * np.sin(az), np.sin(el)], axis=1)
        return d


def rot_zyx(yaw, pitch, roll):
    cy, sy, cp, spp, cr, sr = math.cos(yaw), math.sin(yaw), math.cos(pitch), math.sin(pitch), math.cos(roll), math.sin(roll)
    Rz = np.array([[cy, -sy, 0], [sy, cy, 0], [0, 0, 1]])
    Ry = np.array([[cp, 0, spp], [0, 1, 0], [-spp, 0, cp]])
    Rx = np.array([[1, 0, 0], [0, cr, -sr], [0, sr, cr]])
    return Rz @ Ry @ Rx


@dataclass
class Mount:
    """传感器相对机体的安装：yaw/pitch/roll（°）与杠杆臂（m）。pitch=-90° 为视轴竖直向下。"""
    yaw: float = 0.0
    pitch: float = -90.0
    roll: float = 0.0
    lever: tuple = (0.0, 0.0, -0.15)

    def R(self):
        # 视轴 x 先绕自身滚转，再俯仰（pitch<0 向下），再偏航（yaw>0 向左）。
        # 双倾角载荷：yaw=±90°、pitch=−(90°−θ) 即视轴自铅垂向左/右倾斜 θ。
        return rot_zyx(math.radians(self.yaw), -math.radians(self.pitch), math.radians(self.roll))

    def boresight(self):
        return self.R() @ np.array([1.0, 0.0, 0.0])


@dataclass
class Trajectory:
    t: np.ndarray
    pos: np.ndarray       # (n,3)
    yaw: np.ndarray       # (n,) 机头方位（自 x 轴逆时针，rad）

    def at(self, tq):
        p = np.stack([np.interp(tq, self.t, self.pos[:, k]) for k in range(3)], axis=1)
        y = np.interp(tq, self.t, np.unwrap(self.yaw))
        return p, y

    @property
    def length(self) -> float:
        return float(np.sum(np.linalg.norm(np.diff(self.pos, axis=0), axis=1)))

    @property
    def duration(self) -> float:
        return float(self.t[-1] - self.t[0])


def line_path(p_start, p_end, speed=8.0, dt=0.05) -> Trajectory:
    p0, p1 = np.asarray(p_start, float), np.asarray(p_end, float)
    L = np.linalg.norm(p1 - p0)
    n = max(2, int(L / speed / dt) + 1)
    s = np.linspace(0, 1, n)
    pos = p0 + s[:, None] * (p1 - p0)
    yaw = np.full(n, math.atan2(p1[1] - p0[1], p1[0] - p0[0]))
    return Trajectory(s * L / speed, pos, yaw)


def orbit_path(center, radius, z0, z1=None, turns=1.0, speed=4.0, dt=0.05, face_center=True) -> Trajectory:
    """环绕/螺旋航线（逆时针），机头朝向切向；face_center=True 时传感器偏航由 Mount 决定指向塔心。"""
    c = np.asarray(center, float)
    z1 = z0 if z1 is None else z1
    L = 2 * np.pi * radius * turns
    n = max(2, int(L / speed / dt) + 1)
    th = np.linspace(0, 2 * np.pi * turns, n)
    pos = np.stack([c[0] + radius * np.cos(th), c[1] + radius * np.sin(th), np.linspace(z0, z1, n)], axis=1)
    yaw = th + np.pi / 2
    return Trajectory(np.linspace(0, L / speed, n), pos, yaw)


def waypoint_path(points, speed=5.0, dt=0.05, yaws=None) -> Trajectory:
    pts = np.asarray(points, float)
    segs = np.linalg.norm(np.diff(pts, axis=0), axis=1)
    tt = np.concatenate([[0], np.cumsum(segs / speed)])
    n = max(2, int(tt[-1] / dt) + 1)
    tq = np.linspace(0, tt[-1], n)
    pos = np.stack([np.interp(tq, tt, pts[:, k]) for k in range(3)], axis=1)
    if yaws is None:
        d = np.gradient(pos, axis=0)
        yaw = np.arctan2(d[:, 1], d[:, 0])
    else:
        yaw = np.interp(tq, tt, np.unwrap(np.asarray(yaws, float)))
    return Trajectory(tq, pos, yaw)


def concat_paths(paths) -> Trajectory:
    t, pos, yaw = [], [], []
    off = 0.0
    for p in paths:
        t.append(p.t - p.t[0] + off); pos.append(p.pos); yaw.append(p.yaw)
        off = t[-1][-1] + 1e-3
    return Trajectory(np.concatenate(t), np.concatenate(pos), np.concatenate(yaw))


# ====================================================================== 扫描
def scan(geom: Geometry, traj: Trajectory, scanner: Scanner, mount: Mount, seed=0, block=0.002,
         pos_sigma=0.02, att_sigma_deg=0.01, decim: float = 1.0, sensor_id: int = 0, max_pulses: int = 8_000_000):
    """沿航迹扫描，返回点云字典（xyz, member, plate, sensor, t, cos_inc, range, origin）。

    decim<1 时按比例抽取脉冲（等效降低点频）以加速；返回的点数按抽取比例反映真实密度。
    """
    rng = np.random.default_rng(seed)
    T = traj.duration
    npulse = int(T * scanner.prr * decim)
    npulse = min(npulse, max_pulses)
    tp = np.sort(rng.uniform(traj.t[0], traj.t[-1], npulse)) if decim < 1 else \
        np.linspace(traj.t[0], traj.t[-1], npulse, endpoint=False)
    # 位姿（按 block 分段取中心位姿）
    tb = np.floor((tp - traj.t[0]) / block)
    tc = traj.t[0] + (tb + 0.5) * block
    pos, yaw = traj.at(tc)
    bias = rng.normal(0, pos_sigma, 3)
    pos = pos + bias + rng.normal(0, pos_sigma * 0.3, pos.shape)
    Rm = mount.R()
    dsens = scanner.directions(tp)
    dbody = dsens @ Rm.T
    att = np.radians(att_sigma_deg)
    cy, sy = np.cos(yaw + rng.normal(0, att, len(yaw))), np.sin(yaw + rng.normal(0, att, len(yaw)))
    dworld = np.stack([cy * dbody[:, 0] - sy * dbody[:, 1], sy * dbody[:, 0] + cy * dbody[:, 1], dbody[:, 2]], axis=1)
    lev = np.asarray(mount.lever, float)
    org = pos + np.stack([cy * lev[0] - sy * lev[1], sy * lev[0] + cy * lev[1], np.full(len(cy), lev[2])], axis=1)
    if scanner.divergence > 0:
        dworld = dworld + rng.normal(0, scanner.divergence / 2, dworld.shape)
        dworld /= np.linalg.norm(dworld, axis=1, keepdims=True)
    t_hit, k_hit = cast_rays(geom, org, dworld, scanner.max_range)
    hit = k_hit >= 0
    cosi = np.abs(np.einsum("ij,ij->i", dworld[hit], geom.N[k_hit[hit]]))
    keep = rng.random(hit.sum()) < np.clip(np.sqrt(cosi) * (1 - (t_hit[hit] / scanner.max_range) ** 2), 0, 1)
    idx = np.flatnonzero(hit)[keep]
    rr = t_hit[idx] + rng.normal(0, scanner.range_sigma, len(idx))
    xyz = org[idx] + dworld[idx] * rr[:, None]
    return {"xyz": xyz, "member": geom.member[k_hit[idx]], "plate": k_hit[idx], "sensor": np.full(len(idx), sensor_id),
            "t": tp[idx], "cos_inc": cosi[keep], "range": rr, "origin": org[idx], "n_pulses": npulse,
            "decim": decim}


def merge_clouds(clouds) -> dict:
    keys = ("xyz", "member", "plate", "sensor", "t", "cos_inc", "range", "origin")
    out = {k: np.concatenate([c[k] for c in clouds]) for k in keys}
    out["n_pulses"] = int(sum(c["n_pulses"] for c in clouds))
    return out


def expected_hits(geom: Geometry, origins: np.ndarray, scanner: Scanner, mount_R_list, dwell: float = 1.0,
                  n_sample: int = 20000, seed: int = 0, yaw=None) -> np.ndarray:
    """每个视点（位置 + 机头方位 + 若干安装姿态）在驻留 dwell 秒内对每根杆件的期望命中点数 (nvp, n_members)。"""
    rng = np.random.default_rng(seed)
    nvp = len(origins)
    yaw = np.zeros(nvp) if yaw is None else np.asarray(yaw)
    out = np.zeros((nvp, geom.n_members))
    tq = rng.uniform(0, 1.0, n_sample)
    dsens = scanner.directions(tq)
    for v in range(nvp):
        cy, sy = math.cos(yaw[v]), math.sin(yaw[v])
        for Rm in mount_R_list:
            db = dsens @ Rm.T
            dw = np.stack([cy * db[:, 0] - sy * db[:, 1], sy * db[:, 0] + cy * db[:, 1], db[:, 2]], axis=1)
            t, k = cast_rays(geom, np.repeat(origins[v][None], n_sample, 0), dw, scanner.max_range)
            ok = k >= 0
            m = geom.member[k[ok]]
            m = m[m >= 0]
            out[v] += np.bincount(m, minlength=geom.n_members)[:geom.n_members] * (scanner.prr * dwell / n_sample)
    return out


def visible(geom: Geometry, origin, targets: np.ndarray, target_member=None, tol=0.05) -> np.ndarray:
    """从 origin 看各目标点是否无遮挡（首个命中位于目标附近，或命中的就是目标杆件）。"""
    o = np.asarray(origin, float)
    d = targets - o
    dist = np.linalg.norm(d, axis=1)
    d = d / dist[:, None]
    t, k = cast_rays(geom, np.repeat(o[None], len(d), 0), d, float(dist.max() + 1))
    vis = (k < 0) | (t >= dist - tol)
    if target_member is not None:
        vis |= (k >= 0) & (geom.member[np.maximum(k, 0)] == np.asarray(target_member))
    return vis
