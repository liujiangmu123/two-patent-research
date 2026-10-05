# -*- coding: utf-8 -*-
"""拉普拉斯近似置信度：以随机符号梯度估计 Gauss–Newton/Fisher 信息块并叠加先验精度。

E[g gᵀ] = Σ_r ∇ℓ_r ∇ℓ_rᵀ，其中 g = ∇Σ_r s_r ℓ_r，s_r 为独立 ±1 随机符号；
取 M 个样本即可同时估计全部节点 3×3 块与杆件 [b, φ, δ1, δ2] 4×4 块（块对角近似）。
"""
from __future__ import annotations

import autograd.numpy as anp
import numpy as np
from autograd import grad

from .surfels import legs_np, sigmoid


def fisher_samples(prob, x, M=40, seed=0):
    rng = np.random.default_rng(seed)
    prob.repair(x)
    N = int(np.asarray(prob.per_ray(x)).shape[0])
    g = grad(lambda z, s: anp.sum(s * prob.per_ray(z)))
    G = np.empty((len(x), M))
    for m in range(M):
        G[:, m] = g(x, rng.choice([-1.0, 1.0], N))
    return G


def posterior_blocks(prob, x, G):
    cfg = prob.cfg
    M = G.shape[1]
    n, m = prob.n, prob.m
    sV = prob.sl["V"].start
    node_cov = np.zeros((n, 3, 3))
    pv = 1.0 / cfg.sig_node ** 2
    for i in range(n):
        r = G[sV + 3 * i:sV + 3 * i + 3]
        F = r @ r.T / M
        node_cov[i] = np.linalg.inv(F + pv * np.eye(3))
    mem_cov = np.zeros((m, 4, 4))
    pri = np.array([1 / cfg.sig_b ** 2, 1 / cfg.sig_phi ** 2, 1 / cfg.sig_delta ** 2, 1 / cfg.sig_delta ** 2])
    sb, sp, s1, s2 = (prob.sl[k].start for k in ("b", "phi", "d1", "d2"))
    for e in range(m):
        r = G[[sb + e, sp + e, s1 + e, s2 + e]]
        F = r @ r.T / M
        mem_cov[e] = np.linalg.inv(F + np.diag(pri))
    return node_cov, mem_cov


def member_confidence(prob, x, node_cov, mem_cov, b_cont=None):
    """杆件置信度 c_e = π_e · exp(−σ_b/(0.15 b)) · exp(−σ_φ/0.35) · min(c_vi, c_vj)，c_v = exp(−σ_v/0.05)。"""
    lay = prob.lay
    pi = np.asarray(sigmoid(x[prob.sl["logit"]]))
    b = np.asarray(x[prob.sl["b"]]) if b_cont is None else np.asarray(b_cont)
    sig_v = np.sqrt(np.trace(node_cov, axis1=1, axis2=2))
    c_v = np.exp(-sig_v / 0.05)
    sig_b = np.sqrt(np.maximum(mem_cov[:, 0, 0], 0))
    sig_phi = np.sqrt(np.maximum(mem_cov[:, 1, 1], 0))
    c = pi * np.exp(-sig_b / (0.15 * b)) * np.exp(-sig_phi / 0.35) * np.minimum(c_v[lay.mi], c_v[lay.mj])
    return {"pi": pi, "sig_v": sig_v, "c_v": c_v, "sig_b": sig_b, "sig_phi": sig_phi, "c": c}


def spec_posterior(b_cont, sig_b, table):
    """各杆件对规格表各肢宽档的后验概率（高斯近似）。"""
    z2 = ((np.asarray(b_cont)[:, None] - table[None, :]) / np.maximum(np.asarray(sig_b)[:, None], 1e-4)) ** 2
    w = np.exp(-0.5 * (z2 - z2.min(1, keepdims=True)))
    return w / w.sum(1, keepdims=True)
