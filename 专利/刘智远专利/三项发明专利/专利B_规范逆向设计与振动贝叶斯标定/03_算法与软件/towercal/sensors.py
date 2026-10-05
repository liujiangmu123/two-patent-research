# -*- coding: utf-8 -*-
"""测点优化：Fisher 信息 / 有效独立法（EfI）按三轴节点逐步剔除，及经验布置。

候选点：主材节点（塔身角点 corner、主材中间节点）与横担端部/地线支架端部。每个节点为一个三轴传感器，
提供 x、y、z 三个通道；EfI 以节点 3×3 块的 Fisher 信息贡献度量剔除。
可选：以模态参数对设计参数的灵敏度加权（参数 Fisher 信息 D 最优），见 select_dopt。
"""
from __future__ import annotations

import numpy as np


def candidate_nodes(g, kinds=("corner", "arm_tip", "peak_tip", "main_mid")):
    return [i for i, t in enumerate(g.ntype) if t in kinds]


def node_dofs(nodes, comps=(0, 1, 2)):
    return np.array([6 * n + c for n in nodes for c in comps], int)


def efi_nodes(phi, nodes, n_select, comps=(0, 1, 2), weights=None):
    """phi: (ndof, nm) 目标模态振型（全自由度）；返回选中节点列表与最终 Fisher 信息行列式（log）。"""
    nodes = list(nodes)
    blocks = {n: phi[node_dofs([n], comps)] for n in nodes}
    if weights is not None:
        blocks = {n: b * weights[None, :] for n, b in blocks.items()}
    # 去除近乎重合（同振型贡献）的对称点：按块逐步剔除
    while len(nodes) > n_select:
        Phi = np.vstack([blocks[n] for n in nodes])
        Q = Phi.T @ Phi
        Qi = np.linalg.pinv(Q)
        contrib = []
        for n in nodes:
            b = blocks[n]
            Ed = b @ Qi @ b.T                       # 该节点块的有效独立分布
            contrib.append(np.trace(Ed))
        nodes.pop(int(np.argmin(contrib)))
    Phi = np.vstack([blocks[n] for n in nodes])
    sign, ld = np.linalg.slogdet(Phi.T @ Phi)
    return nodes, float(ld if sign > 0 else -np.inf)


def select_dopt(J_by_node: dict, n_select, ridge=1e-9):
    """参数 Fisher 信息 D 最优贪心选点：J_by_node[n] 为节点 n 的观测对参数灵敏度块 (3, np)。"""
    chosen = []
    remaining = list(J_by_node)
    npar = next(iter(J_by_node.values())).shape[1]
    F = ridge * np.eye(npar)
    for _ in range(n_select):
        best, bv = None, -np.inf
        for n in remaining:
            v = np.linalg.slogdet(F + J_by_node[n].T @ J_by_node[n])[1]
            if v > bv:
                best, bv = n, v
        chosen.append(best); remaining.remove(best)
        F = F + J_by_node[best].T @ J_by_node[best]
    return chosen, float(np.linalg.slogdet(F)[1])


def empirical_nodes(g, n_select):
    """经验布置：沿同一主材（c0 角点，+x+y）自塔顶向下等间距布置，首点为塔顶角点。"""
    X = g.nodes
    cand = [i for i, t in enumerate(g.ntype) if t == "corner" and X[i, 0] > 0 and X[i, 1] > 0]
    cand = sorted(cand, key=lambda i: -X[i, 2])
    zs = np.linspace(X[cand[0], 2], X[cand[0], 2] * 0.25, n_select)
    out = []
    for z in zs:
        k = min(cand, key=lambda i: abs(X[i, 2] - z) + (1e3 if i in out else 0))
        out.append(k)
    return out


def mac(a, b):
    a = np.asarray(a); b = np.asarray(b)
    return float(np.abs(np.vdot(a, b)) ** 2 / (np.vdot(a, a).real * np.vdot(b, b).real + 1e-300))


def mac_matrix(A, B):
    num = np.abs(A.conj().T @ B) ** 2
    den = np.outer(np.sum(np.abs(A) ** 2, 0), np.sum(np.abs(B) ** 2, 0)) + 1e-300
    return num / den


def offdiag_mac(phi_s):
    M = mac_matrix(phi_s, phi_s)
    np.fill_diagonal(M, 0.0)
    return float(M.max())
