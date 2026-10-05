# -*- coding: utf-8 -*-
"""拓扑更新：存在概率剪枝 + 零能模态（机构）检查 + 规格分组一致化。

剪枝后的铰接桁架总刚度矩阵若比剪枝前多出零能模态，说明剪除的杆件是维持几何不变所必需的，予以恢复。
（格构塔交叉斜材的交叉点在纯铰接模型中本就存在面外零能模态，故以“剪枝前后零空间维数之差”判断。）
"""
from __future__ import annotations

import numpy as np

from .surfels import sigmoid


def truss_nullity(V, mi, mj, active, fixed_nodes, tol=1e-9):
    """铰接桁架（仅轴向刚度）零空间维数；孤立节点不计入。"""
    act = np.flatnonzero(active)
    used = np.zeros(len(V), bool)
    used[mi[act]] = True; used[mj[act]] = True
    used[np.asarray(fixed_nodes, int)] = False
    idx = -np.ones(len(V), int)
    idx[used] = np.arange(used.sum())
    nd = 3 * used.sum()
    if nd == 0:
        return 0
    K = np.zeros((nd, nd))
    for e in act:
        a, b = mi[e], mj[e]
        d = V[b] - V[a]
        L = np.linalg.norm(d)
        u = d / L
        k = np.outer(u, u) / L
        for (p, q, s) in ((a, a, 1), (b, b, 1), (a, b, -1), (b, a, -1)):
            if idx[p] >= 0 and idx[q] >= 0:
                K[3 * idx[p]:3 * idx[p] + 3, 3 * idx[q]:3 * idx[q] + 3] += s * k
    w = np.linalg.eigvalsh(K)
    return int(np.sum(w < tol * max(w.max(), 1e-12)))


def prune(prob, x, apply=False):
    """apply=False：返回已剪除（冻结）的杆件；apply=True：执行剪枝与零能模态恢复，返回新参数向量。"""
    s = prob.sl["logit"]
    pi = np.asarray(sigmoid(x[s]))
    if not apply:
        return np.flatnonzero(pi < 0.01)
    lay = prob.lay
    V = np.asarray(x[prob.sl["V"]]).reshape(-1, 3)
    ref = np.asarray(getattr(prob, "ref_active", pi >= 0.5), bool)     # 参考拓扑（初始图）
    after = pi >= prob.cfg.prune
    fixed = getattr(prob, "base_nodes", [])
    n0 = truss_nullity(V, lay.mi, lay.mj, ref, fixed)
    n1 = truss_nullity(V, lay.mi, lay.mj, after, fixed)
    restored = []
    removed = np.flatnonzero(ref & ~after)
    for e in removed[np.argsort(-pi[removed])]:
        if n1 <= n0:
            break
        after[e] = True
        n_new = truss_nullity(V, lay.mi, lay.mj, after, fixed)
        if n_new < n1:
            restored.append(int(e)); n1 = n_new
        else:
            after[e] = False
    x = x.copy()
    lg = x[s].copy()
    lg[~after] = -7.0
    lg[np.array(restored, int)] = np.maximum(lg[np.array(restored, int)], 0.5) if restored else lg[[]]
    x[s] = lg
    prob.topology_log = {"pruned": [int(e) for e in np.flatnonzero(~after)], "restored": restored,
                         "nullity_ref": n0, "nullity_final": n1}
    return x


def group_consistency(b_snap, groups, pi, thr=0.5):
    """同一截面组（对称位置）内的规格多数一致化（以存在杆件投票，按肢宽众数）。"""
    out = b_snap.copy()
    groups = np.asarray(groups)
    for gname in np.unique(groups):
        sel = np.flatnonzero((groups == gname) & (pi >= thr))
        if len(sel) < 3:
            continue
        vals, cnt = np.unique(np.round(b_snap[sel], 4), return_counts=True)
        mode = vals[np.argmax(cnt)]
        if cnt.max() / len(sel) >= 0.6:
            out[sel] = mode
    return out
