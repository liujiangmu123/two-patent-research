# -*- coding: utf-8 -*-
"""合成观测：真值格构塔（含肢朝向、准线偏心、缺材、局部不对称）→ 无人机多视影像（像素射线、轮廓与灰度）
与激光雷达脉冲（含足迹发散、测距噪声、检测概率、植被与地面回波），以及 PTM 式初始桁架图与面板语法候选杆件。

真值几何直接由角钢两肢薄板构成（towerkit.lidar.Geometry），与反演所用的高斯面元表示不同，存在真实的模型失配。
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from . import _paths  # noqa: F401
import towerkit as tk
from towerkit import lidar as L
from towerkit import sections as S
from towerkit import tower as T
from towerkit.graph import TrussGraph

from .surfels import legs_np, phi_from_legs, ref_vectors

SUN = np.array([0.45, -0.55, 0.70]) / np.linalg.norm([0.45, -0.55, 0.70])
VEG = dict(half=7.5, ztop=2.5)          # 塔脚植被区（|x|,|y|<half，z<ztop）


# ====================================================================== 真值塔
@dataclass
class Universe:
    """优化所用杆件全集（初始图 ∪ 候选），以及真值存在性。"""
    nodes_true: np.ndarray
    mi: np.ndarray
    mj: np.ndarray
    cat: list
    part: list
    face: np.ndarray
    panel: np.ndarray
    exist: np.ndarray        # 真值是否存在
    in_init: np.ndarray      # 是否在 PTM 式初始图中
    is_cand: np.ndarray      # 是否为面板语法候选
    b: np.ndarray            # 真值肢宽（不存在的杆件给类别典型值）
    t: np.ndarray            # 真值肢厚
    sec: list                # 真值规格名
    phi: np.ndarray          # 真值肢朝向（相对 r_e）
    d1: np.ndarray
    d2: np.ndarray
    r: np.ndarray            # 参考向量
    g_design: TrussGraph = field(repr=False, default=None)
    damaged: list = field(default_factory=list)
    false_neg: list = field(default_factory=list)
    asym_nodes: list = field(default_factory=list)

    @property
    def n_members(self):
        return len(self.mi)


def _grammar_candidates(g: TrussGraph, rng, n_spurious: int, existing: set):
    """面板语法：同一塔身面、同一节间的节点两两连线中，长度与已有斜材相当、且不与已有杆件共线者。"""
    X = g.nodes
    face = np.asarray(g.face); panel = np.asarray(g.panel)
    mi, mj = g.ends()
    out = []
    for f in sorted(set(face[face >= 0])):
        for p in sorted(set(panel[(face == f) & (panel >= 0)])):
            sel = np.flatnonzero((face == f) & (panel == p))
            if len(sel) == 0:
                continue
            nodes = sorted(set(mi[sel]) | set(mj[sel]))
            lens = np.linalg.norm(X[mj[sel]] - X[mi[sel]], axis=1)
            lmax = 1.6 * lens.max()
            for a_i in range(len(nodes)):
                for b_i in range(a_i + 1, len(nodes)):
                    a, b = nodes[a_i], nodes[b_i]
                    if (a, b) in existing or (b, a) in existing:
                        continue
                    v = X[b] - X[a]
                    l = np.linalg.norm(v)
                    if l < 0.6 or l > lmax:
                        continue
                    inc = np.flatnonzero((mi == a) | (mj == a) | (mi == b) | (mj == b))
                    dv = X[mj[inc]] - X[mi[inc]]
                    dv /= np.linalg.norm(dv, axis=1, keepdims=True)
                    if np.max(np.abs(dv @ (v / l))) > 0.985:      # 与相邻已有杆件共线（重叠）
                        continue
                    out.append((a, b, int(f), int(p)))
    rng.shuffle(out)
    return out[:n_spurious]


def build_universe(preset="suspension", seed=0, n_damaged=6, n_false_neg=6, n_spurious=24, asym=True,
                   rot_frac=0.15, delta_max=0.004) -> Universe:
    rng = np.random.default_rng(seed)
    spec = T.TowerSpec.preset(preset)
    g = T.build_tower(spec)
    T.assign_sections(g, spec)
    mi, mj = g.ends()
    X = g.nodes.copy()
    m0 = g.n_members
    cat = list(g.cat); part = list(g.part)
    face = np.asarray(g.face); panel = np.asarray(g.panel)
    # 真值缺材（损伤）与 PTM 漏检：均取自塔身/横担的斜材与辅材
    pool = [e for e in range(m0) if cat[e] in ("diagonal", "auxiliary") and part[e] in ("body", "arm")]
    rng.shuffle(pool)
    damaged = sorted(pool[:n_damaged])
    false_neg = sorted(pool[n_damaged:n_damaged + n_false_neg])
    existing = {(int(a), int(b)) for a, b in zip(mi, mj)}
    spur = _grammar_candidates(g, rng, n_spurious, existing)
    # 杆件全集
    MI = np.concatenate([mi, [s[0] for s in spur]]).astype(np.int64)
    MJ = np.concatenate([mj, [s[1] for s in spur]]).astype(np.int64)
    n = len(MI)
    cat_u = cat + ["diagonal"] * len(spur)
    part_u = part + ["body"] * len(spur)
    face_u = np.concatenate([face, [s[2] for s in spur]]).astype(int)
    panel_u = np.concatenate([panel, [s[3] for s in spur]]).astype(int)
    exist = np.ones(n, bool); exist[damaged] = False; exist[m0:] = False
    in_init = np.ones(n, bool); in_init[false_neg] = False; in_init[m0:] = False
    is_cand = np.zeros(n, bool); is_cand[false_neg] = True; is_cand[m0:] = True
    # 截面
    sec = list(g.sec) + ["L63x5"] * len(spur)
    b = np.array([S.angle(s).b for s in sec]); t = np.array([S.angle(s).t for s in sec])
    # 肢朝向：towerkit 规则（塔身主材两肢朝塔内，其余一肢朝塔心）+ 部分斜材/辅材翻转 90°/180°（安装方向差异）
    base = g.meta["base_nodes"]
    cen = np.mean(X[base, :2], axis=0)
    r = ref_vectors(X, MI, MJ, cen)
    u = X[MJ] - X[MI]; u /= np.linalg.norm(u, axis=1, keepdims=True)
    w1 = r - np.sum(r * u, 1, keepdims=True) * u
    w1 /= np.linalg.norm(w1, axis=1, keepdims=True)
    w2 = np.cross(u, w1)
    for e in range(m0):
        if cat[e] == "main" and part[e] == "body":
            a, bb = X[MI[e]], X[MJ[e]]
            sx = np.sign(0.5 * (a[0] + bb[0]) - cen[0]) or 1.0
            sy = np.sign(0.5 * (a[1] + bb[1]) - cen[1]) or 1.0
            p1 = np.array([-sx, 0, 0.0]) - np.dot([-sx, 0, 0.0], u[e]) * u[e]
            p2 = np.array([0, -sy, 0.0]) - np.dot([0, -sy, 0.0], u[e]) * u[e]
            w1[e] = p1 / np.linalg.norm(p1); w2[e] = p2 / np.linalg.norm(p2)
    phi = phi_from_legs(u, r, w1, w2)
    rot = np.flatnonzero((np.array([c != "main" for c in cat_u])) & (rng.random(n) < rot_frac))
    phi[rot] += rng.choice([np.pi / 2, np.pi, -np.pi / 2], len(rot))
    phi = (phi + np.pi) % (2 * np.pi) - np.pi
    # 准线偏心：斜材与辅材以连接肢上的螺栓准线（距肢背约 0.55b 的准距）通过节点，肢背线相对节点连线偏置 −g·n_k；
    # 主材以肢背线为准线（偏心为 0）。另加 ±delta_max 的施工偏差。
    d1 = np.zeros(n); d2 = np.zeros(n)
    nm = np.flatnonzero(np.array([c != "main" for c in cat_u]))
    gauge = np.clip(np.round(0.55 * b[nm] / 0.005) * 0.005, 0.02, 0.07)
    leg = rng.integers(0, 2, len(nm))
    d1[nm] = np.where(leg == 0, -gauge, 0.0) + rng.uniform(-delta_max, delta_max, len(nm))
    d2[nm] = np.where(leg == 1, -gauge, 0.0) + rng.uniform(-delta_max, delta_max, len(nm))
    # 局部不对称：一侧横担端部下挠、一腿基础沉降（对称软先验不应抹平）
    asym_nodes = []
    if asym:
        arm_nodes = sorted(set(MI[np.array(part_u) == "arm"]) | set(MJ[np.array(part_u) == "arm"]))
        tip = max(arm_nodes, key=lambda k: X[k, 0])
        X[tip, 2] -= 0.08
        foot = base[0]
        legn = [k for k in range(len(X)) if np.linalg.norm(X[k, :2] - X[foot, :2]) < 0.6 and X[k, 2] < 0.5]
        for k in legn:
            X[k, 2] -= 0.05
        asym_nodes = [int(tip)] + [int(k) for k in legn]
    return Universe(X, MI, MJ, cat_u, part_u, face_u, panel_u, exist, in_init, is_cand, b, t, sec, phi, d1, d2, r,
                    g, damaged, false_neg, asym_nodes)


def truth_geometry(U: Universe) -> L.Geometry:
    """真值角钢两肢薄板几何（仅真值存在的杆件）。"""
    e = np.flatnonzero(U.exist)
    hi, hj, n1, n2, u, Lm = legs_np(U.nodes_true, U.mi[e], U.mj[e], U.r[e], U.b[e], U.phi[e], U.d1[e], U.d2[e])
    P0 = np.concatenate([hi, hi]); Uu = np.concatenate([u, u]); Lu = np.concatenate([Lm, Lm])
    W = np.concatenate([n1, n2]); Lw = np.concatenate([U.b[e], U.b[e]])
    Nn = np.cross(Uu, W); Nn /= np.linalg.norm(Nn, axis=1, keepdims=True)
    mem = np.concatenate([e, e]).astype(np.int64)
    geom = L.Geometry(P0, Uu, Lu, W, Lw, Nn, mem, U.n_members)
    geom.grid = L._build_grid(geom, 0.6)
    return geom


# ====================================================================== 相机
def rodrigues(w):
    w = np.asarray(w, float)
    th = np.linalg.norm(w)
    if th < 1e-15:
        return np.eye(3)
    k = w / th
    K = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
    return np.eye(3) + math.sin(th) * K + (1 - math.cos(th)) * K @ K


def look_at(C, target, up=(0, 0, 1.0)):
    z = np.asarray(target, float) - np.asarray(C, float)
    z /= np.linalg.norm(z)
    x = np.cross(z, up); x /= np.linalg.norm(x)
    y = np.cross(z, x)
    return np.vstack([x, y, z])     # 世界→相机（行为相机轴）


@dataclass
class Cam:
    C_nom: np.ndarray        # POS 记录的投影中心
    R_nom: np.ndarray        # POS 记录的姿态（世界→相机）
    C_act: np.ndarray        # 真实投影中心
    R_act: np.ndarray
    vel: np.ndarray          # 载体速度（时间偏移标定用）
    f: float
    W: int
    H: int
    kind: str = "down"       # down：俯视测绘相机 / up：仰视相机

    def dcam(self, u, v):
        d = np.stack([(u - (self.W - 1) / 2) / self.f, (v - (self.H - 1) / 2) / self.f, np.ones_like(u)], -1)
        return d / np.linalg.norm(d, axis=-1, keepdims=True)

    def project(self, X, actual=False):
        R, C = (self.R_act, self.C_act) if actual else (self.R_nom, self.C_nom)
        Xc = (np.asarray(X) - C) @ R.T
        return np.stack([self.f * Xc[..., 0] / Xc[..., 2] + (self.W - 1) / 2,
                         self.f * Xc[..., 1] / Xc[..., 2] + (self.H - 1) / 2], -1), Xc[..., 2]


@dataclass
class ExtTruth:
    omega: np.ndarray        # 相机视轴安装误差（rad，相机系小转角）
    lever: np.ndarray        # 杠杆臂误差（m）
    dt: float                # 曝光时间偏移（s）


def make_cameras(H_tower, rng, radius=28.0, rings=(12.0, 26.0, 40.0, 54.0), n_az=10, up_views=8, W=5280, Hh=3956,
                 hfov_deg=73.7, ext: ExtTruth | None = None, pos_sigma=0.015, att_sigma_deg=0.01, speed=3.0):
    """默认相机参数取 4/3 英寸 2000 万像素测绘相机（等效焦距 24 mm，5280×3956），28 m 处地面采样距离约 8 mm。"""
    f = (W / 2) / math.tan(math.radians(hfov_deg) / 2)
    ext = ext or ExtTruth(np.radians([0.08, -0.05, 0.10]), np.array([0.02, -0.01, 0.015]), 0.004)
    cams = []
    for ri, z in enumerate(rings):
        for k in range(n_az):
            az = 2 * math.pi * (k + 0.5 * (ri % 2)) / n_az
            C = np.array([radius * math.cos(az), radius * math.sin(az), z])
            R = look_at(C, [0.0, 0.0, min(z + 2.0, H_tower)])
            vel = speed * np.array([-math.sin(az), math.cos(az), 0.0])
            cams.append((C, R, vel, "down"))
    for k in range(up_views):
        az = 2 * math.pi * (k + 0.25) / up_views
        C = np.array([16.0 * math.cos(az), 16.0 * math.sin(az), 0.55 * H_tower])
        tgt = np.array([0.0, 0.0, 0.85 * H_tower])
        R = look_at(C, tgt)
        vel = speed * np.array([-math.sin(az), math.cos(az), 0.0])
        cams.append((C, R, vel, "up"))
    out = []
    for C, R, vel, kind in cams:
        # 真实位姿 = 记录位姿经系统误差（安装、杠杆臂、时间偏移）与随机误差修正
        R_act = R
        C_act = C
        R_nom = rodrigues(ext.omega) @ R_act
        R_nom = rodrigues(rng.normal(0, math.radians(att_sigma_deg), 3)) @ R_nom
        C_nom = C_act - ext.lever - vel * ext.dt + rng.normal(0, pos_sigma, 3)
        out.append(Cam(C_nom, R_nom, C_act, R_act, vel, f, W, Hh, kind))
    return out, ext


def _bg_gray(d):
    """背景（天空/远景）灰度：随射线仰角变化。"""
    el = np.arcsin(np.clip(d[..., 2], -1, 1))
    return np.where(el > 0, 0.88 - 0.10 * el, 0.42 + 0.05 * np.sin(13 * d[..., 0]) * np.cos(11 * d[..., 1]))


def _veg_hit(o, d):
    """射线在到达塔体前是否穿过塔脚植被区（简化为长方体）。"""
    h, zt = VEG["half"], VEG["ztop"]
    t0 = np.zeros(len(o)); t1 = np.full(len(o), 1e9)
    lo = np.array([-h, -h, -1.0]); hi = np.array([h, h, zt])
    for ax in range(3):
        dd = d[:, ax]
        with np.errstate(divide="ignore", invalid="ignore"):
            ta = (lo[ax] - o[:, ax]) / dd
            tb = (hi[ax] - o[:, ax]) / dd
        tmin = np.where(np.abs(dd) < 1e-12, np.where((o[:, ax] >= lo[ax]) & (o[:, ax] <= hi[ax]), -1e9, 1e9), np.minimum(ta, tb))
        tmax = np.where(np.abs(dd) < 1e-12, np.where((o[:, ax] >= lo[ax]) & (o[:, ax] <= hi[ax]), 1e9, -1e9), np.maximum(ta, tb))
        t0 = np.maximum(t0, tmin); t1 = np.minimum(t1, tmax)
    return t0 <= t1, t0


def sample_pixels(cam: Cam, V_init, mi, mj, b_init, rng, n_band=6000, n_bg=1500, band_m=0.18):
    """在初始桁架图投影的杆件带内与塔体投影包围盒内抽样像素（用名义位姿）。"""
    pts, cols = [], []
    W, H = cam.W, cam.H
    for e in range(len(mi)):
        a, b = V_init[mi[e]], V_init[mj[e]]
        n = int(max(4, np.linalg.norm(b - a) / 0.03))
        s = np.linspace(0, 1, n)[:, None]
        P = a + s * (b - a)
        uv, z = cam.project(P)
        ok = z > 1.0
        if ok.sum() < 2:
            continue
        uv = uv[ok]; z = z[ok]
        dv = np.diff(uv, axis=0)
        if len(dv) == 0:
            continue
        tan = dv / np.maximum(np.linalg.norm(dv, axis=1, keepdims=True), 1e-9)
        tan = np.vstack([tan, tan[-1:]])
        nor = np.stack([-tan[:, 1], tan[:, 0]], 1)
        wpx = (band_m + 1.2 * b_init[e]) * cam.f / z
        offs = rng.uniform(-1, 1, (len(uv), 6)) * wpx[:, None]
        q = uv[:, None, :] + offs[..., None] * nor[:, None, :]
        pts.append(q.reshape(-1, 2))
    if not pts:
        return np.zeros((0, 2))
    Q = np.round(np.concatenate(pts)).astype(int)
    Q = Q[(Q[:, 0] >= 0) & (Q[:, 0] < W) & (Q[:, 1] >= 0) & (Q[:, 1] < H)]
    if len(Q) == 0:
        return np.zeros((0, 2))
    key = np.unique(Q[:, 1] * W + Q[:, 0])
    band = rng.choice(key, min(n_band, len(key)), replace=False)
    u0, v0 = Q[:, 0].min(), Q[:, 1].min(); u1, v1 = Q[:, 0].max(), Q[:, 1].max()
    bg = rng.integers(v0, v1 + 1, n_bg) * W + rng.integers(u0, u1 + 1, n_bg)
    allk = np.unique(np.concatenate([band, bg]))
    return np.stack([allk % W, allk // W], 1).astype(float)


def render_pixels(cam: Cam, uv, geom, albedo, rng, ss=3, img_noise=0.01, mask_noise=0.03):
    """真实位姿下对像素做 ss×ss 超采样光线投射，得到灰度、轮廓占据率（含分割噪声）与植被遮挡标记。"""
    n = len(uv)
    offs = (np.arange(ss) + 0.5) / ss - 0.5
    du, dv = np.meshgrid(offs, offs)
    U = (uv[:, 0:1] + du.ravel()[None]).ravel()
    Vv = (uv[:, 1:2] + dv.ravel()[None]).ravel()
    dc = cam.dcam(U, Vv)
    dw = dc @ cam.R_act
    o = np.repeat(cam.C_act[None], len(dw), 0)
    t_hit, k_hit = L.cast_rays(geom, o, dw, 400.0)
    hit = k_hit >= 0
    g = _bg_gray(dw)
    nv = geom.N[np.maximum(k_hit, 0)]
    nv = nv * (-np.sign(np.sum(nv * dw, 1)))[:, None]
    shade = albedo[geom.member[np.maximum(k_hit, 0)]] * (0.32 + 0.68 * np.clip(nv @ SUN, 0, None))
    g = np.where(hit, shade, g)
    veg, tveg = _veg_hit(o, dw)
    veg_block = veg & ((~hit) | (tveg < t_hit))
    g = g.reshape(n, ss * ss).mean(1) + rng.normal(0, img_noise, n)
    frac = hit.reshape(n, ss * ss).mean(1)
    mask = np.clip(frac + rng.normal(0, mask_noise, n), 0, 1)
    valid = ~(veg_block.reshape(n, ss * ss).any(1))
    sky = _bg_gray(cam.dcam(uv[:, 0], uv[:, 1]) @ cam.R_act) + rng.normal(0, 0.01, n)
    return g, mask, frac, valid, sky


# ====================================================================== 激光雷达
@dataclass
class LidarObs:
    o: np.ndarray
    d: np.ndarray
    rng_m: np.ndarray        # 回波距离（无回波 −1）
    kind: np.ndarray         # 0 塔体回波 1 地面 2 植被 −1 无回波
    member: np.ndarray       # 真值命中杆件（−1 无）
    cos_inc: np.ndarray
    n_pulses: int
    sig_div: float           # 发散角（每轴标准差，rad）
    range_sigma: float


def simulate_lidar(geom, rings, radius, rng, scanner: L.Scanner | None = None, decim=0.25, speed=3.0,
                   mount=None, pos_sigma=0.01, att_sigma_deg=0.005, chunk=2_000_000, keep_free=None):
    """绕塔环绕航线扫描。返回全部回波（塔体/地面/植被）与供负证据用的无塔体回波射线。

    keep_free(o,d) -> bool 掩码：选择保留的无塔体回波射线（如穿过初始模型附近者）。
    """
    sc = scanner or L.Scanner()
    mt = mount or L.Mount(yaw=90.0, pitch=-12.0, roll=0.0, lever=(0.0, 0.0, -0.12))
    paths = [L.orbit_path((0, 0), radius, z, speed=speed) for z in rings]
    Rm = mt.R()
    sig_div = sc.divergence / 2
    out = {k: [] for k in ("o", "d", "r", "kind", "member", "cos")}
    total = 0
    for traj in paths:
        npulse = int(traj.duration * sc.prr * decim)
        total += npulse
        for s0 in range(0, npulse, chunk):
            m = min(chunk, npulse - s0)
            tp = traj.t[0] + (np.arange(s0, s0 + m) + rng.random(m)) / npulse * traj.duration
            pos, yaw = traj.at(tp)
            pos = pos + rng.normal(0, pos_sigma, pos.shape)
            ds = sc.directions(tp)
            db = ds @ Rm.T
            yy = yaw + rng.normal(0, math.radians(att_sigma_deg), len(yaw))
            cy, sy = np.cos(yy), np.sin(yy)
            dw = np.stack([cy * db[:, 0] - sy * db[:, 1], sy * db[:, 0] + cy * db[:, 1], db[:, 2]], 1)
            lev = np.asarray(mt.lever)
            org = pos + np.stack([cy * lev[0] - sy * lev[1], sy * lev[0] + cy * lev[1], np.full(m, lev[2])], 1)
            dsamp = dw + rng.normal(0, sig_div, dw.shape)          # 足迹内随机采样光线（检测概率∝截获能量）
            dsamp /= np.linalg.norm(dsamp, axis=1, keepdims=True)
            t_hit, k_hit = L.cast_rays(geom, org, dsamp, sc.max_range)
            hit = k_hit >= 0
            cosi = np.zeros(m)
            cosi[hit] = np.abs(np.sum(dsamp[hit] * geom.N[k_hit[hit]], 1))
            pdet = np.clip(np.sqrt(cosi) * (1 - (np.maximum(t_hit, 0) / sc.max_range) ** 2), 0, 1)
            det = hit & (rng.random(m) < pdet)
            # 植被
            veg, tveg = _veg_hit(org, dsamp)
            veg_ret = veg & (rng.random(m) < 0.55) & ((~det) | (tveg < t_hit))
            tveg_r = tveg + rng.uniform(0.0, 2.0, m)
            # 地面
            with np.errstate(divide="ignore", invalid="ignore"):
                tg = np.where(dsamp[:, 2] < -1e-6, -org[:, 2] / dsamp[:, 2], -1.0)
            grd = (~det) & (~veg_ret) & (tg > 0) & (tg < sc.max_range)
            r = np.full(m, -1.0); kind = np.full(m, -1); mem = np.full(m, -1)
            r[det] = t_hit[det]; kind[det] = 0; mem[det] = geom.member[k_hit[det]]
            r[veg_ret] = tveg_r[veg_ret]; kind[veg_ret] = 2; mem[veg_ret] = -1
            r[grd] = tg[grd]; kind[grd] = 1
            r = np.where(r > 0, r + rng.normal(0, sc.range_sigma, m), r)
            keep = (kind == 0) | (kind == 2)
            if keep_free is not None:
                cand = ~keep
                kf = np.zeros(m, bool)
                if cand.any():
                    kf[cand] = keep_free(org[cand], dw[cand], np.where(r[cand] > 0, r[cand], sc.max_range))
                keep = keep | kf
            for k, v in (("o", org), ("d", dw), ("r", r), ("kind", kind), ("member", mem), ("cos", cosi)):
                out[k].append(v[keep])
    cat = {k: np.concatenate(v) for k, v in out.items()}
    return LidarObs(cat["o"], cat["d"], cat["r"], cat["kind"], cat["member"], cat["cos"], total, sig_div,
                    sc.range_sigma)


# ====================================================================== 初始图（PTM 式）
def initial_state(U: Universe, rng, node_sigma=0.055, b_cat=None):
    """PTM 式初始：节点含定位误差，截面按类别取典型值，肢朝向按默认规则（φ=0），无偏心。"""
    b_cat = b_cat or {"main": 0.14, "diagonal": 0.075, "auxiliary": 0.056}
    V0 = U.nodes_true + rng.normal(0, node_sigma, U.nodes_true.shape)
    base = U.g_design.meta["base_nodes"]
    V0[base, 2] = U.nodes_true[base, 2] + rng.normal(0, node_sigma * 0.5, len(base))
    b0 = np.array([b_cat[c] for c in U.cat])
    phi0 = np.zeros(U.n_members)
    # 塔身主材：默认两肢朝塔内（与真值规则相同的先验），其余 φ=0（一肢朝塔心）
    X = U.nodes_true
    u = X[U.mj] - X[U.mi]; u /= np.linalg.norm(u, axis=1, keepdims=True)
    cen = np.mean(X[base, :2], axis=0)
    for e in range(U.n_members):
        if U.cat[e] == "main" and U.part[e] == "body":
            a, bb = V0[U.mi[e]], V0[U.mj[e]]
            sx = np.sign(0.5 * (a[0] + bb[0]) - cen[0]) or 1.0
            sy = np.sign(0.5 * (a[1] + bb[1]) - cen[1]) or 1.0
            p1 = np.array([-sx, 0, 0.0]) - np.dot([-sx, 0, 0.0], u[e]) * u[e]
            p2 = np.array([0, -sy, 0.0]) - np.dot([0, -sy, 0.0], u[e]) * u[e]
            phi0[e] = phi_from_legs(u[e:e + 1], U.r[e:e + 1], (p1 / np.linalg.norm(p1))[None],
                                    (p2 / np.linalg.norm(p2))[None])[0]
    logit0 = np.where(U.in_init, 2.5, -1.0)
    return V0, b0, phi0, np.zeros(U.n_members), np.zeros(U.n_members), logit0


def symmetry_pairs(V, tol=0.25):
    """塔身双轴对称：节点 i 与其关于 x=0、y=0 及中心反射的对应节点（初始图上按最近匹配）。"""
    from scipy.spatial import cKDTree
    tree = cKDTree(V)
    pairs = []
    for M in (np.diag([-1, 1, 1.0]), np.diag([1, -1, 1.0]), np.diag([-1, -1, 1.0])):
        d, j = tree.query(V @ M.T)
        for i in range(len(V)):
            if d[i] < tol and j[i] != i:
                pairs.append((i, int(j[i]), M))
    return pairs
