# -*- coding: utf-8 -*-
"""同一高斯场的双模态渲染（autograd 可微）：相机像素射线与激光射线共用“射线—面元响应”。

射线 r（原点 o、单位方向 d、足迹标准差 σ_b(t)=σ0+σk·t）与面元 s 的响应（命中能量占比，权利要求 3、4）：
    ρ   = 面元中心相对射线的横向偏移（在射线横截面基 e1,e2 内）
    Σ⊥  = s1²·(P t1)(P t1)ᵀ + s2²·(P t2)(P t2)ᵀ   （面元协方差在横截面内的投影）
    h   = α·|Σ⊥|^{1/2}/|Σ⊥+σ_b²I|^{1/2}·exp(−½ ρᵀ(Σ⊥+σ_b²I)⁻¹ρ)
深度 t_s 取射线与面元平面的交点深度（掠射时限幅）。
同一射线上按深度排序合成：w_s = h_s·Π_{l<s}(1−h_l)，透射率 T = Π(1−h)，命中概率 H = 1−T。
  · 相机：轮廓占据 O=1−T，灰度 C = Σ w_s c_s + T·c_sky；
  · 激光：混合距离似然 Σ w_s N(d_meas; t_s, σ_r²)，自由空间（负证据）Σ_{t_s<d_meas−3σ_r} −log(1−h_s)。
"""
from __future__ import annotations

import autograd.numpy as anp
import numpy as np

from .adops import take
from .surfels import cross


def ray_basis(d):
    """每条射线横截面的正交基 e1, e2（numpy，配对时固定）。"""
    d = np.asarray(d, float)
    ref = np.where(np.abs(d[:, 2:3]) < 0.9, np.array([[0.0, 0.0, 1.0]]), np.array([[1.0, 0.0, 0.0]]))
    e1 = np.cross(d, ref)
    e1 /= np.linalg.norm(e1, axis=1, keepdims=True)
    e2 = np.cross(d, e1)
    return e1, e2


def _g(A, idx):
    """收集：autograd 数组用 take（快速反传），常量用 numpy 索引。"""
    if isinstance(A, np.ndarray):
        return A[idx]
    return take(A, idx)


def pair_response(S, pr, ps, o, d, e1, e2, sig0, sigk, lim, extra_blur=0.0, footprint=True):
    """返回每个配对的命中能量占比 h 与交点深度 t_s。o、d 可为 autograd 数组（相机外参标定时）。

    lim：每个配对的深度修正限幅（numpy，配对时按面元尺度确定）。
    """
    w = _g(S["mu"], ps) - _g(o, pr)
    dd = _g(d, pr)
    tc = anp.sum(w * dd, 1)
    rv = w - tc[:, None] * dd
    E1, E2 = e1[pr], e2[pr]
    r1 = anp.sum(rv * E1, 1)
    r2 = anp.sum(rv * E2, 1)
    T1, T2 = _g(S["t1"], ps), _g(S["t2"], ps)
    a1, a2 = anp.sum(T1 * E1, 1), anp.sum(T1 * E2, 1)
    b1, b2 = anp.sum(T2 * E1, 1), anp.sum(T2 * E2, 1)
    q1, q2 = _g(S["s1"], ps) ** 2, _g(S["s2"], ps) ** 2
    c11 = q1 * a1 ** 2 + q2 * b1 ** 2
    c12 = q1 * a1 * a2 + q2 * b1 * b2
    c22 = q1 * a2 ** 2 + q2 * b2 ** 2
    detS = anp.maximum(c11 * c22 - c12 ** 2, 0.0)
    if footprint:
        sb = sig0[pr] + sigk[pr] * tc + extra_blur
    else:
        sb = 1e-4 + extra_blur + 0.0 * tc
    sb2 = sb ** 2
    m11, m22 = c11 + sb2, c22 + sb2
    detM = m11 * m22 - c12 ** 2
    quad = (m22 * r1 ** 2 - 2.0 * c12 * r1 * r2 + m11 * r2 ** 2) / detM
    h = _g(S["alpha"], ps) * anp.sqrt((detS + 1e-18) / detM) * anp.exp(-0.5 * quad)
    nrm = cross(T1, T2)
    nd = anp.sum(nrm * dd, 1)
    nrv = anp.sum(nrm * rv, 1)
    nd_safe = anp.where(anp.abs(nd) < 0.08, anp.where(nd >= 0, 0.08, -0.08), nd)
    corr = anp.clip(nrv / nd_safe, -lim, lim)
    return h, tc + corr


def seg_sum(x, start, end):
    """按射线分段求和（配对已按射线连续排列）。"""
    cs = anp.concatenate([anp.zeros(1), anp.cumsum(x)])
    return take(cs, end) - take(cs, start)


def seg_excl(x, pstart):
    """射线内排他前缀和：Σ_{l<s, 同射线} x_l。pstart 为每个配对所在射线首配对位置。"""
    c = anp.cumsum(x)
    cs_prev = c - x                       # 含本身之前的全局前缀和
    cs0 = anp.concatenate([anp.zeros(1), c])
    return cs_prev - take(cs0, pstart)


def composite(h, start, end, pstart):
    """返回 lq=log(1−h)、logT（每射线）、w（每配对合成权重）。"""
    lq = anp.log1p(-h)
    logT = seg_sum(lq, start, end)
    w = h * anp.exp(seg_excl(lq, pstart))
    return lq, logT, w


def camera_terms(h, tk, pairs, mask, gray, sky, cpair, valid, w_photo=1.0):
    """相机：轮廓二元交叉熵 + 灰度 Huber（逐射线损失）。cpair 为逐配对颜色（反照率 × 明暗）。"""
    lq, logT, w = composite(h, pairs.start, pairs.end, pairs.pair_start())
    logO = anp.log(-anp.expm1(logT) + 1e-6)
    bce = -(mask * logO + (1.0 - mask) * logT)
    g = seg_sum(w * cpair, pairs.start, pairs.end) + anp.exp(logT) * sky
    e = g - gray
    hub = anp.where(anp.abs(e) < 0.05, 0.5 * e ** 2 / 0.05, anp.abs(e) - 0.025)
    return valid * (bce + w_photo * hub / 0.05)


def lidar_return_terms(h, tk, pairs, dmeas, sigr, front, eps_out=2e-3):
    """激光有回波射线：混合距离似然负对数 + 回波前方自由空间负证据（逐射线）。"""
    lq, logT, w = composite(h, pairs.start, pairs.end, pairs.pair_start())
    z = (dmeas[pairs.pr] - tk) / sigr
    lik = seg_sum(w * anp.exp(-0.5 * z ** 2), pairs.start, pairs.end)
    free = seg_sum(-lq * front, pairs.start, pairs.end)
    return -anp.log(eps_out + lik), free


def lidar_free_terms(h, pairs):
    """无塔体回波（穿过塔体包围区后命中地面或无回波）射线：自由空间负证据（逐射线）。"""
    lq = anp.log1p(-h)
    return seg_sum(-lq, pairs.start, pairs.end)
