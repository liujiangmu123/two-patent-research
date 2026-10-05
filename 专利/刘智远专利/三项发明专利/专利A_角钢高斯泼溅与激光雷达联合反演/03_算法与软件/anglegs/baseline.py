# -*- coding: utf-8 -*-
"""PTM 式激光点云基线：固定拓扑下以点到杆件中心线的鲁棒距离优化节点坐标，截面按类别统一赋值。

对应 PTM 论文的“固定拓扑图优化 + 截面统一假设”（主材 L220×22、斜材 L140×12、辅材 L90×8）。
点云中心线穿过角钢两肢点的质心而非肢背准线，这一系统偏差是纯点云方法的固有误差来源之一。
"""
from __future__ import annotations

import numpy as np
import scipy.sparse as sp
from scipy.optimize import least_squares
from scipy.spatial import cKDTree

PTM_SECTIONS = {"main": "L220x22", "diagonal": "L140x12", "auxiliary": "L90x8"}


def _seg_dist(P, A, B):
    v = B - A
    L2 = np.sum(v * v, 1)
    s = np.clip(np.sum((P - A) * v, 1) / np.maximum(L2, 1e-12), 0, 1)
    Q = A + s[:, None] * v
    return np.linalg.norm(P - Q, axis=1), s


def assign_points(P, V, mi, mj, active, radius=0.35, nsamp=12):
    """把点分配给最近的活动杆件（按杆件采样点 KD 树近似，再精确比较）。"""
    act = np.flatnonzero(active)
    S = []
    owner = []
    for e in act:
        a, b = V[mi[e]], V[mj[e]]
        n = max(nsamp, int(np.linalg.norm(b - a) / 0.15))
        s = np.linspace(0, 1, n)[:, None]
        S.append(a + s * (b - a)); owner.append(np.full(n, e))
    S = np.concatenate(S); owner = np.concatenate(owner)
    tree = cKDTree(S)
    d, j = tree.query(P, k=6, distance_upper_bound=radius + 0.3)
    best = np.full(len(P), -1); bestd = np.full(len(P), np.inf)
    for c in range(j.shape[1]):
        ok = np.isfinite(d[:, c])
        e = np.where(ok, owner[np.minimum(j[:, c], len(owner) - 1)], -1)
        idx = np.flatnonzero(ok)
        dist, _ = _seg_dist(P[idx], V[mi[e[idx]]], V[mj[e[idx]]])
        better = dist < bestd[idx]
        bestd[idx[better]] = dist[better]; best[idx[better]] = e[idx[better]]
    best[bestd > radius] = -1
    return best


def ptm_like(points, V0, mi, mj, active, prior_sigma=0.3, f_scale=0.03, max_nfev=60, fixed=None):
    """返回优化后的节点坐标与分配信息。fixed：坐标固定的节点（如无点支撑）。"""
    V0 = np.asarray(V0, float)
    owner = assign_points(points, V0, mi, mj, active)
    ok = owner >= 0
    P, own = points[ok], owner[ok]
    n = len(V0)
    i_a, i_b = mi[own], mj[own]

    def res(x):
        V = x.reshape(n, 3)
        d, _ = _seg_dist(P, V[i_a], V[i_b])
        pr = (x - V0.ravel()) / prior_sigma * 0.05
        return np.concatenate([d, pr])

    rows = np.repeat(np.arange(len(P)), 6)
    cols = np.stack([3 * i_a, 3 * i_a + 1, 3 * i_a + 2, 3 * i_b, 3 * i_b + 1, 3 * i_b + 2], 1).ravel()
    J = sp.coo_matrix((np.ones(len(rows)), (rows, cols)), shape=(len(P), 3 * n))
    Jp = sp.identity(3 * n, format="coo")
    spars = sp.vstack([J, Jp]).tocsr()
    sol = least_squares(res, V0.ravel(), jac_sparsity=spars, loss="huber", f_scale=f_scale, max_nfev=max_nfev,
                        x_scale=0.05, method="trf")
    V = sol.x.reshape(n, 3)
    return V, {"n_points_used": int(ok.sum()), "n_points": int(len(points)), "cost": float(sol.cost),
               "owner": owner}
