# -*- coding: utf-8 -*-
"""结构重要性加权信息增益 + 子模贪心选点 + 安全图最短路 TSP 航线 + 停止判据。

预测置信度 ĉ_e(S) 由“当前点数 + 候选视点期望点数”“当前扇区 + 候选扇区”经与评估同一公式得到；
增益 G(S) = Σ_e w_e·max(0, ĉ_e(S) − c_e)。q_n 关于点数为凹函数、扇区覆盖为饱和覆盖函数，
G 单调且（在 max 截断外）满足边际递减，采用懒惰贪心 + 代价归一（增益/（驻留+增量航程时间））。"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra

from .confidence import BIN_MIN, N_BINS, RHO0


def predicted_cgeo(counts_full, bins_full, L):
    dens = counts_full / np.maximum(L, 0.3)
    q_n = 1 - np.exp(-dens / RHO0)
    nb = np.sum(bins_full >= BIN_MIN, axis=-1)
    q_v = np.minimum(1.0, nb / 3.0)
    return q_n * (0.35 + 0.65 * q_v)


@dataclass
class PlanState:
    counts_full: np.ndarray      # (M,) 当前点数（折算全点频）
    bins_full: np.ndarray        # (M,6)
    c: np.ndarray                # 当前置信度
    w: np.ndarray                # 结构重要性权重（纯几何 NBV 时全 1）
    L: np.ndarray
    hit_frac: float = 1.0        # 期望点数折减（考虑入射角/回波丢失，按已飞视点实测/预测比自适应）


def objective(state: PlanState, cand, S):
    cf = state.counts_full.copy(); bf = state.bins_full.copy()
    M = len(cf)
    for v in S:
        h = cand.hits[v] * state.hit_frac
        cf += h
        bf[np.arange(M), cand.vbin[v]] += h
    return float(np.sum(state.w * np.maximum(0, predicted_cgeo(cf, bf, state.L) - state.c)))


def lazy_greedy(state: PlanState, cand, k, D, start_idx, speed=4.0, used=(), exclude_mask=None):
    """懒惰贪心（代价归一）。D：候选+起点之间安全图最短路距离矩阵，start_idx 为起点在 D 中的下标。
    返回所选视点、各步边际增益与边际代价。"""
    V = len(cand.pos)
    M = len(state.c)
    cf = state.counts_full.copy(); bf = state.bins_full.copy()
    base = predicted_cgeo(cf, bf, state.L)
    cur = np.sum(state.w * np.maximum(0, base - state.c))
    sel, gains, costs = [], [], []
    avail = np.ones(V, bool)
    avail[list(used)] = False
    if exclude_mask is not None:
        avail &= ~exclude_mask
    route_nodes = [start_idx]

    def marg(v):
        h = cand.hits[v] * state.hit_frac
        cf2 = cf + h
        bf2 = bf.copy(); bf2[np.arange(M), cand.vbin[v]] += h
        g = np.sum(state.w * np.maximum(0, predicted_cgeo(cf2, bf2, state.L) - state.c)) - cur
        dmin = np.min(D[v, route_nodes])
        cost = cand.dwell + dmin / speed
        return g, cost

    ub = np.full(V, np.inf)
    for _ in range(k):
        best, bv, bg, bc = -1.0, -1, 0.0, 1.0
        order = np.argsort(-ub)
        for v in order:
            if not avail[v]:
                continue
            if ub[v] <= best:
                break
            g, c = marg(v)
            ub[v] = g / c
            if ub[v] > best:
                best, bv, bg, bc = ub[v], v, g, c
        if bv < 0 or bg <= 1e-9:
            break
        sel.append(int(bv)); gains.append(float(bg)); costs.append(float(bc))
        avail[bv] = False
        h = cand.hits[bv] * state.hit_frac
        cf += h; bf[np.arange(M), cand.vbin[bv]] += h
        cur += bg
        route_nodes.append(int(bv))
    return sel, gains, costs


# ---------------------------------------------------------------- 安全图与航线
def safe_graph(nodes, shell, r_conn=9.0, step=0.5):
    """节点：候选视点 + 起降点 + 塔顶上方中转点；边：长度 ≤ r_conn 且整段位于安全壳/避碰区外。"""
    n = len(nodes)
    from scipy.spatial import cKDTree
    pairs = cKDTree(nodes).query_pairs(r_conn, output_type="ndarray")
    rows, cols, vals = [], [], []
    for a, b in pairs:
        if shell.segment_safe(nodes[a], nodes[b], step):
            d = float(np.linalg.norm(nodes[a] - nodes[b]))
            rows += [a, b]; cols += [b, a]; vals += [d, d]
    G = csr_matrix((vals, (rows, cols)), shape=(n, n))
    D, pred = dijkstra(G, directed=False, return_predecessors=True)
    return D, pred


def path_from_pred(pred, a, b):
    out = [b]
    while out[-1] != a:
        p = pred[a, out[-1]]
        if p < 0:
            return None
        out.append(p)
    return out[::-1]


def tsp_route(D, start, targets, end=None):
    """度量闭包上的最近邻构造 + 2-opt。start/end 为固定端点（开放路径）。"""
    targets = list(targets)
    if not targets:
        return [start] + ([end] if end is not None else [])
    route = [start]
    rem = set(targets)
    while rem:
        cur = route[-1]
        nx = min(rem, key=lambda t: D[cur, t])
        route.append(nx); rem.remove(nx)
    if end is not None:
        route.append(end)
    improved = True
    last = len(route) - (1 if end is not None else 0)
    while improved:
        improved = False
        for i in range(1, last - 1):
            for j in range(i + 1, last):
                a, b = route[i - 1], route[i]
                c = route[j]; d = route[j + 1] if j + 1 < len(route) else None
                old = D[a, b] + (D[c, d] if d is not None else 0)
                new = D[a, c] + (D[b, d] if d is not None else 0)
                if new < old - 1e-6:
                    route[i:j + 1] = route[i:j + 1][::-1]
                    improved = True
    return route


def expand_route(route, pred, nodes):
    pts = [nodes[route[0]]]
    for a, b in zip(route[:-1], route[1:]):
        p = path_from_pred(pred, a, b)
        if p is None:
            raise RuntimeError("安全图不连通")
        pts += [nodes[k] for k in p[1:]]
    return np.asarray(pts)


def route_length(route, D):
    return float(sum(D[a, b] for a, b in zip(route[:-1], route[1:])))


@dataclass
class StopRule:
    """停止判据：(1) 加权置信缺口 Σw(1−c)/Σw ≤ eps；(2) 预测最优边际增益率 < g_rate_min（单位：加权置信/秒）；
    (3) 上一轮实测增益 / 预测增益 < rho_min 且预测增益率也低（遮挡不可达）；(4) 轮次/时间预算。"""
    eps: float = 0.05
    g_rate_min: float = 3e-4
    rho_min: float = 0.2
    max_rounds: int = 6
    max_time: float = 900.0
    history: list = field(default_factory=list)

    def check(self, deficit, best_rate, realized, predicted, t_used, rnd):
        if deficit <= self.eps:
            return "缺口达标"
        if best_rate < self.g_rate_min:
            return "边际增益率过低"
        if predicted > 0 and realized / predicted < self.rho_min and best_rate < 5 * self.g_rate_min:
            return "实测/预测增益比过低"
        if rnd >= self.max_rounds:
            return "轮次预算"
        if t_used >= self.max_time:
            return "时间预算"
        return None
