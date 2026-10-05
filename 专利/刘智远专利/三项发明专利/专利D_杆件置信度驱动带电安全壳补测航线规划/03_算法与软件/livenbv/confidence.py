# -*- coding: utf-8 -*-
"""杆件级几何置信度：点数（线密度）、视角覆盖（绕杆轴方位扇区）、对称一致性三态判别
（一致 / 冲突 / 不可判），以及点云 → 杆件归属、杆轴拟合、节点最小二乘交会与存在性判定。"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy.spatial import cKDTree

N_BINS = 6                 # 绕杆轴视角扇区数（每扇区 60°）
RHO0 = 6.0                 # 点线密度尺度（点/m）
BIN_MIN = 3                # 扇区计为“已覆盖”所需最少点数
SYM_TOL = 0.15             # 对称一致性容差（m）
STATE = {1: "一致", -1: "冲突", 0: "不可判"}


def member_frames(X, mi, mj):
    """每杆：单位轴向 u 与垂直平面内基 (e1, e2)（e1 取水平/全局 z 在法平面投影，确定且可重复）。"""
    u = X[mj] - X[mi]
    L = np.linalg.norm(u, axis=1)
    u = u / L[:, None]
    ref = np.where(np.abs(u[:, 2:3]) < 0.9, np.array([[0, 0, 1.0]]), np.array([[1.0, 0, 0]]))
    e1 = ref - np.sum(ref * u, 1, keepdims=True) * u
    e1 /= np.linalg.norm(e1, axis=1, keepdims=True)
    e2 = np.cross(u, e1)
    return u, e1, e2, L


def view_bins(X, mi, mj, members, origins):
    """观测射线（杆件中点 → 传感器原点）在杆件法平面内的方位扇区编号。"""
    u, e1, e2, _ = member_frames(X, mi, mj)
    mid = 0.5 * (X[mi] + X[mj])
    d = origins - mid[members]
    a = np.arctan2(np.sum(d * e2[members], 1), np.sum(d * e1[members], 1))
    return np.floor((a + np.pi) / (2 * np.pi) * N_BINS).astype(int) % N_BINS


@dataclass
class Evidence:
    """累积观测：每杆点数、每杆×扇区点数、期望点数（存在性判别）、原始点（拟合用）。"""
    n_members: int
    counts: np.ndarray = None
    bins: np.ndarray = None
    expected: np.ndarray = None
    xyz: list = field(default_factory=list)
    origin: list = field(default_factory=list)

    def __post_init__(self):
        self.counts = np.zeros(self.n_members)
        self.bins = np.zeros((self.n_members, N_BINS))
        self.expected = np.zeros(self.n_members)

    def add_cloud(self, xyz, origin, expected=None):
        self.xyz.append(np.asarray(xyz)); self.origin.append(np.asarray(origin))
        if expected is not None:
            self.expected += expected

    @property
    def all_xyz(self):
        return np.concatenate(self.xyz) if self.xyz else np.zeros((0, 3))

    @property
    def all_origin(self):
        return np.concatenate(self.origin) if self.origin else np.zeros((0, 3))


def assign_points(xyz, X, mi, mj, thr=0.45, step=0.08):
    """点 → 最近杆件（基于当前模型几何的线段采样 KD 树）；超过 thr 记 -1。"""
    seg_pts, seg_id, seg_t = [], [], []
    for e, (a, b) in enumerate(zip(mi, mj)):
        L = np.linalg.norm(X[b] - X[a])
        n = max(2, int(L / step) + 1)
        t = np.linspace(0, 1, n)
        seg_pts.append(X[a] + t[:, None] * (X[b] - X[a])); seg_id.append(np.full(n, e)); seg_t.append(t)
    P = np.concatenate(seg_pts); I = np.concatenate(seg_id)
    if len(xyz) == 0:
        return np.zeros(0, int)
    d, j = cKDTree(P).query(xyz, distance_upper_bound=thr)
    out = np.full(len(xyz), -1)
    ok = np.isfinite(d)
    out[ok] = I[j[ok]]
    return out


@dataclass
class ConfidenceResult:
    c: np.ndarray            # 杆件综合置信度 [0,1]
    c_geo: np.ndarray        # 几何置信度（点数×视角）
    q_n: np.ndarray
    q_v: np.ndarray
    sym_state: np.ndarray    # 1 一致 / -1 冲突 / 0 不可判
    exist: np.ndarray        # 1 存在 / -1 缺失 / 0 未判定
    nodes: np.ndarray        # 估计节点坐标
    node_est: np.ndarray     # 节点估计来源：2 直接交会 / 1 对称借用 / 0 先验
    counts: np.ndarray
    bins: np.ndarray


def fit_lines(xyz, lab, n_members, X, mi, mj, min_pts=12):
    """每杆主方向直线拟合（PCA）；返回质心、方向、有效标志、沿轴覆盖比例。"""
    cen = np.zeros((n_members, 3)); dirs = np.zeros((n_members, 3)); ok = np.zeros(n_members, bool)
    ext = np.zeros(n_members)
    order = np.argsort(lab)
    labs = lab[order]
    starts = np.searchsorted(labs, np.arange(n_members)); ends = np.searchsorted(labs, np.arange(n_members), "right")
    for e in range(n_members):
        idx = order[starts[e]:ends[e]]
        if len(idx) < min_pts:
            continue
        P = xyz[idx]
        c = P.mean(0)
        _, _, vt = np.linalg.svd(P - c, full_matrices=False)
        d = vt[0]
        u0 = X[mj[e]] - X[mi[e]]; L = np.linalg.norm(u0)
        if abs(d @ u0) / L < 0.97:
            continue
        s = (P - c) @ d
        ext[e] = (s.max() - s.min()) / L
        if ext[e] < 0.35:
            continue
        cen[e], dirs[e], ok[e] = c, d * np.sign(d @ u0), True
    return cen, dirs, ok, ext


def intersect_nodes(X0, mi, mj, cen, dirs, ok, w=None):
    """节点 = 与其相连且拟合有效的杆轴直线的最小二乘交会点（需 ≥2 条不平行直线）。"""
    n = len(X0)
    A = np.zeros((n, 3, 3)); b = np.zeros((n, 3)); cnt = np.zeros(n)
    for e in np.flatnonzero(ok):
        d = dirs[e]
        Pm = np.eye(3) - np.outer(d, d)
        we = 1.0 if w is None else w[e]
        for nd in (mi[e], mj[e]):
            A[nd] += we * Pm; b[nd] += we * Pm @ cen[e]; cnt[nd] += 1
    Xn = X0.copy(); est = np.zeros(n, int)
    for nd in range(n):
        if cnt[nd] >= 2:
            ev = np.linalg.eigvalsh(A[nd])
            if ev[0] > 0.05 * ev[-1]:
                p = np.linalg.solve(A[nd], b[nd])
                if np.linalg.norm(p - X0[nd]) < 2.5:
                    Xn[nd] = p; est[nd] = 2
    return Xn, est


def compute_confidence(ev: Evidence, prior, maps_n, maps_e, decim=1.0, n_iter=3, borrow=True) -> ConfidenceResult:
    """完整的置信度评估：迭代（归属 → 拟合 → 交会 → 更新几何），再做存在性与对称三态判别。"""
    mi, mj = np.asarray(prior.mi), np.asarray(prior.mj)
    nm = prior.n_members
    X = prior.nodes.copy()
    xyz, org = ev.all_xyz, ev.all_origin
    est = np.zeros(len(X), int)
    for _ in range(n_iter):
        lab = assign_points(xyz, X, mi, mj)
        cen, dirs, ok, _ = fit_lines(xyz[lab >= 0], lab[lab >= 0], nm, X, mi, mj)
        Xn, est = intersect_nodes(prior.nodes, mi, mj, cen, dirs, ok)
        X = Xn
    good = lab >= 0
    counts = np.bincount(lab[good], minlength=nm).astype(float)
    bins = np.zeros((nm, N_BINS))
    if good.any():
        vb = view_bins(X, mi, mj, lab[good], org[good])
        np.add.at(bins, (lab[good], vb), 1.0)
    _, _, _, L = member_frames(X, mi, mj)
    dens = counts / decim / np.maximum(L, 0.3)
    q_n = 1 - np.exp(-dens / RHO0)
    nb = np.sum(bins >= BIN_MIN, 1)
    q_v = np.minimum(1.0, nb / 3.0)
    c_geo = q_n * (0.35 + 0.65 * q_v)
    # 存在性：期望点数（全点频）足够而实测极少 → 缺失
    exist = np.zeros(nm, int)
    E = ev.expected * decim
    enough = E >= 25
    r = counts / np.maximum(E, 1e-9)
    exist[enough & (r > 0.12)] = 1
    exist[enough & (r < 0.03)] = -1
    exist[(~enough) & (q_n > 0.5)] = 1
    # 对称一致性三态（节点级 → 杆件级）
    node_state = np.zeros(len(X), int)
    for k_m, mn in enumerate(maps_n):
        S = np.array([[-1, 1, 1], [1, -1, 1], [-1, -1, 1]])[k_m]
        pr = [(nd, mn[nd]) for nd in range(len(X)) if mn[nd] >= 0 and mn[nd] != nd and est[nd] == 2 and est[mn[nd]] == 2]
        if not pr:
            continue
        a_, b_ = np.array(pr).T
        R = X[a_] * S - X[b_]
        # 剔除整体倾斜（镜像残差关于高度的线性趋势，两次鲁棒拟合），只保留局部破缺
        Z = np.stack([X[a_, 2], np.ones(len(a_))], 1)
        coef = np.linalg.lstsq(Z, R, rcond=None)[0]
        keep = np.linalg.norm(R - Z @ coef, axis=1) < 3 * SYM_TOL
        if keep.sum() > 6:
            coef = np.linalg.lstsq(Z[keep], R[keep], rcond=None)[0]
        resid = np.linalg.norm(R - Z @ coef, axis=1)
        for (nd, j), res in zip(pr, resid):
            s = 1 if res < SYM_TOL else -1
            node_state[nd] = -1 if (node_state[nd] == -1 or s == -1) else 1
    sym = np.zeros(nm, int)
    for e in range(nm):
        sa, sb = node_state[mi[e]], node_state[mj[e]]
        mirror_ex = [exist[me[e]] for me in maps_e if me[e] >= 0 and me[e] != e]
        ex_conf = any(m != 0 and exist[e] != 0 and m != exist[e] for m in mirror_ex)
        if sa == -1 or sb == -1 or ex_conf:
            sym[e] = -1
        elif sa == 1 or sb == 1 or (any(m == 1 for m in mirror_ex) and exist[e] == 1):
            sym[e] = 1
    # 对称借用：未直接交会的节点若其镜像节点直接交会且邻域一致，取镜像估计
    Xb = X.copy(); est_b = est.copy()
    if borrow:
        signs = np.array([[-1, 1, 1], [1, -1, 1], [-1, -1, 1]])
        for nd in np.flatnonzero(est == 0):
            for k, mn in enumerate(maps_n):
                j = mn[nd]
                if j >= 0 and est[j] == 2 and node_state[j] == 1:
                    Xb[nd] = X[j] * signs[k]; est_b[nd] = 1
                    break
    c = c_geo.copy()
    for e in range(nm):
        if sym[e] == 1:
            mirr = [c_geo[me[e]] for me in maps_e if me[e] >= 0 and me[e] != e]
            if mirr:
                c[e] = max(c[e], 0.75 * max(mirr) if c_geo[e] < 0.5 else c[e])
        elif sym[e] == -1:
            c[e] = c[e] * 0.85
        if exist[e] == -1:
            c[e] = min(1.0, E[e] / 60.0)
    return ConfidenceResult(np.clip(c, 0, 1), c_geo, q_n, q_v, sym, exist, Xb, est_b, counts, bins)


def reconstructed_graph(prior, res: ConfidenceResult):
    """重建模型：估计节点 + 去掉判为缺失的杆件（截面沿用设计先验）。"""
    g = prior.copy()
    g.nodes = res.nodes.copy()
    miss = np.flatnonzero(res.exist == -1)
    return g.remove_members(miss, drop_orphans=False) if len(miss) else g
